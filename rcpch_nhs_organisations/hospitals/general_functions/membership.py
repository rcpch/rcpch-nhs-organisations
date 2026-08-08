"""
Helper functions for writing to the temporal history layer.

These wrap the close-previous / open-new pattern so that the rest of the
codebase (the ODS sync, the merger command, the admin actions) does not
have to repeat the temporal bookkeeping. Every state change goes through
one of these helpers, which guarantees the invariants the schema is
designed around:

- at most one current row per (child, relationship-type) pair
- the previous row is closed (valid_to set) before a new one opens
- the denormalised FK on the main table is updated so existing
  current-state queries keep working

See documentation/docs/developer/temporal-history.md for the design.
"""
import datetime
import logging

from django.apps import apps
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("hospitals")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _effective_date(effective_date=None) -> datetime.date:
    """Resolve the effective date for a change. Defaults to today."""
    if effective_date is None:
        return timezone.now().date()
    return effective_date


def _reassign_relationship(
    *,
    child,
    membership_model,
    child_field,
    parent_field,
    new_parent,
    effective_date=None,
):
    """
    Generic close-previous / open-new for a relationship membership table.

    Args:
        child: the entity whose parent is changing (e.g. an Organisation).
        membership_model: the membership model class (e.g. OrganisationTrustMembership).
        child_field: the name of the FK on the membership model pointing to the child
                     (e.g. "organisation").
        parent_field: the name of the FK on the membership model pointing to the parent
                      (e.g. "trust").
        new_parent: the new parent entity (e.g. a Trust).
        effective_date: the date the change takes effect. Defaults to today.

    Returns:
        The new (current) membership row.
    """
    effective_date = _effective_date(effective_date)
    with transaction.atomic():
        # Close the existing current membership row, if any.
        membership_model.objects.filter(
            **{child_field: child, "valid_to__isnull": True}
        ).update(valid_to=effective_date)
        # Open the new one.
        new_row = membership_model.objects.create(
            **{
                child_field: child,
                parent_field: new_parent,
                "valid_from": effective_date,
                "valid_to": None,
            }
        )
    logger.info(
        "Reassigned %s.%s: %s → %s (effective %s)",
        child.__class__.__name__,
        parent_field,
        getattr(child, parent_field, None),
        new_parent,
        effective_date,
    )
    return new_row


def _update_entity_attributes(
    *,
    entity,
    version_model,
    parent_field,
    effective_date=None,
    **fields,
):
    """
    Generic close-previous / open-new for an entity version table.

    Snapshots the entity's mutable attributes into a new version row, closing
    the previous current row. The main entity row is then updated in place
    so existing current-state queries keep working.

    Args:
        entity: the entity whose attributes are changing (e.g. an Organisation).
        version_model: the version model class (e.g. OrganisationVersion).
        parent_field: the name of the FK on the version model pointing to the parent
                      entity (e.g. "organisation").
        effective_date: the date the change takes effect. Defaults to today.
        **fields: the mutable attributes to update, with their new values.

    Returns:
        The new (current) version row.
    """
    effective_date = _effective_date(effective_date)
    # Snapshot the full set of mutable attributes from the current entity,
    # overriding with the new values supplied by the caller.
    snapshot = _snapshot_entity_fields(version_model, entity)
    snapshot.update(fields)

    with transaction.atomic():
        # Close the existing current version row, if any.
        version_model.objects.filter(
            **{parent_field: entity, "valid_to__isnull": True}
        ).update(valid_to=effective_date)
        # Open the new one.
        new_row = version_model.objects.create(
            **{
                parent_field: entity,
                "valid_from": effective_date,
                "valid_to": None,
            },
            **snapshot,
        )
        # Update the main entity row in place.
        for key, value in fields.items():
            setattr(entity, key, value)
        entity.save(update_fields=list(fields.keys()))
    logger.info(
        "Updated %s attributes (effective %s): %s",
        entity.__class__.__name__,
        effective_date,
        ", ".join(f"{k}={v!r}" for k, v in fields.items()),
    )
    return new_row


def _snapshot_entity_fields(version_model, entity):
    """
    Build a dict of the version model's snapshot fields, populated from the
    current entity row. Excludes the parent FK, valid_from, valid_to, and
    the timestamp fields from the abstract base class.
    """
    excluded = {"id", "valid_from", "valid_to", "created_at", "updated_at"}
    snapshot = {}
    for field in _snapshot_fields(version_model):
        attname = field.attname
        # Map the version model's attname back to the entity's attribute name.
        # The version model mirrors the entity's field names, so attname is
        # the same on both.
        snapshot[attname] = getattr(entity, attname, None)
    return snapshot


def _snapshot_fields(version_model):
    """
    Return the list of concrete field objects on ``version_model`` that hold
    snapshotted attributes. Excludes the parent FK, any other FKs (e.g. the
    network snapshot on PaediatricDiabetesUnitVersion), and the bookkeeping
    columns (id, valid_from, valid_to, created_at, updated_at).

    Used by ``_snapshot_entity_fields`` and by the admin form builder so both
    share one definition of "what is a snapshot field".
    """
    excluded = {"id", "valid_from", "valid_to", "created_at", "updated_at"}
    fields = []
    for field in version_model._meta.get_fields():
        if field.name in excluded:
            continue
        if field.is_relation and field.many_to_one:
            # Skip the parent FK and any other FK fields on the version model
            # (e.g. the network snapshot on PaediatricDiabetesUnitVersion is
            # handled explicitly by the caller if needed).
            continue
        if not hasattr(field, "attname"):
            continue
        fields.append(field)
    return fields


def _snapshot_matches(version_model, row, snapshot):
    """
    Return True if every snapshotted attribute on ``row`` equals the
    corresponding value in ``snapshot``. Used by ``_backfill_version_row`` to
    detect whether a current baseline row records the same state as a
    backfilled historical row (in which case the baseline row is redundant).
    """
    for field in _snapshot_fields(version_model):
        attname = field.attname
        if getattr(row, attname, None) != snapshot.get(attname):
            return False
    return True


# ---------------------------------------------------------------------------
# Organisation relationship reassignments
# ---------------------------------------------------------------------------


def reassign_organisation_trust(organisation, new_trust, effective_date=None):
    """Reassign an Organisation to a new Trust, recording the change in
    OrganisationTrustMembership and updating the denormalised FK."""
    new_row = _reassign_relationship(
        child=organisation,
        membership_model=apps.get_model("hospitals", "OrganisationTrustMembership"),
        child_field="organisation",
        parent_field="trust",
        new_parent=new_trust,
        effective_date=effective_date,
    )
    organisation.trust = new_trust
    organisation.save(update_fields=["trust"])
    return new_row


def reassign_organisation_local_health_board(
    organisation, new_local_health_board, effective_date=None
):
    """Reassign an Organisation to a new Local Health Board."""
    new_row = _reassign_relationship(
        child=organisation,
        membership_model=apps.get_model(
            "hospitals", "OrganisationLocalHealthBoardMembership"
        ),
        child_field="organisation",
        parent_field="local_health_board",
        new_parent=new_local_health_board,
        effective_date=effective_date,
    )
    organisation.local_health_board = new_local_health_board
    organisation.save(update_fields=["local_health_board"])
    return new_row


def reassign_organisation_integrated_care_board(
    organisation, new_integrated_care_board, effective_date=None
):
    """Reassign an Organisation to a new Integrated Care Board."""
    new_row = _reassign_relationship(
        child=organisation,
        membership_model=apps.get_model(
            "hospitals", "OrganisationIntegratedCareBoardMembership"
        ),
        child_field="organisation",
        parent_field="integrated_care_board",
        new_parent=new_integrated_care_board,
        effective_date=effective_date,
    )
    organisation.integrated_care_board = new_integrated_care_board
    organisation.save(update_fields=["integrated_care_board"])
    return new_row


def reassign_organisation_nhs_england_region(
    organisation, new_nhs_england_region, effective_date=None
):
    """Reassign an Organisation to a new NHS England Region."""
    new_row = _reassign_relationship(
        child=organisation,
        membership_model=apps.get_model(
            "hospitals", "OrganisationNHSEnglandRegionMembership"
        ),
        child_field="organisation",
        parent_field="nhs_england_region",
        new_parent=new_nhs_england_region,
        effective_date=effective_date,
    )
    organisation.nhs_england_region = new_nhs_england_region
    organisation.save(update_fields=["nhs_england_region"])
    return new_row


def reassign_organisation_openuk_network(
    organisation, new_openuk_network, effective_date=None
):
    """Reassign an Organisation to a new OPEN UK Network."""
    new_row = _reassign_relationship(
        child=organisation,
        membership_model=apps.get_model(
            "hospitals", "OrganisationOPENUKNetworkMembership"
        ),
        child_field="organisation",
        parent_field="openuk_network",
        new_parent=new_openuk_network,
        effective_date=effective_date,
    )
    organisation.openuk_network = new_openuk_network
    organisation.save(update_fields=["openuk_network"])
    return new_row


def reassign_organisation_paediatric_diabetes_unit(
    organisation, new_paediatric_diabetes_unit, effective_date=None
):
    """Reassign an Organisation to a new Paediatric Diabetes Unit.

    If the organisation was the lead_organisation of its old PDU, the old
    PDU's lead_organisation FK is set to NULL — it no longer has a lead. The
    caller (or the operator) is responsible for setting a new lead on the old
    PDU if it remains active, which is unusual for a reassignment (most
    reassignments happen during a merger where the old PDU is deactivated).
    """
    old_pdu = organisation.paediatric_diabetes_unit
    new_row = _reassign_relationship(
        child=organisation,
        membership_model=apps.get_model(
            "hospitals", "OrganisationPaediatricDiabetesUnitMembership"
        ),
        child_field="organisation",
        parent_field="paediatric_diabetes_unit",
        new_parent=new_paediatric_diabetes_unit,
        effective_date=effective_date,
    )
    organisation.paediatric_diabetes_unit = new_paediatric_diabetes_unit
    organisation.save(update_fields=["paediatric_diabetes_unit"])
    # If the reassigned org was the lead of its old PDU, clear the FK on
    # the old PDU so it doesn't dangle (point at an org that's no longer a
    # member).
    if old_pdu is not None and old_pdu.lead_organisation_id == organisation.pk:
        old_pdu.lead_organisation = None
        old_pdu.save(update_fields=["lead_organisation"])
    return new_row


def reassign_organisation_london_borough(
    organisation, new_london_borough, effective_date=None
):
    """Reassign an Organisation to a new London Borough."""
    new_row = _reassign_relationship(
        child=organisation,
        membership_model=apps.get_model(
            "hospitals", "OrganisationLondonBoroughMembership"
        ),
        child_field="organisation",
        parent_field="london_borough",
        new_parent=new_london_borough,
        effective_date=effective_date,
    )
    organisation.london_borough = new_london_borough
    organisation.save(update_fields=["london_borough"])
    return new_row


def reassign_organisation_local_authority_district(
    organisation, new_local_authority_district, effective_date=None
):
    """Reassign an Organisation to a new Local Authority District."""
    new_row = _reassign_relationship(
        child=organisation,
        membership_model=apps.get_model(
            "hospitals", "OrganisationLocalAuthorityDistrictMembership"
        ),
        child_field="organisation",
        parent_field="local_authority_district",
        new_parent=new_local_authority_district,
        effective_date=effective_date,
    )
    organisation.local_authority_district = new_local_authority_district
    organisation.save(update_fields=["local_authority_district"])
    return new_row


def reassign_organisation_lower_layer_super_output_area(
    organisation, new_lsoa, effective_date=None
):
    """Reassign an Organisation to a new Lower Layer Super Output Area."""
    new_row = _reassign_relationship(
        child=organisation,
        membership_model=apps.get_model(
            "hospitals", "OrganisationLowerLayerSuperOutputAreaMembership"
        ),
        child_field="organisation",
        parent_field="lower_layer_super_output_area",
        new_parent=new_lsoa,
        effective_date=effective_date,
    )
    organisation.lower_layer_super_output_area = new_lsoa
    organisation.save(update_fields=["lower_layer_super_output_area"])
    return new_row


# ---------------------------------------------------------------------------
# Trust relationship reassignments
# ---------------------------------------------------------------------------


def reassign_trust_integrated_care_board(trust, new_integrated_care_board, effective_date=None):
    """Reassign a Trust to a new Integrated Care Board."""
    return _reassign_relationship(
        child=trust,
        membership_model=apps.get_model(
            "hospitals", "TrustIntegratedCareBoardMembership"
        ),
        child_field="trust",
        parent_field="integrated_care_board",
        new_parent=new_integrated_care_board,
        effective_date=effective_date,
    )


def reassign_trust_nhs_england_region(trust, new_nhs_england_region, effective_date=None):
    """Reassign a Trust to a new NHS England Region."""
    return _reassign_relationship(
        child=trust,
        membership_model=apps.get_model(
            "hospitals", "TrustNHSEnglandRegionMembership"
        ),
        child_field="trust",
        parent_field="nhs_england_region",
        new_parent=new_nhs_england_region,
        effective_date=effective_date,
    )


# ---------------------------------------------------------------------------
# PDU relationship reassignments
# ---------------------------------------------------------------------------


def reassign_paediatric_diabetes_unit_network(
    paediatric_diabetes_unit, new_network, effective_date=None
):
    """Reassign a Paediatric Diabetes Unit to a new Paediatric Diabetes Network."""
    new_row = _reassign_relationship(
        child=paediatric_diabetes_unit,
        membership_model=apps.get_model(
            "hospitals", "PaediatricDiabetesUnitNetworkMembership"
        ),
        child_field="paediatric_diabetes_unit",
        parent_field="paediatric_diabetes_network",
        new_parent=new_network,
        effective_date=effective_date,
    )
    paediatric_diabetes_unit.paediatric_diabetes_network = new_network
    paediatric_diabetes_unit.save(update_fields=["paediatric_diabetes_network"])
    return new_row


# ---------------------------------------------------------------------------
# Entity attribute updates
# ---------------------------------------------------------------------------


def update_organisation_attributes(organisation, effective_date=None, **fields):
    """
    Update an Organisation's mutable attributes, recording the change in
    OrganisationVersion. The Organisation row is updated in place so existing
    current-state queries keep working.

    Example:
        update_organisation_attributes(org, name="New Name", address1="2 New St")
    """
    return _update_entity_attributes(
        entity=organisation,
        version_model=apps.get_model("hospitals", "OrganisationVersion"),
        parent_field="organisation",
        effective_date=effective_date,
        **fields,
    )


def update_trust_attributes(trust, effective_date=None, **fields):
    """Update a Trust's mutable attributes, recording the change in TrustVersion."""
    return _update_entity_attributes(
        entity=trust,
        version_model=apps.get_model("hospitals", "TrustVersion"),
        parent_field="trust",
        effective_date=effective_date,
        **fields,
    )


def update_local_health_board_attributes(local_health_board, effective_date=None, **fields):
    """Update a Local Health Board's mutable attributes, recording the change in
    LocalHealthBoardVersion."""
    return _update_entity_attributes(
        entity=local_health_board,
        version_model=apps.get_model("hospitals", "LocalHealthBoardVersion"),
        parent_field="local_health_board",
        effective_date=effective_date,
        **fields,
    )


def update_integrated_care_board_attributes(integrated_care_board, effective_date=None, **fields):
    """Update an Integrated Care Board's mutable attributes, recording the change
    in IntegratedCareBoardVersion."""
    return _update_entity_attributes(
        entity=integrated_care_board,
        version_model=apps.get_model("hospitals", "IntegratedCareBoardVersion"),
        parent_field="integrated_care_board",
        effective_date=effective_date,
        **fields,
    )


def update_nhs_england_region_attributes(nhs_england_region, effective_date=None, **fields):
    """Update an NHS England Region's mutable attributes, recording the change in
    NHSEnglandRegionVersion."""
    return _update_entity_attributes(
        entity=nhs_england_region,
        version_model=apps.get_model("hospitals", "NHSEnglandRegionVersion"),
        parent_field="nhs_england_region",
        effective_date=effective_date,
        **fields,
    )


def update_paediatric_diabetes_unit_attributes(paediatric_diabetes_unit, effective_date=None, **fields):
    """Update a Paediatric Diabetes Unit's mutable attributes, recording the change
    in PaediatricDiabetesUnitVersion."""
    return _update_entity_attributes(
        entity=paediatric_diabetes_unit,
        version_model=apps.get_model("hospitals", "PaediatricDiabetesUnitVersion"),
        parent_field="paediatric_diabetes_unit",
        effective_date=effective_date,
        **fields,
    )


def update_paediatric_diabetes_network_attributes(paediatric_diabetes_network, effective_date=None, **fields):
    """Update a Paediatric Diabetes Network's mutable attributes, recording the
    change in PaediatricDiabetesNetworkVersion."""
    return _update_entity_attributes(
        entity=paediatric_diabetes_network,
        version_model=apps.get_model("hospitals", "PaediatricDiabetesNetworkVersion"),
        parent_field="paediatric_diabetes_network",
        effective_date=effective_date,
        **fields,
    )


# ---------------------------------------------------------------------------
# Composite rename helpers (Layer 1 version write + Layer 3 succession row)
# ---------------------------------------------------------------------------
# These exist only for entities with a succession table (Trust and PDU).
# A rename is a single business event that touches two layers: the entity's
# own attributes change (Layer 1) *and* a succession row records *why* the
# change happened, distinguishing a genuine rename by NHS England from a
# silent operator correction. Membership tables are untouched — a rename
# does not change any affiliation.
# For entities without a succession table (Organisation, ICB, etc.) use the
# plain update_<entity>_attributes() helpers instead.


def rename_trust(trust, new_name, effective_date=None, notes=""):
    """Rename a Trust, recording both a TrustVersion update and a
    TrustSuccession row with succession_type='rename'.

    The Trust row's denormalised ``name`` is updated so existing current-state
    queries keep working. ``predecessor`` and ``successor`` on the succession
    row both point at the same Trust instance, since the entity persists.

    Args:
        trust: the Trust being renamed.
        new_name: the new name.
        effective_date: the date the rename takes effect. Defaults to today.
        notes: optional free-text notes for the succession row.

    Returns:
        The new (current) TrustVersion row.
    """
    effective_date = _effective_date(effective_date)
    TrustSuccession = apps.get_model("hospitals", "TrustSuccession")
    with transaction.atomic():
        new_version = update_trust_attributes(
            trust, effective_date=effective_date, name=new_name
        )
        TrustSuccession.objects.create(
            predecessor=trust,
            successor=trust,
            succession_date=effective_date,
            succession_type="rename",
            notes=notes,
        )
    logger.info(
        "Renamed Trust %s → %r (effective %s)",
        trust.ods_code,
        new_name,
        effective_date,
    )
    return new_version


def rename_paediatric_diabetes_unit(
    paediatric_diabetes_unit, new_name, effective_date=None, notes=""
):
    """Rename a Paediatric Diabetes Unit, recording both a
    PaediatricDiabetesUnitVersion update and a PaediatricDiabetesUnitSuccession
    row with succession_type='rename'.

    The PDU row's denormalised ``unit_name`` is updated so existing current-state
    queries keep working. ``predecessor`` and ``successor`` on the succession
    row both point at the same PDU instance, since the entity persists.

    Args:
        paediatric_diabetes_unit: the PDU being renamed.
        new_name: the new unit_name.
        effective_date: the date the rename takes effect. Defaults to today.
        notes: optional free-text notes for the succession row.

    Returns:
        The new (current) PaediatricDiabetesUnitVersion row.
    """
    effective_date = _effective_date(effective_date)
    PaediatricDiabetesUnitSuccession = apps.get_model(
        "hospitals", "PaediatricDiabetesUnitSuccession"
    )
    with transaction.atomic():
        new_version = update_paediatric_diabetes_unit_attributes(
            paediatric_diabetes_unit,
            effective_date=effective_date,
            unit_name=new_name,
        )
        PaediatricDiabetesUnitSuccession.objects.create(
            predecessor=paediatric_diabetes_unit,
            successor=paediatric_diabetes_unit,
            succession_date=effective_date,
            succession_type="rename",
            notes=notes,
        )
    logger.info(
        "Renamed PDU %s → %r (effective %s)",
        paediatric_diabetes_unit.pz_code,
        new_name,
        effective_date,
    )
    return new_version


# ---------------------------------------------------------------------------
# Deactivation helpers (Layer 1 version write + Layer 3 closure succession row)
# ---------------------------------------------------------------------------
# A closure is an entity ceasing to operate with no successor — e.g. a hospital
# closed through poor quality of care, or a trust dissolved with its children
# redistributed (the redistribution itself is recorded as separate split
# successions). Like a rename, a closure is a single business event that touches
# two layers: the entity's `active` flag flips (Layer 1) *and* a succession row
# with succession_type='closure' and successor=None records *why* (Layer 3).
# Membership tables are untouched — a closure does not reassign any child;
# child reassignment is recorded separately as split successions.
#
# For entities without a succession table (IntegratedCareBoard,
# NHSEnglandRegion, LocalHealthBoard, PaediatricDiabetesNetwork) use the plain
# update_<entity>_attributes(active=False) helpers instead — there is no
# succession row to write.


def deactivate_trust(trust, effective_date=None, notes=""):
    """Deactivate a Trust (closure with no successor), recording both a
    TrustVersion update with active=False and a TrustSuccession row with
    succession_type='closure' and successor=None.

    Args:
        trust: the Trust being closed.
        effective_date: the date the closure takes effect. Defaults to today.
        notes: optional free-text notes for the succession row (e.g. the
            reason for closure).

    Returns:
        The new (current) TrustVersion row.
    """
    effective_date = _effective_date(effective_date)
    TrustSuccession = apps.get_model("hospitals", "TrustSuccession")
    with transaction.atomic():
        new_version = update_trust_attributes(
            trust, effective_date=effective_date, active=False
        )
        TrustSuccession.objects.create(
            predecessor=trust,
            successor=None,
            succession_date=effective_date,
            succession_type="closure",
            notes=notes,
        )
    logger.info(
        "Deactivated Trust %s (effective %s)",
        trust.ods_code,
        effective_date,
    )
    return new_version


def deactivate_organisation(organisation, effective_date=None, notes=""):
    """Deactivate an Organisation (closure with no successor), recording both
    an OrganisationVersion update with active=False and an OrganisationSuccession
    row with succession_type='closure' and successor=None.

    Args:
        organisation: the Organisation being closed.
        effective_date: the date the closure takes effect. Defaults to today.
        notes: optional free-text notes for the succession row.

    Returns:
        The new (current) OrganisationVersion row.
    """
    effective_date = _effective_date(effective_date)
    OrganisationSuccession = apps.get_model("hospitals", "OrganisationSuccession")
    with transaction.atomic():
        new_version = update_organisation_attributes(
            organisation, effective_date=effective_date, active=False
        )
        OrganisationSuccession.objects.create(
            predecessor=organisation,
            successor=None,
            succession_date=effective_date,
            succession_type="closure",
            notes=notes,
        )
    logger.info(
        "Deactivated Organisation %s (effective %s)",
        organisation.ods_code,
        effective_date,
    )
    return new_version


def deactivate_paediatric_diabetes_unit(
    paediatric_diabetes_unit, effective_date=None, notes=""
):
    """Deactivate a Paediatric Diabetes Unit (closure with no successor),
    recording both a PaediatricDiabetesUnitVersion update with active=False and
    a PaediatricDiabetesUnitSuccession row with succession_type='closure' and
    successor=None.

    Args:
        paediatric_diabetes_unit: the PDU being closed.
        effective_date: the date the closure takes effect. Defaults to today.
        notes: optional free-text notes for the succession row.

    Returns:
        The new (current) PaediatricDiabetesUnitVersion row.
    """
    effective_date = _effective_date(effective_date)
    PaediatricDiabetesUnitSuccession = apps.get_model(
        "hospitals", "PaediatricDiabetesUnitSuccession"
    )
    with transaction.atomic():
        new_version = update_paediatric_diabetes_unit_attributes(
            paediatric_diabetes_unit, effective_date=effective_date, active=False
        )
        PaediatricDiabetesUnitSuccession.objects.create(
            predecessor=paediatric_diabetes_unit,
            successor=None,
            succession_date=effective_date,
            succession_type="closure",
            notes=notes,
        )
    logger.info(
        "Deactivated PDU %s (effective %s)",
        paediatric_diabetes_unit.pz_code,
        effective_date,
    )
    return new_version


# ---------------------------------------------------------------------------
# Backfill helpers (insert a historical state without snapshotting the current row)
# ---------------------------------------------------------------------------
# These are for recording historical states that were overwritten before the
# temporal layer was installed. The forward-looking helpers (update_*, rename_*,
# deactivate_*) snapshot the *current* entity row into the "old" version row,
# which is wrong for a backfill: the old row would record the current name for
# the period before the change date.
#
# The backfill helpers instead insert a version row with an explicit
# [valid_from, valid_to) interval and explicit attribute values, without
# touching the current entity row or the current version row. They are
# idempotent: if a row already exists for the same interval, they update it
# in place rather than creating a duplicate.
#
# These are not exposed in the admin — they are for shell use, documented in
# temporal-history.md under "Backfilling historical states".


def _backfill_version_row(
    version_model, *, parent_field, parent, valid_from, valid_to, snapshot
):
    """Insert or update a version row, enforcing the single-current-row invariant.

    If valid_to is None (the new row is intended to be the current state) and
    a current row already exists with a different valid_from, the existing
    current row is closed at the new row's valid_from date. This prevents two
    open rows (valid_to=None) for the same entity.

    If a row already exists for the exact same (parent, valid_from, valid_to)
    tuple, it is updated in place rather than duplicated.

    If valid_to is a real date (a historical backfill) and the backfilled
    snapshot matches the current row's attributes, the current row is a
    baseline migration artefact that records no real state change. Rather than
    leaving a redundant row with the same attributes as the backfilled one, the
    current row is deleted and the backfilled row is promoted to be current
    (valid_to=None). This keeps the version table semantically honest: every
    row represents a real state change, not a tracking-system event.
    """
    # Track whether the backfilled row should be promoted to be the current
    # row (valid_to=None) because it matches and replaces a baseline artefact.
    # Only set in the historical-backfill branch below.
    promote_to_current = False
    # If the new row is current (valid_to=None), handle the existing current row.
    if valid_to is None:
        existing_current = version_model.objects.filter(
            **{parent_field: parent, "valid_to__isnull": True}
        ).exclude(valid_from=valid_from).first()
        if existing_current:
            # If the existing current row starts AFTER the new row, it's a
            # baseline artefact (e.g. from the baseline migration) that
            # should be replaced — close it at the new row's valid_from and
            # delete it, since it doesn't represent a real state change.
            if existing_current.valid_from > valid_from:
                existing_current.delete()
            else:
                # The existing current row starts before the new row — close
                # it at the new row's valid_from, so the new row takes over
                # as the current state from that date forward.
                existing_current.valid_to = valid_from
                existing_current.save(update_fields=["valid_to"])
    else:
        # Historical backfill (valid_to is a real date). If the backfilled
        # snapshot matches the current row's attributes and the current row
        # starts at or after the backfill interval ends, the current row is a
        # baseline migration artefact recording no real state change —
        # promote the backfilled row to be current instead, so the version
        # table does not carry a redundant row with identical attributes.
        # The >= (rather than >) covers the contiguous-handoff case where the
        # backfill's valid_to equals the baseline row's valid_from: the two
        # rows meet exactly, and the baseline row adds nothing.
        existing_current = version_model.objects.filter(
            **{parent_field: parent, "valid_to__isnull": True}
        ).first()
        promote_to_current = (
            existing_current is not None
            and existing_current.valid_from >= valid_to
            and _snapshot_matches(version_model, existing_current, snapshot)
        )
        if promote_to_current:
            existing_current.delete()
    # Insert or update the new row using the ORIGINAL valid_to so
    # update_or_create finds an existing backfill row with that interval
    # rather than creating a duplicate.
    obj, _ = version_model.objects.update_or_create(
        **{
            parent_field: parent,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "defaults": snapshot,
        }
    )
    if promote_to_current:
        # The backfilled row is promoted to be current (valid_to=None),
        # replacing the deleted baseline artefact. Also delete any prior
        # historical row with the same valid_from and matching attributes —
        # it is now entirely subsumed by the promoted current row and would
        # otherwise linger as an orphan (e.g. a bridge row from a previous
        # run that used the baseline's valid_from as its valid_to).
        obj.valid_to = None
        obj.save(update_fields=["valid_to"])
        orphaned = version_model.objects.filter(
            **{parent_field: parent, "valid_from": valid_from}
        ).exclude(pk=obj.pk).exclude(valid_to__isnull=True)
        for orphan in orphaned:
            if _snapshot_matches(version_model, orphan, snapshot):
                orphan.delete()
    return obj


def backfill_trust_attributes(trust, valid_from, valid_to, **fields):
    """Insert a historical TrustVersion row for the interval [valid_from, valid_to)
    with the given attribute values, without touching the current entity row.

    Use this to record a past state that was overwritten before the temporal
    layer was installed. For example, to record that RM3 was called "Salford
    Royal NHS Foundation Trust" from 2001-04-01 until it was renamed to
    "Northern Care Alliance" on 2021-10-01:

        backfill_trust_attributes(
            trust,
            valid_from=datetime.date(2001, 4, 1),
            valid_to=datetime.date(2021, 10, 1),
            name="Salford Royal NHS Foundation Trust",
            active=True,
        )

    If a version row already exists for the same [valid_from, valid_to) interval,
    it is updated in place rather than duplicated.

    If valid_to is None (the new row is intended to be the current state) and
    a current row already exists with a different valid_from, the existing
    current row is closed at the new row's valid_from date. This prevents two
    open rows (valid_to=None) for the same entity — the single-current-row
    invariant.

    Args:
        trust: the Trust the historical state belongs to.
        valid_from: the date the historical state began.
        valid_to: the date the historical state ended (the date of the next
            change). Use None if this is the current state (e.g. backfilling
            the operational start date of a trust that is still active under
            the same name).
        **fields: the historical attribute values (name, active, address, etc.).
    """
    TrustVersion = apps.get_model("hospitals", "TrustVersion")
    snapshot = _snapshot_entity_fields(TrustVersion, trust)
    snapshot.update(fields)
    with transaction.atomic():
        row = _backfill_version_row(
            TrustVersion, parent_field="trust", parent=trust,
            valid_from=valid_from, valid_to=valid_to, snapshot=snapshot,
        )
    logger.info(
        "Backfilled Trust %s version %s → %s: %s",
        trust.ods_code,
        valid_from,
        valid_to or "now",
        ", ".join(f"{k}={v!r}" for k, v in fields.items()),
    )
    return row


def backfill_integrated_care_board_attributes(
    integrated_care_board, valid_from, valid_to, **fields
):
    """Insert a historical IntegratedCareBoardVersion row for the interval
    [valid_from, valid_to) with the given attribute values, without touching the
    current entity row. See backfill_trust_attributes for the full description.
    """
    IntegratedCareBoardVersion = apps.get_model(
        "hospitals", "IntegratedCareBoardVersion"
    )
    snapshot = _snapshot_entity_fields(IntegratedCareBoardVersion, integrated_care_board)
    snapshot.update(fields)
    with transaction.atomic():
        row = _backfill_version_row(
            IntegratedCareBoardVersion,
            parent_field="integrated_care_board",
            parent=integrated_care_board,
            valid_from=valid_from,
            valid_to=valid_to,
            snapshot=snapshot,
        )
    logger.info(
        "Backfilled Integrated Care Board %s version %s → %s: %s",
        integrated_care_board.ods_code,
        valid_from,
        valid_to or "now",
        ", ".join(f"{k}={v!r}" for k, v in fields.items()),
    )
    return row


def backfill_organisation_attributes(organisation, valid_from, valid_to, **fields):
    """Insert a historical OrganisationVersion row for the interval
    [valid_from, valid_to) with the given attribute values, without touching the
    current entity row. See backfill_trust_attributes for the full description.
    """
    OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")
    snapshot = _snapshot_entity_fields(OrganisationVersion, organisation)
    snapshot.update(fields)
    with transaction.atomic():
        row = _backfill_version_row(
            OrganisationVersion, parent_field="organisation", parent=organisation,
            valid_from=valid_from, valid_to=valid_to, snapshot=snapshot,
        )
    logger.info(
        "Backfilled Organisation %s version %s → %s: %s",
        organisation.ods_code,
        valid_from,
        valid_to or "now",
        ", ".join(f"{k}={v!r}" for k, v in fields.items()),
    )
    return row


def backfill_organisation_trust_membership(
    organisation, trust, valid_from, valid_to
):
    """Insert a historical OrganisationTrustMembership row for the interval
    [valid_from, valid_to), recording that the organisation was a member of the
    given trust during that period.

    Use this to record a past affiliation that was overwritten before the
    temporal layer was installed. For example, to record that an organisation
    was in Pennine Acute (RW6) from 2001-04-01 until it moved to Northern Care
    Alliance (RM3) on 2021-10-01:

        backfill_organisation_trust_membership(
            organisation,
            trust=pennine_acute,
            valid_from=datetime.date(2001, 4, 1),
            valid_to=datetime.date(2021, 10, 1),
        )

    If a membership row already exists for the same organisation, trust, and
    [valid_from, valid_to) interval, it is updated in place rather than
    duplicated.

    Args:
        organisation: the Organisation.
        trust: the Trust the organisation was affiliated to during the period.
        valid_from: the date the affiliation began.
        valid_to: the date the affiliation ended (the date of the reassignment).
    """
    OrganisationTrustMembership = apps.get_model(
        "hospitals", "OrganisationTrustMembership"
    )
    with transaction.atomic():
        obj, created = OrganisationTrustMembership.objects.update_or_create(
            organisation=organisation,
            trust=trust,
            valid_from=valid_from,
            valid_to=valid_to,
        )
    logger.info(
        "Backfilled Organisation %s → Trust %s membership %s → %s (%s)",
        organisation.ods_code,
        trust.ods_code,
        valid_from,
        valid_to or "now",
        "created" if created else "updated",
    )
    return obj


def backfill_trust_icb_membership(trust, integrated_care_board, valid_from, valid_to):
    """Insert a historical TrustIntegratedCareBoardMembership row for the
    interval [valid_from, valid_to), recording that the trust was a member of
    the given ICB during that period.

    Use this to record a past ICB affiliation that was overwritten before the
    temporal layer was installed. For example, to record that a trust was in
    Frimley ICB (QNQ) from 2020-04-01 until it moved to Thames Valley ICB
    (S0E4D) on 2026-04-01:

        backfill_trust_icb_membership(
            trust,
            integrated_care_board=frimley_icb,
            valid_from=datetime.date(2020, 4, 1),
            valid_to=datetime.date(2026, 4, 1),
        )

    If a membership row already exists for the same trust, ICB, and
    [valid_from, valid_to) interval, it is updated in place rather than
    duplicated.

    Args:
        trust: the Trust.
        integrated_care_board: the ICB the trust was affiliated to.
        valid_from: the date the affiliation began.
        valid_to: the date the affiliation ended (the date of the reassignment).
    """
    TrustIntegratedCareBoardMembership = apps.get_model(
        "hospitals", "TrustIntegratedCareBoardMembership"
    )
    with transaction.atomic():
        obj, created = TrustIntegratedCareBoardMembership.objects.update_or_create(
            trust=trust,
            integrated_care_board=integrated_care_board,
            valid_from=valid_from,
            valid_to=valid_to,
        )
    logger.info(
        "Backfilled Trust %s → ICB %s membership %s → %s (%s)",
        trust.ods_code,
        integrated_care_board.ods_code,
        valid_from,
        valid_to or "now",
        "created" if created else "updated",
    )
    return obj
