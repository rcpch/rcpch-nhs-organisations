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
        attname = field.attname
        # Map the version model's attname back to the entity's attribute name.
        # The version model mirrors the entity's field names, so attname is
        # the same on both.
        snapshot[attname] = getattr(entity, attname, None)
    return snapshot


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
    """Reassign an Organisation to a new Paediatric Diabetes Unit."""
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
