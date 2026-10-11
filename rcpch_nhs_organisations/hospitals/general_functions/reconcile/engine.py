"""
The ODS reconciliation engine.

A single per-level diff engine that treats ODS as the source of truth and
reconciles the local database against it, detecting mergers, acquisitions,
splits, closures, renames, re-parentings, and status changes. Structural
changes are queued as ``PendingOdsChange`` rows for human review; attribute-only
changes with no succession in the window are applied automatically (when
``apply=True``).

Every Layer 1–3 write goes through the existing idempotent helpers
(``backfill_*`` / ``update_*`` / ``reassign_*``) and derives interval endpoints
identically to them, so re-runs over the already-backfilled production tables
add zero rows.

See documentation/docs/developer/ods-sync.md.
"""
import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    fetch_updated_organisations,
    extract_ods_code,
    _extract_ord_fields,
    _extract_succession_info,
    _extract_trust_membership_info,
    _extract_icb_membership_info,
    current_trust_icb_code,
    _parse_ods_date,
    _diff_fields,
)
from rcpch_nhs_organisations.hospitals.general_functions.reconcile.ods_sources import (
    deep_fetch,
    fetch_roster,
    fetch_by_postcode,
    roster_ods_code,
    roster_primary_role,
    is_effectively_active,
    legal_start,
    operational_end,
    LEVEL_ROSTER_FILTERS,
    ROLE_ORG_SITE,
    TEMPORAL_FLOOR,
)
from rcpch_nhs_organisations.hospitals.general_functions.membership import (
    backfill_organisation_attributes,
    backfill_trust_attributes,
    backfill_integrated_care_board_attributes,
)

logger = logging.getLogger("hospitals")

# Level → version-row backfill helper. LHB has no helper and is handled
# directly in _promote_baseline (it only carries a name field).
_VERSION_BACKFILL_HELPERS = {
    "organisation": backfill_organisation_attributes,
    "trust": backfill_trust_attributes,
    "icb": backfill_integrated_care_board_attributes,
}


# Attribute fields to diff per level, as (model_field, ord_field) pairs. The
# ORD field names come from ``_extract_ord_fields``.
LEVEL_ATTRIBUTE_FIELDS = {
    "organisation": [
        ("name", "name"),
        ("address1", "address1"),
        ("address2", "address2"),
        ("address3", "address3"),
        ("city", "city"),
        ("county", "county"),
        ("postcode", "postcode"),
        ("telephone", "telephone"),
        ("website", "website"),
    ],
    "trust": [
        ("name", "name"),
        ("address_line_1", "address1"),
        ("address_line_2", "address2"),
        ("town", "city"),
        ("postcode", "postcode"),
        ("telephone", "telephone"),
        ("website", "website"),
    ],
    "lhb": [
        ("name", "name"),
    ],
    "icb": [
        ("name", "name"),
    ],
}

# Which levels carry an ``active`` flag that status reconciliation can flip.
LEVELS_WITH_ACTIVE = {"organisation", "trust", "icb"}


@dataclass
class DetectedChange:
    """One detected delta between ODS and the local database."""

    level: str
    ods_code: str
    change_class: str
    summary: str
    effective_date: Optional[datetime.date] = None
    payload: dict = field(default_factory=dict)
    # Attribute-only changes with no succession in the window are auto-safe:
    # the engine may apply them automatically. Everything else is structural
    # and must be queued for review.
    auto_safe: bool = False


@dataclass
class DetectionResult:
    """The outcome of a detection pass."""

    changes: list = field(default_factory=list)
    # Collapsed count of legacy "predecessor/target not in DB and pre-floor"
    # skips — the issue #172 noise, surfaced as a single number not 350 lines.
    legacy_skips: int = 0
    # ODS codes we could not deep-fetch (network/404), surfaced in the report.
    fetch_errors: list = field(default_factory=list)
    # Count of baseline version/membership rows promoted to the temporal
    # floor (see _promote_baseline). Fills the [floor, installation_day) gap
    # left by the baseline migration for stable entities.
    baseline_promotions: int = 0


def _model_for_level(level):
    mapping = {
        "organisation": "Organisation",
        "trust": "Trust",
        "lhb": "LocalHealthBoard",
        "icb": "IntegratedCareBoard",
    }
    return apps.get_model("hospitals", mapping[level])


def _succession_model_for_level(level):
    mapping = {
        "organisation": "OrganisationSuccession",
        "trust": "TrustSuccession",
        "icb": "IntegratedCareBoardSuccession",
    }
    name = mapping.get(level)
    if name is None:
        return None
    return apps.get_model("hospitals", name)


class ReconcileEngine:
    """Detect (and optionally apply) ODS reconciliation changes."""

    def __init__(
        self,
        levels,
        *,
        since=None,
        floor=TEMPORAL_FLOOR,
        rate_limiter=None,
        apply=False,
        write_queue=False,
        stdout=None,
    ):
        self.levels = list(levels)
        # ``since`` drives the incremental /sync window. None means a full
        # backfill scan (deep-fetch every held entity).
        self.since = since
        self.floor = floor
        self.rate_limiter = rate_limiter
        # apply: auto-apply the attribute-only class to the temporal layer.
        self.apply = apply
        # write_queue: persist structural changes to PendingOdsChange. Enabled
        # by --apply and by the monthly --dry-run --queue job; off for a pure
        # local dry-run (which writes nothing at all).
        self.write_queue = write_queue or apply
        self.stdout = stdout
        self._flagged_codes = None  # populated lazily for incremental runs
        # Deep-fetch cache: one ODS detail call returns an entity's entire
        # history, and several detection passes may need the same record
        # (roster zombie check, retire-by-absence confirmation, per-entity
        # deep diff, parent-trust bridge). Cache so each code is fetched once.
        self._deep_cache = {}

    def _deep_fetch(self, code):
        """Deep-fetch an ODS record once per run, caching the result (incl. None)."""
        if code in self._deep_cache:
            return self._deep_cache[code]
        record = deep_fetch(code, rate_limiter=self.rate_limiter)
        self._deep_cache[code] = record
        return record

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self):
        """Run detection across all configured levels, returning a DetectionResult."""
        result = DetectionResult()
        for level in self.levels:
            if level == "organisation":
                self._detect_organisation_level(result)
            else:
                self._detect_roster_level(level, result)
        return result

    # ------------------------------------------------------------------
    # Incremental window
    # ------------------------------------------------------------------

    def _flagged(self):
        """Return the set of ODS codes flagged by /sync, or None to scan all.

        For an incremental run (``since`` set) we deep-fetch only the entities
        the /sync feed reports as changed since the window start. For a backfill
        run (``since`` is None) we return None, meaning "deep-fetch everything".
        """
        if self.since is None:
            return None
        if self._flagged_codes is not None:
            return self._flagged_codes
        days = (timezone.now().date() - self.since).days
        days = max(1, min(days, 185))
        flagged = set()
        for item in fetch_updated_organisations(time_frame=days):
            code = extract_ods_code(item["OrgLink"])
            if code:
                flagged.add(code)
        self._flagged_codes = flagged
        return flagged

    # ------------------------------------------------------------------
    # Roster levels (trust / lhb / icb) — full reconciliation
    # ------------------------------------------------------------------

    def _detect_roster_level(self, level, result):
        model = _model_for_level(level)
        filter_param, role_id = LEVEL_ROSTER_FILTERS[level]
        roster = fetch_roster(filter_param, role_id, rate_limiter=self.rate_limiter)
        roster_by_code = {}
        for item in roster:
            code = roster_ods_code(item)
            if code:
                roster_by_code[code] = item

        db_entities = {e.ods_code: e for e in model.objects.all()}

        # Roster presence: in ODS (active), not in DB → roster-add. The roster
        # Status flag alone is unreliable (ODS leaves long-dissolved trusts
        # stamped Active for years), so confirm the candidate is genuinely still
        # open via a deep fetch before flagging. A candidate we cannot fetch is
        # surfaced anyway — we only suppress ones ODS positively shows as closed.
        for code, item in roster_by_code.items():
            if item.get("Status") != "Active":
                continue
            if code in db_entities:
                continue
            candidate = self._deep_fetch(code)
            if candidate is not None and not is_effectively_active(candidate):
                # A zombie: ODS still stamps it Active but its end date has
                # passed (e.g. a trust that merged years ago). Not a real add.
                continue
            result.changes.append(
                DetectedChange(
                    level=level,
                    ods_code=code,
                    change_class="roster-add",
                    summary=f"{item.get('Name', code)} is active in ODS but not in the database.",
                    effective_date=_parse_ods_date(item.get("LastChangeDate")),
                    payload={
                        "name": item.get("Name"),
                        "ods_status": item.get("Status"),
                        "last_change_date": item.get("LastChangeDate"),
                    },
                )
            )

        # Roster presence / status: in DB (active), missing or Inactive in ODS
        # → retire. A curated divergence (diverged_from_ods) is honoured and
        # not re-flagged.
        for code, entity in db_entities.items():
            if getattr(entity, "diverged_from_ods", False):
                continue
            db_active = getattr(entity, "active", True)
            if not db_active:
                continue
            item = roster_by_code.get(code)
            if item is None:
                # Absent from the English roster roles. Before retiring, confirm
                # the entity is really gone from ODS — a held row can be absent
                # simply because it sits outside the queried roles (e.g. a Welsh
                # LHB or a Crown-dependency site mis-stored in this table). If a
                # deep fetch shows it still effectively active, it is not a
                # retirement.
                record = self._deep_fetch(code)
                if record is not None and is_effectively_active(record):
                    continue
                result.changes.append(
                    DetectedChange(
                        level=level,
                        ods_code=code,
                        change_class="retire",
                        summary=f"{entity} is active in the database but absent from the ODS roster.",
                        payload={"reason": "absent-from-roster"},
                    )
                )
            elif item.get("Status") != "Active":
                result.changes.append(
                    DetectedChange(
                        level=level,
                        ods_code=code,
                        change_class="retire",
                        summary=f"{entity} is active in the database but Inactive in ODS.",
                        effective_date=_parse_ods_date(item.get("LastChangeDate")),
                        payload={
                            "reason": "ods-inactive",
                            "last_change_date": item.get("LastChangeDate"),
                        },
                    )
                )

        # Per-entity deep diff: attributes, successions, relationships.
        flagged = self._flagged()
        for code, entity in db_entities.items():
            if flagged is not None and code not in flagged:
                continue
            record = self._deep_fetch(code)
            if record is None:
                result.fetch_errors.append((level, code))
                continue
            self._diff_attributes(level, entity, record, result)
            self._diff_successions(level, entity, record, result)
            if level == "trust":
                self._diff_trust_icb_relationship(entity, record, result)
            self._promote_baseline(level, entity, record, result)

    # ------------------------------------------------------------------
    # Organisation level — closed set, succession-follow only
    # ------------------------------------------------------------------

    def _detect_organisation_level(self, result):
        Organisation = _model_for_level("organisation")
        flagged = self._flagged()
        for org in Organisation.objects.all():
            code = org.ods_code
            if flagged is not None and code not in flagged:
                continue
            record = self._deep_fetch(code)
            if record is None:
                result.fetch_errors.append(("organisation", code))
                continue

            self._diff_attributes("organisation", org, record, result)
            self._diff_successions("organisation", org, record, result)
            self._diff_organisation_trust_relationship(org, record, result)
            self._promote_baseline("organisation", org, record, result)

            # Effective status: an org we still hold active but that ODS has
            # effectively closed (Status Inactive OR a past end date — the ODS
            # Status flag alone is unreliable, so re-coded sites stay stamped
            # Active past their end date). Curated divergences are left alone.
            if (
                not is_effectively_active(record)
                and org.active
                and not org.diverged_from_ods
            ):
                self._detect_organisation_closure(org, record, result)

    def _detect_organisation_closure(self, org, record, result):
        """Classify a held-active org that ODS has effectively closed.

        Three outcomes, in order of confidence:

        1. The org's own ``Succs`` names a successor code → ``superseded-code``
           (we follow the closed-set chain forward to that code).
        2. No own successor, but the held parent trust has an ODS successor →
           ``parallel-code``: the site very likely re-opened under a parallel
           code beneath the successor trust (the North Middlesex pattern). We
           record the parent-trust bridge for review but never auto-pick the
           successor site — postcode is not a unique key (dozens of co-located
           sites) and names change on transfer.
        3. Neither → a plain ``retire``.
        """
        code = org.ods_code
        end = operational_end(record)
        successor = self._organisation_successor(record)
        if successor is not None:
            result.changes.append(
                DetectedChange(
                    level="organisation",
                    ods_code=code,
                    change_class="superseded-code",
                    summary=(
                        f"{org} is closed in ODS and succeeded by "
                        f"{successor['target_ods_code']}."
                    ),
                    effective_date=successor["date"] or end,
                    payload={
                        "successor_ods_code": successor["target_ods_code"],
                        "succession_date": (
                            successor["date"].isoformat()
                            if successor["date"]
                            else None
                        ),
                        "operational_end": end.isoformat() if end else None,
                    },
                )
            )
            return

        bridge = self._parent_trust_bridge(org)
        if bridge is not None:
            candidates = self._candidate_successor_codes(
                org, record, bridge["successor_trust"]
            )
            candidate_note = (
                " Candidate successor code(s) under "
                f"{bridge['successor_trust']}: {', '.join(candidates)}."
                if candidates
                else ""
            )
            result.changes.append(
                DetectedChange(
                    level="organisation",
                    ods_code=code,
                    change_class="parallel-code",
                    summary=(
                        f"{org} is closed in ODS (end "
                        f"{end.isoformat() if end else 'unknown'}) but has no own "
                        f"successor; its parent trust {bridge['predecessor_trust']} "
                        f"was succeeded by {bridge['successor_trust']} — review for a "
                        "parallel successor code under the new trust." + candidate_note
                    ),
                    effective_date=end or bridge["succession_date"],
                    payload={
                        "reason": "parent-trust-succession-bridge",
                        "operational_end": end.isoformat() if end else None,
                        "predecessor_trust": bridge["predecessor_trust"],
                        "successor_trust": bridge["successor_trust"],
                        "succession_date": (
                            bridge["succession_date"].isoformat()
                            if bridge["succession_date"]
                            else None
                        ),
                        # Candidate successor codes for human review only —
                        # never auto-picked (postcode is not a unique key).
                        "candidate_successors": candidates,
                    },
                )
            )
            return

        result.changes.append(
            DetectedChange(
                level="organisation",
                ods_code=code,
                change_class="retire",
                summary=f"{org} is closed in ODS with no successor.",
                effective_date=end,
                payload={
                    "reason": "ods-inactive",
                    "operational_end": end.isoformat() if end else None,
                },
            )
        )

    def _parent_trust_bridge(self, org):
        """If the held parent trust has an on/after-floor ODS successor, return
        bridge info ``{predecessor_trust, successor_trust, succession_date}``;
        else None.

        A closed site with no own ``Succs`` is often moved at the trust level:
        the parent trust was succeeded and the site re-opened under a parallel
        code beneath the successor trust. We surface that bridge for review
        rather than guessing the successor site.
        """
        parent = org.trust
        if parent is None:
            return None
        parent_record = self._deep_fetch(parent.ods_code)
        if parent_record is None:
            return None
        for ev in _extract_succession_info(parent_record):
            if ev["type"] != "Successor":
                continue
            if ev["date"] is not None and ev["date"] < self.floor:
                continue
            return {
                "predecessor_trust": parent.ods_code,
                "successor_trust": ev["target_ods_code"],
                "succession_date": ev["date"],
            }
        return None

    def _candidate_successor_codes(
        self, org, record, successor_trust, fetch_budget=15, limit=10
    ):
        """Surface candidate successor codes for a closed site whose parent trust
        was succeeded. Returns a sorted list of ODS codes (possibly empty).

        ODS models no explicit link between a re-coded site and its predecessor,
        so the structural bridge is: an active ``RO198`` directory site at the
        predecessor's postcode whose current (open ``RE6``) parent is the
        successor trust AND which is a genuine *parallel* code — one that was
        already open under the successor trust *before* the predecessor closed.

        That last condition is the discriminator that matters in practice. A
        hospital postcode carries dozens of co-located sites under the successor
        trust, but when two trusts merge ODS mints a fresh departmental code
        (wards, clinics) for every sub-site on the merger date. Those freshly
        minted codes share the postcode and the new trust but are not the moved
        site; the genuinely parallel code pre-dates the merger. Filtering on
        ``own legal start < predecessor's operational end`` isolates it
        (e.g. North Middlesex RAPNM closed 2024-12-31 → RAL27, open under RAL
        since 2003, is surfaced while ~28 merger-date departmental codes are
        not).

        Selection is deliberately name-free: a site's name may or may not
        survive a transfer, so names are used *only* to order the bounded deep
        fetches (a name match is fetched first so the strongest candidate is
        confirmed within budget), never as a selection criterion. Nothing is
        auto-picked — the list is surfaced for human review.
        """
        if successor_trust is None:
            return []
        fields = _extract_ord_fields(record)
        postcode = fields.get("postcode")
        if not postcode:
            return []
        predecessor_end = operational_end(record)
        pred_name = (fields.get("name") or "").strip().upper()

        # One postcode query returns every co-located site; filter cheaply on
        # the roster fields (active + RO198) before spending any deep fetch.
        prefiltered = []
        for item in fetch_by_postcode(postcode, rate_limiter=self.rate_limiter):
            candidate = roster_ods_code(item)
            if not candidate or candidate == org.ods_code:
                continue
            if roster_primary_role(item) != ROLE_ORG_SITE:
                continue
            if item.get("Status") != "Active":
                continue
            name_match = bool(pred_name) and (
                (item.get("Name") or "").strip().upper() == pred_name
            )
            prefiltered.append((candidate, name_match))

        # Deep-fetch a bounded number, name-matching sites first so the
        # strongest candidate is confirmed within budget. The name only orders
        # the fetches here; the confirmation below is purely structural.
        prefiltered.sort(key=lambda t: (not t[1], t[0]))

        confirmed = []
        for candidate, _ in prefiltered[:fetch_budget]:
            if len(confirmed) >= limit:
                break
            detail = self._deep_fetch(candidate)
            if detail is None or not is_effectively_active(detail):
                continue
            if self._open_parent_trust(detail) != successor_trust:
                continue
            # A genuine parallel code co-existed with the predecessor: it was
            # open under the successor trust before the predecessor closed.
            # This excludes the merger-date departmental codes.
            start = legal_start(detail)
            if (
                predecessor_end is not None
                and start is not None
                and start >= predecessor_end
            ):
                continue
            confirmed.append(candidate)
        return sorted(confirmed)

    def _open_parent_trust(self, record):
        """Return the ODS code of the record's current (open ``RE6``) parent
        trust, or None."""
        for membership in _extract_trust_membership_info(record):
            if membership.get("valid_to") is None:
                return membership.get("trust_ods_code")
        return None

    def _organisation_successor(self, record):
        """Return the on/after-floor Successor event for an org record, or None.

        A "Successor" event means this org was absorbed into the target — the
        target is the successor code we should follow forward.
        """
        for ev in _extract_succession_info(record):
            if ev["type"] != "Successor":
                continue
            if ev["date"] is not None and ev["date"] < self.floor:
                continue
            return ev
        return None

    # ------------------------------------------------------------------
    # Baseline promotion — fill the [floor, installation_day) gap
    # ------------------------------------------------------------------

    def _promote_baseline(self, level, entity, record, result):
        """Create or promote the entity's baseline version and membership
        rows so they reach back to ``max(legal_start, floor)``, filling the
        gap left by the baseline migration (which used ``date.today()`` for
        ``valid_from`` and created version rows only — no membership rows).

        Two cases:

        1. **Existing baseline** (the `0024` migration ran on a populated DB):
           the earliest version row starts at installation day. Promote its
           ``valid_from`` to ``max(legal_start, floor)``. For organisations,
           also promote the earliest membership rows' ``valid_from`` to the
           floor (trust/PDU rows may already be dated by the backfill
           commands — those are left alone).

        2. **Fresh DB** (the `0024` migration ran before `seed`, so no
           version or membership rows exist): create a baseline version row
           at ``max(legal_start, floor)`` snapshotting the current entity
           attributes, and create baseline membership rows at the floor for
           each non-null denormalised FK on the ``Organisation`` model.

        Idempotent: if the earliest row already starts at or before the
        target date, it is a no-op. Only writes when ``self.apply`` is True;
        in a dry run, reports what would be created or promoted.
        """
        start = legal_start(record) or self.floor
        target = max(start, self.floor)
        promoted = False

        # --- Version row ---
        earliest = entity.versions.order_by("valid_from").first()
        if earliest is None:
            # No version row (fresh DB, or the 0024 migration ran before
            # seed). Create a baseline at max(legal_start, floor).
            if self.apply:
                helper = _VERSION_BACKFILL_HELPERS.get(level)
                if helper is not None:
                    helper(entity, valid_from=target, valid_to=None)
                elif level == "lhb":
                    # No backfill helper for LHB — create directly.
                    LHBVersion = apps.get_model(
                        "hospitals", "LocalHealthBoardVersion"
                    )
                    LHBVersion.objects.create(
                        local_health_board=entity,
                        valid_from=target,
                        valid_to=None,
                        name=entity.name,
                    )
                promoted = True
            if self.stdout:
                self.stdout.write(
                    f"  {'Created' if self.apply else 'Would create'} "
                    f"{entity} baseline version: valid_from → {target}"
                )
        elif earliest.valid_from > target:
            # Existing row starts after target (installation day > floor).
            # Promote it.
            if self.apply:
                earliest.valid_from = target
                earliest.save(update_fields=["valid_from"])
                promoted = True
            if self.stdout:
                self.stdout.write(
                    f"  {'Promoted' if self.apply else 'Would promote'} "
                    f"{entity} version baseline: "
                    f"valid_from {earliest.valid_from} → {target}"
                )

        # --- Membership rows (organisation level only) ---
        # The 0024 migration created version rows only — no membership rows.
        # The backfill commands create trust and PDU memberships (from ODS
        # Rels and constants respectively), but ICB, NHS England region,
        # OPENUK, and LHB memberships at the organisation level are never
        # backfilled. Create a baseline at the floor for each non-null
        # denormalised FK, and promote existing rows that start after the
        # floor.
        if level == "organisation":
            for related_name, fk_field in (
                ("trust_memberships", "trust"),
                ("local_health_board_memberships", "local_health_board"),
                ("integrated_care_board_memberships", "integrated_care_board"),
                ("nhs_england_region_memberships", "nhs_england_region"),
                ("openuk_network_memberships", "openuk_network"),
                ("paediatric_diabetes_unit_memberships", "paediatric_diabetes_unit"),
            ):
                parent = getattr(entity, fk_field, None)
                if parent is None:
                    continue
                memberships = getattr(entity, related_name, None)
                if memberships is None:
                    continue
                earliest = memberships.order_by("valid_from").first()
                if earliest is None:
                    # No membership row — create a baseline at the floor.
                    if self.apply:
                        memberships.model.objects.create(
                            **{
                                fk_field: parent,
                                "organisation": entity,
                            },
                            valid_from=self.floor,
                            valid_to=None,
                        )
                        promoted = True
                    if self.stdout:
                        self.stdout.write(
                            f"  {'Created' if self.apply else 'Would create'} "
                            f"{entity} {related_name} baseline: "
                            f"valid_from → {self.floor}"
                        )
                elif earliest.valid_from > self.floor:
                    if self.apply:
                        earliest.valid_from = self.floor
                        earliest.save(update_fields=["valid_from"])
                        promoted = True
                    if self.stdout:
                        self.stdout.write(
                            f"  {'Promoted' if self.apply else 'Would promote'} "
                            f"{entity} {related_name} baseline: "
                            f"valid_from → {self.floor}"
                        )

        if promoted:
            result.baseline_promotions += 1

    # ------------------------------------------------------------------
    # Shared diff helpers
    # ------------------------------------------------------------------

    def _diff_attributes(self, level, entity, record, result):
        new_fields = _extract_ord_fields(record)
        spec = LEVEL_ATTRIBUTE_FIELDS[level]
        mapped = {model_field: new_fields.get(ord_field) for model_field, ord_field in spec}
        field_names = [model_field for model_field, _ in spec]
        changes = _diff_fields(entity, mapped, field_names)
        if not changes:
            return
        ods_change_date = _parse_ods_date(record.get("LastChangeDate"))
        # Attribute change is auto-safe only if there is no succession event in
        # the window — a merger-driven rename must be reviewed.
        recent_succession = any(
            ev["date"] is not None
            and ev["date"] >= self.floor
            and (self.since is None or ev["date"] >= self.since)
            for ev in _extract_succession_info(record)
        )
        result.changes.append(
            DetectedChange(
                level=level,
                ods_code=entity.ods_code,
                change_class="attribute",
                summary=(
                    f"{entity}: "
                    + ", ".join(f"{f} {old!r}→{new!r}" for f, (old, new) in changes.items())
                ),
                effective_date=ods_change_date,
                payload={
                    "changes": {f: [old, new] for f, (old, new) in changes.items()},
                    "last_change_date": record.get("LastChangeDate"),
                    "merger_in_window": recent_succession,
                },
                auto_safe=not recent_succession,
            )
        )

    def _diff_successions(self, level, entity, record, result):
        succession_model = _succession_model_for_level(level)
        if succession_model is None:
            return
        model = _model_for_level(level)
        for ev in _extract_succession_info(record):
            ev_date = ev["date"]
            target_code = ev["target_ods_code"]
            ev_type = ev["type"]

            # Floor: events wholly before 2020-12-01 are out of scope. An event
            # with no date is treated as in-scope (ODS omitted the date).
            if ev_date is not None and ev_date < self.floor:
                result.legacy_skips += 1
                continue

            target = model.objects.filter(ods_code=target_code).first()
            if target is None:
                # Target not held. For organisations this is a successor to
                # follow (closed-set follow); for trust/icb it is a roster gap.
                # Either way it is actionable, not legacy noise.
                result.changes.append(
                    DetectedChange(
                        level=level,
                        ods_code=entity.ods_code,
                        change_class="succession",
                        summary=(
                            f"{entity}: {ev_type} → {target_code} "
                            f"({ev_date or 'undated'}) — target not in database."
                        ),
                        effective_date=ev_date,
                        payload={
                            "event_type": ev_type,
                            "target_ods_code": target_code,
                            "succession_date": ev_date.isoformat() if ev_date else None,
                            "target_in_database": False,
                        },
                    )
                )
                continue

            if ev_type == "Successor":
                predecessor, successor = entity, target
            else:  # Predecessor
                predecessor, successor = target, entity

            already = succession_model.objects.filter(
                predecessor=predecessor,
                successor=successor,
                succession_date=ev_date,
            ).exists()
            if already:
                continue

            result.changes.append(
                DetectedChange(
                    level=level,
                    ods_code=entity.ods_code,
                    change_class="succession",
                    summary=(
                        f"{predecessor} → {successor} "
                        f"({ev_date or 'undated'}) — missing succession row."
                    ),
                    effective_date=ev_date,
                    payload={
                        "event_type": ev_type,
                        "predecessor_ods_code": predecessor.ods_code,
                        "successor_ods_code": successor.ods_code,
                        "succession_date": ev_date.isoformat() if ev_date else None,
                        "target_in_database": True,
                    },
                )
            )

    def _diff_trust_icb_relationship(self, trust, record, result):
        """Detect a trust's current ICB (RE5/RE8) differing from the DB membership."""
        TrustMembership = apps.get_model(
            "hospitals", "TrustIntegratedCareBoardMembership"
        )
        current_icb_code = current_trust_icb_code(
            _extract_icb_membership_info(record)
        )
        if current_icb_code is None:
            return
        db_row = (
            TrustMembership.objects.filter(trust=trust, valid_to__isnull=True)
            .select_related("integrated_care_board")
            .first()
        )
        db_code = db_row.integrated_care_board.ods_code if db_row else None
        if db_code == current_icb_code:
            return
        result.changes.append(
            DetectedChange(
                level="trust",
                ods_code=trust.ods_code,
                change_class="relationship",
                summary=(
                    f"{trust}: ICB parent {db_code or 'none'} → {current_icb_code} in ODS."
                ),
                payload={
                    "relationship": "trust-icb",
                    "old_ods_code": db_code,
                    "new_ods_code": current_icb_code,
                },
            )
        )

    def _diff_organisation_trust_relationship(self, org, record, result):
        """Detect an organisation's current parent trust (RE6) differing from the DB."""
        current_trust_code = self._current_parent_code(
            _extract_trust_membership_info(record), key="trust_ods_code"
        )
        if current_trust_code is None:
            return
        db_code = org.trust.ods_code if org.trust else None
        if db_code == current_trust_code:
            return
        result.changes.append(
            DetectedChange(
                level="organisation",
                ods_code=org.ods_code,
                change_class="relationship",
                summary=(
                    f"{org}: parent trust {db_code or 'none'} → {current_trust_code} in ODS."
                ),
                payload={
                    "relationship": "organisation-trust",
                    "old_ods_code": db_code,
                    "new_ods_code": current_trust_code,
                },
            )
        )

    @staticmethod
    def _current_parent_code(memberships, *, key):
        """Return the ODS code of the open (valid_to None) membership, or None."""
        for m in memberships:
            if m.get("valid_to") is None:
                return m.get(key)
        return None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def persist(self, result, run=None):
        """Persist detected changes.

        - Auto-safe (attribute-only, no succession in window) changes are applied
          immediately when ``apply=True``; otherwise they are only reported.
        - Structural changes are upserted into ``PendingOdsChange`` (idempotent
          on the dedup key) when ``write_queue`` is set; otherwise only reported.

        The queue is therefore the detection artefact (never a temporal write);
        ``apply`` is the only thing that mutates the Layer 1–3 tables. Returns a
        dict of counts.
        """
        counts = {"queued": 0, "requeued": 0, "applied": 0, "skipped": 0, "reported": 0}
        for change in result.changes:
            if change.auto_safe:
                if self.apply:
                    self._apply_attribute_change(change)
                    counts["applied"] += 1
                else:
                    counts["reported"] += 1
                continue
            # Structural change.
            if not self.write_queue:
                counts["reported"] += 1
                continue
            created = self._queue(change, run)
            if created is None:
                counts["skipped"] += 1
            elif created:
                counts["queued"] += 1
            else:
                counts["requeued"] += 1
        return counts

    def _queue(self, change, run):
        """Idempotently upsert a PendingOdsChange. Returns True if created, False
        if an existing pending row was refreshed, None if a terminal row exists."""
        PendingOdsChange = apps.get_model("hospitals", "PendingOdsChange")
        lookup = {
            "level": change.level,
            "ods_code": change.ods_code,
            "change_class": change.change_class,
            "effective_date": change.effective_date,
        }
        existing = PendingOdsChange.objects.filter(**lookup).first()
        payload = dict(change.payload)
        payload.setdefault("summary", change.summary)
        if existing is not None:
            if existing.is_terminal:
                # Already applied or dismissed — do not re-queue.
                return None
            existing.payload = payload
            if run is not None and existing.source_run is None:
                existing.source_run = run
            existing.save(update_fields=["payload", "source_run", "updated_at"])
            return False
        PendingOdsChange.objects.create(
            payload=payload,
            status=PendingOdsChange.STATUS_PENDING,
            source_run=run,
            **lookup,
        )
        return True

    def _apply_attribute_change(self, change):
        """Apply an auto-safe attribute change via the forward-looking helper."""
        from rcpch_nhs_organisations.hospitals.general_functions import membership as m

        helpers = {
            "organisation": m.update_organisation_attributes,
            "trust": m.update_trust_attributes,
            "lhb": m.update_local_health_board_attributes,
            "icb": m.update_integrated_care_board_attributes,
        }
        model = _model_for_level(change.level)
        entity = model.objects.filter(ods_code=change.ods_code).first()
        if entity is None:
            return
        new_values = {
            field_name: pair[1]
            for field_name, pair in change.payload.get("changes", {}).items()
        }
        effective = change.effective_date or timezone.now().date()
        with transaction.atomic():
            helpers[change.level](entity, effective_date=effective, **new_values)

    # ------------------------------------------------------------------
    # Overlap detector
    # ------------------------------------------------------------------

    def check_overlaps(self):
        """Return a list of temporal-invariant violations found in the DB.

        Asserts no entity has two open (valid_to IS NULL) version rows and no
        two version/membership rows overlap for the same entity. Used before and
        after the one-off bake to prove it added zero overlaps.
        """
        problems = []
        version_specs = [
            ("OrganisationVersion", "organisation"),
            ("TrustVersion", "trust"),
            ("LocalHealthBoardVersion", "local_health_board"),
            ("IntegratedCareBoardVersion", "integrated_care_board"),
        ]
        for model_name, parent_field in version_specs:
            model = apps.get_model("hospitals", model_name)
            problems.extend(self._check_intervals(model, parent_field))

        membership_specs = [
            ("OrganisationTrustMembership", "organisation"),
            ("TrustIntegratedCareBoardMembership", "trust"),
        ]
        for model_name, parent_field in membership_specs:
            model = apps.get_model("hospitals", model_name)
            problems.extend(self._check_intervals(model, parent_field))
        return problems

    @staticmethod
    def _check_intervals(model, parent_field):
        problems = []
        rows = list(model.objects.all().order_by(parent_field, "valid_from"))
        by_parent = {}
        for row in rows:
            by_parent.setdefault(getattr(row, f"{parent_field}_id"), []).append(row)
        for parent_id, group in by_parent.items():
            open_rows = [r for r in group if r.valid_to is None]
            if len(open_rows) > 1:
                problems.append(
                    f"{model.__name__}: {len(open_rows)} open rows for "
                    f"{parent_field}_id={parent_id}"
                )
            # Overlap check: sort by valid_from; a row's valid_from must be >=
            # the previous row's valid_to (half-open [from, to)).
            ordered = sorted(group, key=lambda r: r.valid_from)
            for prev, nxt in zip(ordered, ordered[1:]):
                prev_to = prev.valid_to or datetime.date.max
                if nxt.valid_from < prev_to:
                    problems.append(
                        f"{model.__name__}: overlapping intervals for "
                        f"{parent_field}_id={parent_id} "
                        f"({prev.valid_from}→{prev.valid_to}) and "
                        f"({nxt.valid_from}→{nxt.valid_to})"
                    )
        return problems
