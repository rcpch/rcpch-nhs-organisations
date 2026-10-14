"""
Apply path for reviewed ODS changes.

``apply_pending_change`` is the single write path invoked from the admin
"Approve & apply" action on a ``PendingOdsChange`` row. It drives the existing
idempotent temporal helpers (``update_*`` / ``reassign_*`` / ``deactivate_*`` /
``backfill_*``) and never re-implements the Layer 1–3 writes, so re-approving is
a no-op and re-running over already-applied data adds no rows.

Each handler reads the change's ``level``, ``ods_code``, ``payload`` and
``effective_date`` and returns a short human-readable description of what it
wrote. A class that genuinely needs an operator decision (a name, a successor
creation that ODS cannot disambiguate) raises ``ApplyError`` with guidance to
the relevant wizard page rather than guessing.

See documentation/docs/developer/ods-sync.md.
"""
import datetime

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from rcpch_nhs_organisations.hospitals.general_functions.reconcile.ods_sources import (
    deep_fetch,
)
from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    _extract_ord_fields,
    _extract_trust_membership_info,
)


class ApplyError(Exception):
    """Raised when a change cannot be applied automatically and needs review."""


def _model_for_level(level):
    mapping = {
        "organisation": "Organisation",
        "trust": "Trust",
        "lhb": "LocalHealthBoard",
        "icb": "IntegratedCareBoard",
    }
    return apps.get_model("hospitals", mapping[level])


def _entity(level, ods_code):
    model = _model_for_level(level)
    entity = model.objects.filter(ods_code=ods_code).first()
    if entity is None:
        raise ApplyError(f"{level} {ods_code} is not in the database.")
    return entity


def _effective(change):
    return change.effective_date or timezone.now().date()


def apply_pending_change(change, user=None):
    """Apply a single PendingOdsChange, returning a description string.

    Idempotent: if the change was already applied the handlers detect the
    existing state and return without writing again.
    """
    handlers = {
        "attribute": _apply_attribute,
        "relationship": _apply_relationship,
        "retire": _apply_retire,
        "succession": _apply_succession,
        "superseded-code": _apply_superseded_code,
        "roster-add": _apply_roster_add,
        "parallel-code": _apply_parallel_code,
    }
    handler = handlers.get(change.change_class)
    if handler is None:
        raise ApplyError(f"No apply handler for change class '{change.change_class}'.")
    return handler(change)


def _apply_attribute(change):
    from rcpch_nhs_organisations.hospitals.general_functions import membership as m

    helpers = {
        "organisation": m.update_organisation_attributes,
        "trust": m.update_trust_attributes,
        "lhb": m.update_local_health_board_attributes,
        "icb": m.update_integrated_care_board_attributes,
    }
    entity = _entity(change.level, change.ods_code)
    new_values = {
        field_name: pair[1]
        for field_name, pair in change.payload.get("changes", {}).items()
    }
    if not new_values:
        return "No attribute changes to apply."
    # Idempotency: if the entity already holds the target values, do nothing.
    if all(getattr(entity, k, None) == v for k, v in new_values.items()):
        return "Attributes already match ODS — nothing to apply."
    with transaction.atomic():
        helpers[change.level](entity, effective_date=_effective(change), **new_values)
    return f"Updated {', '.join(new_values)} on {change.ods_code}."


def _apply_relationship(change):
    from rcpch_nhs_organisations.hospitals.general_functions import membership as m

    relationship = change.payload.get("relationship")
    new_code = change.payload.get("new_ods_code")
    effective = _effective(change)
    if relationship == "organisation-trust":
        org = _entity("organisation", change.ods_code)
        Trust = apps.get_model("hospitals", "Trust")
        new_trust = Trust.objects.filter(ods_code=new_code).first()
        if new_trust is None:
            raise ApplyError(
                f"New parent trust {new_code} is not in the database. "
                "Create it (roster-add) first."
            )
        if org.trust_id == new_trust.pk:
            return "Organisation already under the ODS parent trust."
        with transaction.atomic():
            m.reassign_organisation_trust(org, new_trust, effective_date=effective)
        return f"Re-pointed {change.ods_code} to trust {new_code}."
    if relationship == "trust-icb":
        trust = _entity("trust", change.ods_code)
        ICB = apps.get_model("hospitals", "IntegratedCareBoard")
        new_icb = ICB.objects.filter(ods_code=new_code).first()
        if new_icb is None:
            raise ApplyError(
                f"New parent ICB {new_code} is not in the database. "
                "Create it (roster-add) first."
            )
        existing = apps.get_model(
            "hospitals", "TrustIntegratedCareBoardMembership"
        ).objects.filter(trust=trust, valid_to__isnull=True).first()
        if existing and existing.integrated_care_board_id == new_icb.pk:
            return "Trust already under the ODS ICB."
        with transaction.atomic():
            m.reassign_trust_integrated_care_board(
                trust, new_icb, effective_date=effective
            )
        return f"Re-pointed trust {change.ods_code} to ICB {new_code}."
    raise ApplyError(f"Unknown relationship '{relationship}'.")


def _apply_retire(change):
    from rcpch_nhs_organisations.hospitals.general_functions import membership as m

    entity = _entity(change.level, change.ods_code)
    effective = _effective(change)
    if not getattr(entity, "active", True):
        return f"{change.ods_code} is already inactive."
    with transaction.atomic():
        if change.level == "organisation":
            m.deactivate_organisation(
                entity, effective_date=effective, notes="Retired per ODS reconciliation."
            )
        elif change.level == "trust":
            m.deactivate_trust(
                entity, effective_date=effective, notes="Retired per ODS reconciliation."
            )
        elif change.level == "icb":
            m.update_integrated_care_board_attributes(
                entity, effective_date=effective, active=False
            )
        else:
            raise ApplyError(
                f"The {change.level} model has no 'active' flag; retire it by hand."
            )
    return f"Retired {change.ods_code} (active=False from {effective})."


def _apply_succession(change):
    """Create a succession row and close the predecessor, mirroring
    backfill_successions. Both entities must be in the database."""
    from rcpch_nhs_organisations.hospitals.general_functions import membership as m

    payload = change.payload
    succession_model = {
        "organisation": apps.get_model("hospitals", "OrganisationSuccession"),
        "trust": apps.get_model("hospitals", "TrustSuccession"),
        "icb": apps.get_model("hospitals", "IntegratedCareBoardSuccession"),
    }.get(change.level)
    if succession_model is None:
        raise ApplyError(f"No succession table for level '{change.level}'.")

    # The payload may carry predecessor_ods_code/successor_ods_code directly
    # (when both entities were in the DB at detect time), or it may carry
    # event_type + target_ods_code (when the target was not in the DB at
    # detect time but has since been created). Derive the pair from the
    # event type if the explicit keys are absent.
    if "predecessor_ods_code" in payload and "successor_ods_code" in payload:
        pred_code = payload["predecessor_ods_code"]
        succ_code = payload["successor_ods_code"]
    else:
        ev_type = payload.get("event_type")
        target_code = payload.get("target_ods_code")
        if not target_code:
            raise ApplyError(
                "Succession payload has no predecessor/successor or target ODS code."
            )
        if ev_type == "Successor":
            # This entity was absorbed into the target — entity is the
            # predecessor, target is the successor.
            pred_code = change.ods_code
            succ_code = target_code
        else:  # Predecessor
            # This entity absorbed the target — target is the predecessor,
            # entity is the successor.
            pred_code = target_code
            succ_code = change.ods_code

    model = _model_for_level(change.level)
    pred = model.objects.filter(ods_code=pred_code).first()
    succ = model.objects.filter(ods_code=succ_code).first()
    if pred is None or succ is None:
        missing = pred_code if pred is None else succ_code
        raise ApplyError(
            f"{missing} is not in the database. Create it first "
            f"(e.g. mergers --organisations {missing} --create), then re-approve."
        )

    ev_date = change.effective_date
    if ev_date is None:
        raise ApplyError("Succession has no effective date; set one and re-approve.")

    update_helper = {
        "organisation": m.update_organisation_attributes,
        "trust": m.update_trust_attributes,
        "icb": m.update_integrated_care_board_attributes,
    }[change.level]

    with transaction.atomic():
        existing = succession_model.objects.filter(
            predecessor=pred, successor=succ, succession_date=ev_date
        ).first()
        if existing is None:
            succession_model.objects.create(
                predecessor=pred,
                successor=succ,
                succession_date=ev_date,
                succession_type=payload.get("succession_type", "acquisition"),
                notes="Created from ODS reconciliation.",
            )
        # Close the predecessor if still active.
        if getattr(pred, "active", True):
            update_helper(pred, effective_date=ev_date, active=False)
    return f"Recorded succession {pred.ods_code} → {succ.ods_code} on {ev_date}."


def _apply_superseded_code(change):
    """Follow a held organisation's successor code: create the successor
    organisation from ODS, link via OrganisationSuccession, and close the
    predecessor. Organisation level only (the closed-set follow)."""
    from rcpch_nhs_organisations.hospitals.general_functions import membership as m

    if change.level != "organisation":
        raise ApplyError("Superseded-code changes apply to organisations only.")

    Organisation = apps.get_model("hospitals", "Organisation")
    OrganisationSuccession = apps.get_model("hospitals", "OrganisationSuccession")
    Trust = apps.get_model("hospitals", "Trust")

    pred = _entity("organisation", change.ods_code)
    successor_code = change.payload.get("successor_ods_code")
    if not successor_code:
        raise ApplyError("No successor ODS code in payload.")
    ev_date = change.effective_date or timezone.now().date()

    record = deep_fetch(successor_code)
    if record is None:
        raise ApplyError(
            f"Could not fetch the successor record {successor_code} from ODS."
        )
    fields = _extract_ord_fields(record)

    with transaction.atomic():
        successor, created = Organisation.objects.get_or_create(
            ods_code=successor_code,
            defaults={
                "name": fields.get("name"),
                "address1": fields.get("address1"),
                "address2": fields.get("address2"),
                "address3": fields.get("address3"),
                "city": fields.get("city"),
                "county": fields.get("county"),
                "postcode": fields.get("postcode"),
                "telephone": fields.get("telephone"),
                "website": fields.get("website"),
                "active": True,
            },
        )
        # Link the successor to its current parent trust from the ODS RE6 rel.
        memberships = _extract_trust_membership_info(record)
        current_trust_code = next(
            (mem["trust_ods_code"] for mem in memberships if mem.get("valid_to") is None),
            None,
        )
        if current_trust_code:
            new_trust = Trust.objects.filter(ods_code=current_trust_code).first()
            if new_trust is not None and successor.trust_id != new_trust.pk:
                m.reassign_organisation_trust(
                    successor, new_trust, effective_date=ev_date
                )

        if not OrganisationSuccession.objects.filter(
            predecessor=pred, successor=successor, succession_date=ev_date
        ).exists():
            OrganisationSuccession.objects.create(
                predecessor=pred,
                successor=successor,
                succession_date=ev_date,
                succession_type="code_change",
                notes="Created from ODS reconciliation (superseded code).",
            )
        if pred.active:
            m.update_organisation_attributes(pred, effective_date=ev_date, active=False)
        # Inherit the predecessor's non-trust memberships and baseline version
        # row to the successor, and close the predecessor's memberships.
        m.inherit_organisation_state(pred, successor, effective_date=ev_date)
    verb = "created" if created else "linked existing"
    return (
        f"Followed {change.ods_code} → {successor_code} ({verb} successor), "
        f"recorded succession and closed the predecessor."
    )


def _apply_roster_add(change):
    """Create a new trust / LHB / ICB that ODS holds but the database lacks."""
    if change.level == "organisation":
        raise ApplyError(
            "Organisations are a closed set and are never roster-added; follow "
            "a superseded code instead."
        )
    model = _model_for_level(change.level)
    name = change.payload.get("name") or change.ods_code
    with transaction.atomic():
        entity, created = model.objects.get_or_create(
            ods_code=change.ods_code,
            defaults={"name": name},
        )
    if not created:
        return f"{change.ods_code} already exists."
    return f"Created {change.level} {change.ods_code} ({name})."


def _apply_parallel_code(change):
    """Record a parallel-active-code decision.

    When the reviewer supplies a ``replacement_ods_code``, this performs the
    full reconciliation: deep-fetch the successor from ODS, create the
    ``Organisation`` row (with baseline temporal rows) if missing, link via
    ``OrganisationSuccession``, re-point it to its current parent trust,
    close the predecessor, and flag the old code as diverged. This is the
    same write path as ``_apply_superseded_code``, plus the divergence flag.

    When no replacement is supplied (the reviewer leaves it blank), only the
    divergence flag is set on the old code — the successor is not created or
    linked. This is for cases where ODS folded the site into a parent record
    rather than issuing a twin, or the reviewer wants to handle the successor
    separately via ``mergers --create``.
    """
    if change.level != "organisation":
        raise ApplyError("Parallel-code changes apply to organisations only.")

    from rcpch_nhs_organisations.hospitals.general_functions import membership as m

    Organisation = apps.get_model("hospitals", "Organisation")
    OrganisationSuccession = apps.get_model("hospitals", "OrganisationSuccession")
    Trust = apps.get_model("hospitals", "Trust")

    pred = _entity("organisation", change.ods_code)
    replacement = change.payload.get("replacement_ods_code")
    ev_date = change.effective_date or timezone.now().date()

    if not replacement:
        # No successor supplied — flag the old code as diverged only.
        with transaction.atomic():
            pred.diverged_from_ods = True
            pred.save(update_fields=["diverged_from_ods", "updated_at"])
        return f"Flagged {change.ods_code} as diverged from ODS (no replacement)."

    # Full reconciliation: create/link the successor, record the succession,
    # re-point to the parent trust, close the predecessor, and flag the
    # divergence.
    record = deep_fetch(replacement)
    if record is None:
        raise ApplyError(
            f"Could not fetch the successor record {replacement} from ODS. "
            "Create it with `python manage.py mergers --organisations "
            f"{replacement} --create` first, then re-approve."
        )
    fields = _extract_ord_fields(record)

    with transaction.atomic():
        successor, created = Organisation.objects.get_or_create(
            ods_code=replacement,
            defaults={
                "name": fields.get("name"),
                "address1": fields.get("address1"),
                "address2": fields.get("address2"),
                "address3": fields.get("address3"),
                "city": fields.get("city"),
                "county": fields.get("county"),
                "postcode": fields.get("postcode"),
                "telephone": fields.get("telephone"),
                "website": fields.get("website"),
                "active": True,
            },
        )
        # Link the successor to its current parent trust from the ODS RE6 rel.
        memberships = _extract_trust_membership_info(record)
        current_trust_code = next(
            (mem["trust_ods_code"] for mem in memberships if mem.get("valid_to") is None),
            None,
        )
        if current_trust_code:
            new_trust = Trust.objects.filter(ods_code=current_trust_code).first()
            if new_trust is not None and successor.trust_id != new_trust.pk:
                m.reassign_organisation_trust(
                    successor, new_trust, effective_date=ev_date
                )

        if not OrganisationSuccession.objects.filter(
            predecessor=pred, successor=successor, succession_date=ev_date
        ).exists():
            OrganisationSuccession.objects.create(
                predecessor=pred,
                successor=successor,
                succession_date=ev_date,
                succession_type="code_change",
                notes="Created from ODS reconciliation (parallel code).",
            )
        if pred.active:
            m.update_organisation_attributes(pred, effective_date=ev_date, active=False)
        # Flag the old code as diverged with the replacement code.
        pred.diverged_from_ods = True
        pred.ods_replacement_code = replacement
        pred.save(update_fields=["diverged_from_ods", "ods_replacement_code", "updated_at"])
        # Inherit the predecessor's non-trust memberships and baseline version
        # row to the successor, and close the predecessor's memberships.
        m.inherit_organisation_state(pred, successor, effective_date=ev_date)

    verb = "created" if created else "linked existing"
    return (
        f"Followed {change.ods_code} → {replacement} ({verb} successor), "
        f"recorded succession, closed the predecessor, and flagged "
        f"{change.ods_code} as diverged from ODS."
    )
