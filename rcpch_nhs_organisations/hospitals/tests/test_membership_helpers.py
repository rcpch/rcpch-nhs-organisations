"""
Tests for the temporal history helper functions in general_functions/membership.py.

These are the most important tests in the feature: they verify that the
helpers — which are the only sanctioned write path into the temporal layer
— actually maintain the invariants the schema is designed around:

- the previous membership/version row is closed (valid_to set)
- a new current row is opened
- the denormalised FK on the main table is updated
- as-of queries return the correct parent / attributes before and after
- the single-current-row invariant holds after the change
"""
import datetime

import pytest
from django.apps import apps
from django.contrib.gis.geos import MultiPolygon, Polygon

from rcpch_nhs_organisations.hospitals.general_functions.membership import (
    reassign_organisation_trust,
    reassign_organisation_integrated_care_board,
    reassign_organisation_paediatric_diabetes_unit,
    reassign_trust_integrated_care_board,
    reassign_paediatric_diabetes_unit_network,
    update_organisation_attributes,
    update_trust_attributes,
    rename_trust,
    rename_paediatric_diabetes_unit,
    deactivate_trust,
    deactivate_organisation,
    deactivate_paediatric_diabetes_unit,
)

Organisation = apps.get_model("hospitals", "Organisation")
OrganisationTrustMembership = apps.get_model(
    "hospitals", "OrganisationTrustMembership"
)
OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")
OrganisationIntegratedCareBoardMembership = apps.get_model(
    "hospitals", "OrganisationIntegratedCareBoardMembership"
)
OrganisationPaediatricDiabetesUnitMembership = apps.get_model(
    "hospitals", "OrganisationPaediatricDiabetesUnitMembership"
)
Trust = apps.get_model("hospitals", "Trust")
TrustVersion = apps.get_model("hospitals", "TrustVersion")
TrustIntegratedCareBoardMembership = apps.get_model(
    "hospitals", "TrustIntegratedCareBoardMembership"
)
IntegratedCareBoard = apps.get_model("hospitals", "IntegratedCareBoard")
PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")
PaediatricDiabetesNetwork = apps.get_model("hospitals", "PaediatricDiabetesNetwork")
PaediatricDiabetesUnitNetworkMembership = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitNetworkMembership"
)
TrustSuccession = apps.get_model("hospitals", "TrustSuccession")
PaediatricDiabetesUnitSuccession = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitSuccession"
)
PaediatricDiabetesUnitVersion = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitVersion"
)
OrganisationSuccession = apps.get_model("hospitals", "OrganisationSuccession")


def _square_geom(easting, northing, side=200):
    return MultiPolygon(
        Polygon(
            (
                (easting - side / 2, northing + side / 2),
                (easting - side / 2, northing - side / 2),
                (easting + side / 2, northing - side / 2),
                (easting + side / 2, northing + side / 2),
                (easting - side / 2, northing + side / 2),
            )
        )
    )


@pytest.fixture
def trust_a():
    return Trust.objects.create(ods_code="RAA", name="Trust A")


@pytest.fixture
def trust_b():
    return Trust.objects.create(ods_code="RBB", name="Trust B")


@pytest.fixture
def icb_a():
    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000001",
        name="ICB A",
        bng_e=400000,
        bng_n=400000,
        long=-1.0,
        lat=53.0,
        globalid="guid-a",
        geom=_square_geom(400000, 400000),
        ods_code="A01",
    )


@pytest.fixture
def icb_b():
    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000002",
        name="ICB B",
        bng_e=410000,
        bng_n=410000,
        long=-1.1,
        lat=53.1,
        globalid="guid-b",
        geom=_square_geom(410000, 410000),
        ods_code="A02",
    )


@pytest.fixture
def pdu_a():
    return PaediatricDiabetesUnit.objects.create(pz_code="PZA")


@pytest.fixture
def pdu_b():
    return PaediatricDiabetesUnit.objects.create(pz_code="PZB")


@pytest.fixture
def network_a():
    return PaediatricDiabetesNetwork.objects.create(pn_code="PNA", name="Network A")


@pytest.fixture
def network_b():
    return PaediatricDiabetesNetwork.objects.create(pn_code="PNB", name="Network B")


@pytest.fixture
def organisation(trust_a):
    return Organisation.objects.create(
        ods_code="RAA01",
        name="Test Org",
        address1="1 Old St",
        city="Oldtown",
        postcode="OL1 1AA",
        active=True,
        trust=trust_a,
    )


@pytest.fixture
def organisation_with_baseline(organisation):
    """Organisation with a baseline version and a baseline trust membership,
    so the helpers have a previous row to close."""
    OrganisationVersion.objects.create(
        organisation=organisation,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name=organisation.name,
        address1=organisation.address1,
        city=organisation.city,
        postcode=organisation.postcode,
        active=organisation.active,
    )
    OrganisationTrustMembership.objects.create(
        organisation=organisation,
        trust=organisation.trust,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )
    return organisation


# ---------------------------------------------------------------------------
# Relationship reassignment helpers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_reassign_organisation_trust_closes_previous_and_opens_new(
    organisation_with_baseline, trust_b
):
    """The helper closes the old membership, opens a new one, and updates the FK."""
    old_membership = OrganisationTrustMembership.objects.get(
        organisation=organisation_with_baseline, valid_to__isnull=True
    )
    old_trust = organisation_with_baseline.trust

    new_row = reassign_organisation_trust(
        organisation_with_baseline,
        trust_b,
        effective_date=datetime.date(2023, 4, 1),
    )

    # The old row is closed.
    old_membership.refresh_from_db()
    assert old_membership.valid_to == datetime.date(2023, 4, 1)
    assert old_membership.trust == old_trust

    # The new row is current and points to the new trust.
    assert new_row.is_current()
    assert new_row.trust == trust_b
    assert new_row.valid_from == datetime.date(2023, 4, 1)

    # The denormalised FK on the main table is updated.
    organisation_with_baseline.refresh_from_db()
    assert organisation_with_baseline.trust == trust_b

    # Single-current-row invariant holds.
    current_count = OrganisationTrustMembership.objects.filter(
        organisation=organisation_with_baseline, valid_to__isnull=True
    ).count()
    assert current_count == 1


@pytest.mark.django_db
def test_reassign_organisation_trust_as_of_query(
    organisation_with_baseline, trust_b
):
    """As-of queries return the correct trust before and after the reassignment."""
    reassign_organisation_trust(
        organisation_with_baseline,
        trust_b,
        effective_date=datetime.date(2023, 4, 1),
    )

    before = OrganisationTrustMembership.objects.filter(
        organisation=organisation_with_baseline,
        valid_from__lte=datetime.date(2022, 1, 1),
    ).filter(valid_to__gt=datetime.date(2022, 1, 1)).get()
    assert before.trust.ods_code == "RAA"

    after = OrganisationTrustMembership.objects.filter(
        organisation=organisation_with_baseline,
        valid_from__lte=datetime.date(2024, 1, 1),
    ).filter(valid_to__isnull=True).get()
    assert after.trust.ods_code == "RBB"


@pytest.mark.django_db
def test_reassign_organisation_trust_defaults_effective_date_to_today(
    organisation_with_baseline, trust_b
):
    """If effective_date is omitted, it defaults to today."""
    new_row = reassign_organisation_trust(organisation_with_baseline, trust_b)
    assert new_row.valid_from == datetime.date.today()


@pytest.mark.django_db
def test_reassign_organisation_integrated_care_board(
    organisation, icb_a, icb_b
):
    """The ICB reassignment helper works the same way."""
    OrganisationIntegratedCareBoardMembership.objects.create(
        organisation=organisation,
        integrated_care_board=icb_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )
    organisation.integrated_care_board = icb_a
    organisation.save(update_fields=["integrated_care_board"])

    new_row = reassign_organisation_integrated_care_board(
        organisation, icb_b, effective_date=datetime.date(2023, 4, 1)
    )
    assert new_row.is_current()
    assert new_row.integrated_care_board == icb_b
    organisation.refresh_from_db()
    assert organisation.integrated_care_board == icb_b


@pytest.mark.django_db
def test_reassign_organisation_paediatric_diabetes_unit(
    organisation, pdu_a, pdu_b
):
    OrganisationPaediatricDiabetesUnitMembership.objects.create(
        organisation=organisation,
        paediatric_diabetes_unit=pdu_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )
    organisation.paediatric_diabetes_unit = pdu_a
    organisation.save(update_fields=["paediatric_diabetes_unit"])

    new_row = reassign_organisation_paediatric_diabetes_unit(
        organisation, pdu_b, effective_date=datetime.date(2023, 4, 1)
    )
    assert new_row.is_current()
    assert new_row.paediatric_diabetes_unit == pdu_b
    organisation.refresh_from_db()
    assert organisation.paediatric_diabetes_unit == pdu_b


@pytest.mark.django_db
def test_reassign_trust_integrated_care_board(trust_a, icb_a, icb_b):
    """Trust-level reassignment works without a denormalised FK on Trust
    (Trust has no ICB FK column; the membership table is the source of truth)."""
    TrustIntegratedCareBoardMembership.objects.create(
        trust=trust_a,
        integrated_care_board=icb_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )
    new_row = reassign_trust_integrated_care_board(
        trust_a, icb_b, effective_date=datetime.date(2023, 4, 1)
    )
    assert new_row.is_current()
    assert new_row.integrated_care_board == icb_b
    # Single-current-row invariant.
    current_count = TrustIntegratedCareBoardMembership.objects.filter(
        trust=trust_a, valid_to__isnull=True
    ).count()
    assert current_count == 1


@pytest.mark.django_db
def test_reassign_paediatric_diabetes_unit_network(pdu_a, network_a, network_b):
    PaediatricDiabetesUnitNetworkMembership.objects.create(
        paediatric_diabetes_unit=pdu_a,
        paediatric_diabetes_network=network_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )
    pdu_a.paediatric_diabetes_network = network_a
    pdu_a.save(update_fields=["paediatric_diabetes_network"])

    new_row = reassign_paediatric_diabetes_unit_network(
        pdu_a, network_b, effective_date=datetime.date(2023, 4, 1)
    )
    assert new_row.is_current()
    assert new_row.paediatric_diabetes_network == network_b
    pdu_a.refresh_from_db()
    assert pdu_a.paediatric_diabetes_network == network_b


# ---------------------------------------------------------------------------
# Entity attribute update helpers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_organisation_attributes_closes_previous_and_opens_new(
    organisation_with_baseline,
):
    """The attribute helper closes the old version, opens a new one, and
    updates the main row."""
    old_version = OrganisationVersion.objects.get(
        organisation=organisation_with_baseline, valid_to__isnull=True
    )

    new_row = update_organisation_attributes(
        organisation_with_baseline,
        effective_date=datetime.date(2023, 4, 1),
        name="New Name",
        address1="2 New St",
    )

    old_version.refresh_from_db()
    assert old_version.valid_to == datetime.date(2023, 4, 1)
    assert old_version.name == "Test Org"  # old value preserved

    assert new_row.is_current()
    assert new_row.name == "New Name"
    assert new_row.address1 == "2 New St"
    # Unchanged fields are snapshotted from the current entity.
    assert new_row.city == "Oldtown"

    organisation_with_baseline.refresh_from_db()
    assert organisation_with_baseline.name == "New Name"
    assert organisation_with_baseline.address1 == "2 New St"

    # Single-current-version invariant holds.
    current_count = OrganisationVersion.objects.filter(
        organisation=organisation_with_baseline, valid_to__isnull=True
    ).count()
    assert current_count == 1


@pytest.mark.django_db
def test_update_organisation_attributes_as_of_query(
    organisation_with_baseline,
):
    """As-of queries return the correct attributes before and after the update."""
    update_organisation_attributes(
        organisation_with_baseline,
        effective_date=datetime.date(2023, 4, 1),
        name="New Name",
    )

    before = OrganisationVersion.objects.filter(
        organisation=organisation_with_baseline,
        valid_from__lte=datetime.date(2022, 1, 1),
    ).filter(valid_to__gt=datetime.date(2022, 1, 1)).get()
    assert before.name == "Test Org"

    after = OrganisationVersion.objects.filter(
        organisation=organisation_with_baseline,
        valid_from__lte=datetime.date(2024, 1, 1),
    ).filter(valid_to__isnull=True).get()
    assert after.name == "New Name"


@pytest.mark.django_db
def test_update_organisation_attributes_defaults_effective_date_to_today(
    organisation_with_baseline,
):
    new_row = update_organisation_attributes(
        organisation_with_baseline, name="New Name"
    )
    assert new_row.valid_from == datetime.date.today()


@pytest.mark.django_db
def test_update_trust_attributes(trust_a):
    """The Trust attribute helper works the same way."""
    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Trust A",
        active=True,
    )
    new_row = update_trust_attributes(
        trust_a,
        effective_date=datetime.date(2023, 4, 1),
        name="Trust A (renamed)",
    )
    assert new_row.is_current()
    assert new_row.name == "Trust A (renamed)"
    trust_a.refresh_from_db()
    assert trust_a.name == "Trust A (renamed)"
    current_count = TrustVersion.objects.filter(
        trust=trust_a, valid_to__isnull=True
    ).count()
    assert current_count == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_reassign_when_no_previous_membership_exists(organisation, trust_b):
    """If there is no previous current membership, the helper just opens a new
    one. This happens for entities created after the temporal layer was
    switched on, where the baseline backfill has not yet run."""
    new_row = reassign_organisation_trust(
        organisation, trust_b, effective_date=datetime.date(2023, 4, 1)
    )
    assert new_row.is_current()
    assert OrganisationTrustMembership.objects.filter(
        organisation=organisation
    ).count() == 1


@pytest.mark.django_db
def test_update_attributes_when_no_previous_version_exists(organisation):
    """If there is no previous current version, the helper just opens a new one."""
    new_row = update_organisation_attributes(
        organisation, effective_date=datetime.date(2023, 4, 1), name="New Name"
    )
    assert new_row.is_current()
    assert OrganisationVersion.objects.filter(
        organisation=organisation
    ).count() == 1


@pytest.mark.django_db
def test_reassign_is_atomic_on_error(organisation_with_baseline, trust_b):
    """If the new row creation fails, the previous row should not be closed.
    We simulate a failure by passing an invalid parent (None) which will
    raise an integrity error on the new row's FK."""
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        reassign_organisation_trust(
            organisation_with_baseline,
            None,  # invalid: trust FK is non-nullable
            effective_date=datetime.date(2023, 4, 1),
        )
    # The previous current row should still be open.
    # Note: because the IntegrityError aborted the atomic block, we need a
    # fresh query (the in-memory old_membership object may be stale).
    current = OrganisationTrustMembership.objects.filter(
        organisation=organisation_with_baseline, valid_to__isnull=True
    ).get()
    assert current.valid_to is None


# ---------------------------------------------------------------------------
# Composite rename helpers (Layer 1 version + Layer 3 succession)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_rename_trust_writes_version_and_succession(trust_a):
    """rename_trust writes both a TrustVersion row and a TrustSuccession row
    with succession_type='rename', in one transaction."""
    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Trust A",
        active=True,
    )

    new_version = rename_trust(
        trust_a,
        "Trust A (renamed)",
        effective_date=datetime.date(2023, 4, 1),
        notes="NHS England rename",
    )

    # Layer 1: version row written, old row closed.
    assert new_version.is_current()
    assert new_version.name == "Trust A (renamed)"
    assert new_version.valid_from == datetime.date(2023, 4, 1)
    old_version = TrustVersion.objects.get(trust=trust_a, name="Trust A")
    assert old_version.valid_to == datetime.date(2023, 4, 1)

    # Denormalised name on the Trust row updated.
    trust_a.refresh_from_db()
    assert trust_a.name == "Trust A (renamed)"

    # Layer 3: succession row written, predecessor == successor == same trust.
    succession = TrustSuccession.objects.get()
    assert succession.predecessor_id == trust_a.pk
    assert succession.successor_id == trust_a.pk
    assert succession.succession_type == "rename"
    assert succession.succession_date == datetime.date(2023, 4, 1)
    assert succession.notes == "NHS England rename"

    # Membership tables untouched.
    assert OrganisationTrustMembership.objects.filter(trust=trust_a).count() == 0


@pytest.mark.django_db
def test_rename_trust_defaults_effective_date_to_today(trust_a):
    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Trust A",
        active=True,
    )
    new_version = rename_trust(trust_a, "Trust A (renamed)")
    assert new_version.valid_from == datetime.date.today()
    succession = TrustSuccession.objects.get()
    assert succession.succession_date == datetime.date.today()


@pytest.mark.django_db
def test_rename_trust_is_atomic_on_error(trust_a):
    """If the succession row creation fails, the version write should roll back.
    We simulate a failure by passing an empty new_name, which violates the
    CharField's max_length=0 constraint... actually CharField allows empty.
    Instead we patch the succession create to raise."""
    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Trust A",
        active=True,
    )
    from unittest.mock import patch
    from django.db import IntegrityError

    with patch(
        "rcpch_nhs_organisations.hospitals.general_functions.membership.apps.get_model"
    ) as mock_get_model:
        # Allow the update_trust_attributes call to succeed by returning the
        # real TrustVersion model, but fail on the TrustSuccession lookup.
        real_get_model = apps.get_model

        def side_effect(app_label, model_name):
            if model_name == "TrustSuccession":
                raise IntegrityError("simulated failure")
            return real_get_model(app_label, model_name)

        mock_get_model.side_effect = side_effect
        with pytest.raises(IntegrityError):
            rename_trust(trust_a, "Trust A (renamed)", effective_date=datetime.date(2023, 4, 1))

    # No version row should have been committed.
    assert TrustVersion.objects.filter(trust=trust_a, name="Trust A (renamed)").count() == 0
    # The original version row should still be current.
    current = TrustVersion.objects.get(trust=trust_a, valid_to__isnull=True)
    assert current.name == "Trust A"
    # No succession row.
    assert TrustSuccession.objects.count() == 0


@pytest.mark.django_db
def test_rename_paediatric_diabetes_unit_writes_version_and_succession(pdu_a):
    """rename_paediatric_diabetes_unit writes both a PDU version row and a
    PDU succession row with succession_type='rename'."""
    PaediatricDiabetesUnitVersion.objects.create(
        paediatric_diabetes_unit=pdu_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        active=True,
    )

    new_version = rename_paediatric_diabetes_unit(
        pdu_a,
        "New PDU Name",
        effective_date=datetime.date(2023, 4, 1),
    )

    # Layer 1: version row written.
    assert new_version.is_current()
    assert new_version.unit_name == "New PDU Name"
    assert new_version.valid_from == datetime.date(2023, 4, 1)

    # Denormalised unit_name on the PDU row updated.
    pdu_a.refresh_from_db()
    assert pdu_a.unit_name == "New PDU Name"

    # Layer 3: succession row written.
    succession = PaediatricDiabetesUnitSuccession.objects.get()
    assert succession.predecessor_id == pdu_a.pk
    assert succession.successor_id == pdu_a.pk
    assert succession.succession_type == "rename"
    assert succession.succession_date == datetime.date(2023, 4, 1)


# ---------------------------------------------------------------------------
# Deactivation helpers (Layer 1 version write + Layer 3 closure succession row)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deactivate_trust_writes_version_and_closure_succession(trust_a):
    """deactivate_trust writes a TrustVersion row with active=False and a
    TrustSuccession row with succession_type='closure' and successor=None."""
    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Trust A",
        active=True,
    )

    new_version = deactivate_trust(
        trust_a,
        effective_date=datetime.date(2023, 4, 1),
        notes="Closed due to poor quality of care",
    )

    # Layer 1: version row written with active=False, old row closed.
    assert new_version.is_current()
    assert new_version.active is False
    assert new_version.valid_from == datetime.date(2023, 4, 1)
    old_version = TrustVersion.objects.get(trust=trust_a, name="Trust A", active=True)
    assert old_version.valid_to == datetime.date(2023, 4, 1)

    # Denormalised active flag on the Trust row updated.
    trust_a.refresh_from_db()
    assert trust_a.active is False

    # Layer 3: closure succession row written, successor is None.
    succession = TrustSuccession.objects.get()
    assert succession.predecessor_id == trust_a.pk
    assert succession.successor_id is None
    assert succession.succession_type == "closure"
    assert succession.succession_date == datetime.date(2023, 4, 1)
    assert succession.notes == "Closed due to poor quality of care"

    # Membership tables untouched.
    assert OrganisationTrustMembership.objects.filter(trust=trust_a).count() == 0


@pytest.mark.django_db
def test_deactivate_trust_defaults_effective_date_to_today(trust_a):
    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Trust A",
        active=True,
    )
    deactivate_trust(trust_a)
    new_version = TrustVersion.objects.get(trust=trust_a, valid_to__isnull=True)
    assert new_version.valid_from == datetime.date.today()
    assert new_version.active is False
    succession = TrustSuccession.objects.get()
    assert succession.succession_date == datetime.date.today()


@pytest.mark.django_db
def test_deactivate_organisation_writes_version_and_closure_succession(
    organisation_with_baseline,
):
    """deactivate_organisation writes an OrganisationVersion row with
    active=False and an OrganisationSuccession row with
    succession_type='closure' and successor=None."""
    new_version = deactivate_organisation(
        organisation_with_baseline,
        effective_date=datetime.date(2023, 4, 1),
        notes="Wessex House closed",
    )

    # Layer 1: version row written with active=False.
    assert new_version.is_current()
    assert new_version.active is False
    assert new_version.valid_from == datetime.date(2023, 4, 1)

    # Denormalised active flag updated.
    organisation_with_baseline.refresh_from_db()
    assert organisation_with_baseline.active is False

    # Layer 3: closure succession row written, successor is None.
    succession = OrganisationSuccession.objects.get()
    assert succession.predecessor_id == organisation_with_baseline.pk
    assert succession.successor_id is None
    assert succession.succession_type == "closure"
    assert succession.notes == "Wessex House closed"


@pytest.mark.django_db
def test_deactivate_paediatric_diabetes_unit_writes_version_and_closure_succession(
    pdu_a,
):
    """deactivate_paediatric_diabetes_unit writes a PDU version row with
    active=False and a PDU succession row with succession_type='closure'."""
    PaediatricDiabetesUnitVersion.objects.create(
        paediatric_diabetes_unit=pdu_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        active=True,
    )

    new_version = deactivate_paediatric_diabetes_unit(
        pdu_a,
        effective_date=datetime.date(2023, 4, 1),
    )

    # Layer 1: version row written with active=False.
    assert new_version.is_current()
    assert new_version.active is False
    assert new_version.valid_from == datetime.date(2023, 4, 1)

    # Denormalised active flag updated.
    pdu_a.refresh_from_db()
    assert pdu_a.active is False

    # Layer 3: closure succession row written, successor is None.
    succession = PaediatricDiabetesUnitSuccession.objects.get()
    assert succession.predecessor_id == pdu_a.pk
    assert succession.successor_id is None
    assert succession.succession_type == "closure"


@pytest.mark.django_db
def test_deactivate_trust_is_atomic_on_error(trust_a):
    """If the succession row creation fails, the version write should roll back."""
    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Trust A",
        active=True,
    )
    from unittest.mock import patch
    from django.db import IntegrityError

    with patch(
        "rcpch_nhs_organisations.hospitals.general_functions.membership.apps.get_model"
    ) as mock_get_model:
        real_get_model = apps.get_model

        def side_effect(app_label, model_name):
            if model_name == "TrustSuccession":
                raise IntegrityError("simulated failure")
            return real_get_model(app_label, model_name)

        mock_get_model.side_effect = side_effect
        with pytest.raises(IntegrityError):
            deactivate_trust(trust_a, effective_date=datetime.date(2023, 4, 1))

    # No version row should have been committed.
    assert TrustVersion.objects.filter(trust=trust_a, active=False).count() == 0
    # The original version row should still be current.
    current = TrustVersion.objects.get(trust=trust_a, valid_to__isnull=True)
    assert current.active is True
    # No succession row.
    assert TrustSuccession.objects.count() == 0
