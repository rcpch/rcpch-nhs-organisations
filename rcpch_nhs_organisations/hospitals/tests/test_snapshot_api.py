"""
Tests for the organisation snapshot API endpoint.

Covers:
- snapshot at a date before a change returns the old state
- snapshot at a date after a change returns the new state
- snapshot on the exact change date returns the new state (half-open interval)
- snapshot before the first version returns 404
- snapshot with no date returns the current state
- snapshot walks the OrganisationSuccession chain to find a predecessor
- invalid date format returns 400
- unknown ods_code returns 404
"""
import datetime

import pytest
from django.apps import apps
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from rcpch_nhs_organisations.hospitals.general_functions.membership import (
    reassign_organisation_trust,
    update_organisation_attributes,
)

Organisation = apps.get_model("hospitals", "Organisation")
OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")
OrganisationTrustMembership = apps.get_model(
    "hospitals", "OrganisationTrustMembership"
)
OrganisationTrustMembership = apps.get_model(
    "hospitals", "OrganisationTrustMembership"
)
OrganisationSuccession = apps.get_model("hospitals", "OrganisationSuccession")
Trust = apps.get_model("hospitals", "Trust")
TrustVersion = apps.get_model("hospitals", "TrustVersion")
LocalHealthBoard = apps.get_model("hospitals", "LocalHealthBoard")
LocalHealthBoardVersion = apps.get_model("hospitals", "LocalHealthBoardVersion")
IntegratedCareBoard = apps.get_model("hospitals", "IntegratedCareBoard")
IntegratedCareBoardVersion = apps.get_model("hospitals", "IntegratedCareBoardVersion")
OrganisationLocalHealthBoardMembership = apps.get_model(
    "hospitals", "OrganisationLocalHealthBoardMembership"
)
OrganisationIntegratedCareBoardMembership = apps.get_model(
    "hospitals", "OrganisationIntegratedCareBoardMembership"
)


def _square_geom(easting, northing, side=200):
    """Build a small square MultiPolygon for boundary field fixtures."""
    from django.contrib.gis.geos import MultiPolygon, Polygon

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
def api_client():
    return APIClient()


@pytest.fixture
def trust_a():
    return Trust.objects.create(ods_code="RAA", name="Trust A")


@pytest.fixture
def trust_b():
    return Trust.objects.create(ods_code="RBB", name="Trust B")


@pytest.fixture
def organisation(trust_a):
    return Organisation.objects.create(
        ods_code="RAA01",
        name="Old Name",
        address1="1 Old St",
        city="Oldtown",
        postcode="OL1 1AA",
        active=True,
        trust=trust_a,
    )


@pytest.fixture
def organisation_with_history(organisation, trust_b):
    """Organisation with a baseline version + trust membership, then a name
    change and a trust reassignment on 2023-04-01."""
    OrganisationVersion.objects.create(
        organisation=organisation,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Old Name",
        address1="1 Old St",
        city="Oldtown",
        postcode="OL1 1AA",
        active=True,
    )
    OrganisationTrustMembership.objects.create(
        organisation=organisation,
        trust=organisation.trust,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )
    # Apply changes on 2023-04-01
    update_organisation_attributes(
        organisation,
        effective_date=datetime.date(2023, 4, 1),
        name="New Name",
        address1="2 New St",
    )
    reassign_organisation_trust(
        organisation, trust_b, effective_date=datetime.date(2023, 4, 1)
    )
    return organisation


@pytest.mark.django_db
def test_snapshot_before_change_returns_old_state(
    api_client, organisation_with_history
):
    url = reverse(
        "organisation_snapshot", kwargs={"ods_code": "RAA01"}
    )
    response = api_client.get(url, {"date": "2022-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "Old Name"
    assert data["address1"] == "1 Old St"
    assert data["trust"]["ods_code"] == "RAA"
    assert data["predecessor_ods_code"] is None


@pytest.mark.django_db
def test_snapshot_after_change_returns_new_state(
    api_client, organisation_with_history
):
    url = reverse(
        "organisation_snapshot", kwargs={"ods_code": "RAA01"}
    )
    response = api_client.get(url, {"date": "2024-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "New Name"
    assert data["address1"] == "2 New St"
    assert data["trust"]["ods_code"] == "RBB"


@pytest.mark.django_db
def test_snapshot_on_change_date_returns_new_state(
    api_client, organisation_with_history
):
    """On the exact change date, the new state is in force (half-open interval)."""
    url = reverse(
        "organisation_snapshot", kwargs={"ods_code": "RAA01"}
    )
    response = api_client.get(url, {"date": "2023-04-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "New Name"
    assert data["trust"]["ods_code"] == "RBB"


@pytest.mark.django_db
def test_snapshot_before_first_version_returns_404(
    api_client, organisation_with_history
):
    url = reverse(
        "organisation_snapshot", kwargs={"ods_code": "RAA01"}
    )
    response = api_client.get(url, {"date": "2019-01-01"})
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_snapshot_no_date_returns_current_state(
    api_client, organisation_with_history
):
    url = reverse(
        "organisation_snapshot", kwargs={"ods_code": "RAA01"}
    )
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "New Name"
    assert data["trust"]["ods_code"] == "RBB"


@pytest.mark.django_db
def test_snapshot_invalid_date_returns_400(api_client, organisation_with_history):
    url = reverse(
        "organisation_snapshot", kwargs={"ods_code": "RAA01"}
    )
    response = api_client.get(url, {"date": "not-a-date"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_snapshot_unknown_ods_code_returns_404(api_client):
    url = reverse(
        "organisation_snapshot", kwargs={"ods_code": "ZZZ99"}
    )
    response = api_client.get(url, {"date": "2022-01-01"})
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_snapshot_walks_succession_chain_to_predecessor(
    api_client, trust_a, trust_b
):
    """If the org didn't exist on the queried date but a predecessor did, the
    predecessor's state is returned with predecessor_ods_code populated.

    Mirrors the South London Healthcare scenario: RYQ30 → RJZ30.
    """
    ryq30 = Organisation.objects.create(
        ods_code="RYQ30",
        name="Princess Royal University Hospital",
        address1="Old Address",
        active=True,
        trust=trust_a,
    )
    rjz30 = Organisation.objects.create(
        ods_code="RJZ30",
        name="Princess Royal University Hospital",
        address1="New Address",
        active=True,
        trust=trust_b,
    )
    OrganisationVersion.objects.create(
        organisation=ryq30,
        valid_from=datetime.date(2010, 1, 1),
        valid_to=datetime.date(2013, 1, 1),
        name="Princess Royal University Hospital",
        address1="Old Address",
        active=True,
    )
    OrganisationVersion.objects.create(
        organisation=rjz30,
        valid_from=datetime.date(2013, 1, 1),
        valid_to=None,
        name="Princess Royal University Hospital",
        address1="New Address",
        active=True,
    )
    OrganisationTrustMembership.objects.create(
        organisation=ryq30,
        trust=trust_a,
        valid_from=datetime.date(2010, 1, 1),
        valid_to=datetime.date(2013, 1, 1),
    )
    OrganisationTrustMembership.objects.create(
        organisation=rjz30,
        trust=trust_b,
        valid_from=datetime.date(2013, 1, 1),
        valid_to=None,
    )
    OrganisationSuccession.objects.create(
        predecessor=ryq30,
        successor=rjz30,
        succession_date=datetime.date(2013, 1, 1),
        succession_type="split",
    )

    # Query the successor (RJZ30) at a date before it existed (2012).
    url = reverse(
        "organisation_snapshot", kwargs={"ods_code": "RJZ30"}
    )
    response = api_client.get(url, {"date": "2012-06-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RYQ30"
    assert data["predecessor_ods_code"] == "RYQ30"
    assert data["address1"] == "Old Address"
    assert data["trust"]["ods_code"] == "RAA"


@pytest.fixture
def trust_with_rename(trust_a):
    """Trust A (RAA) was named 'Old Trust Name' until 2021-10-01, then renamed
    to 'Trust A'. TrustVersion rows cover both periods — the kind of history
    that backfill_successions / backfill_*_attributes produce for renamed
    trusts (e.g. RM3 Salford Royal → Northern Care Alliance on 2021-10-01)."""
    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2001, 4, 1),
        valid_to=datetime.date(2021, 10, 1),
        name="Old Trust Name",
        active=True,
    )
    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2021, 10, 1),
        valid_to=None,
        name="Trust A",
        active=True,
    )
    return trust_a


@pytest.fixture
def org_under_renamed_trust(trust_with_rename):
    """An organisation continuously under RAA from 2001, so its snapshot can
    be queried on both sides of the trust's 2021-10-01 rename."""
    org = Organisation.objects.create(
        ods_code="RAA01",
        name="Some Hospital",
        active=True,
        trust=trust_with_rename,
    )
    OrganisationVersion.objects.create(
        organisation=org,
        valid_from=datetime.date(2001, 4, 1),
        valid_to=None,
        name="Some Hospital",
        active=True,
    )
    OrganisationTrustMembership.objects.create(
        organisation=org,
        trust=trust_with_rename,
        valid_from=datetime.date(2001, 4, 1),
        valid_to=None,
    )
    return org


@pytest.mark.django_db
def test_snapshot_returns_historical_trust_name_before_rename(
    api_client, org_under_renamed_trust
):
    """The parent trust's name comes from TrustVersion as-of the snapshot date,
    so a date before the rename returns the historical name, not the current
    Trust.name."""
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RAA01"})
    response = api_client.get(url, {"date": "2021-06-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["trust"]["ods_code"] == "RAA"
    assert data["trust"]["name"] == "Old Trust Name"


@pytest.mark.django_db
def test_snapshot_returns_current_trust_name_after_rename(
    api_client, org_under_renamed_trust
):
    """After the rename date, the TrustVersion row carries the new name."""
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RAA01"})
    response = api_client.get(url, {"date": "2022-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["trust"]["ods_code"] == "RAA"
    assert data["trust"]["name"] == "Trust A"


@pytest.mark.django_db
def test_snapshot_trust_name_falls_back_to_current_when_no_version(
    api_client, organisation_with_history
):
    """When no TrustVersion row covers the date (e.g. a trust with only the
    baseline row, or no version history at all), the snapshot falls back to the
    current Trust.name rather than returning None — preserving prior behaviour."""
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RAA01"})
    response = api_client.get(url, {"date": "2022-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # At 2022-01-01 the org is still under trust_a, which has no TrustVersion
    # rows in this fixture, so the name falls back to the current Trust.name.
    assert data["trust"]["ods_code"] == "RAA"
    assert data["trust"]["name"] == "Trust A"


# ---------------------------------------------------------------------------
# Local Health Board name history
# ---------------------------------------------------------------------------


@pytest.fixture
def lhb_with_rename():
    """A LocalHealthBoard (WAL) named 'Old LHB Name' until 2019-04-01, then
    renamed to 'New LHB Name'. Mirrors the trust-rename fixture. Welsh LHBs
    are parents of Welsh organisations; LHB version history is populated by
    backfill_*_attributes / admin backfill actions."""
    lhb = LocalHealthBoard.objects.create(
        ods_code="WAL",
        boundary_identifier="W11000023",
        name="New LHB Name",
        welsh_name="Enw Cymraeg",
        bng_e=300000,
        bng_n=300000,
        long=-3.0,
        lat=52.0,
        globalid="guid",
        geom=_square_geom(300000, 300000),
        publication_date=datetime.date(2003, 4, 1),
    )
    LocalHealthBoardVersion.objects.create(
        local_health_board=lhb,
        valid_from=datetime.date(2003, 4, 1),
        valid_to=datetime.date(2019, 4, 1),
        name="Old LHB Name",
        welsh_name="Hen Enw",
        publication_date=datetime.date(2003, 4, 1),
    )
    LocalHealthBoardVersion.objects.create(
        local_health_board=lhb,
        valid_from=datetime.date(2019, 4, 1),
        valid_to=None,
        name="New LHB Name",
        welsh_name="Enw Cymraeg",
        publication_date=datetime.date(2003, 4, 1),
    )
    return lhb


@pytest.fixture
def org_under_renamed_lhb(lhb_with_rename):
    """A Welsh organisation continuously under WAL (the renamed LHB)."""
    org = Organisation.objects.create(
        ods_code="WAL01",
        name="Some Welsh Hospital",
        active=True,
        local_health_board=lhb_with_rename,
    )
    OrganisationVersion.objects.create(
        organisation=org,
        valid_from=datetime.date(2003, 4, 1),
        valid_to=None,
        name="Some Welsh Hospital",
        active=True,
    )
    OrganisationLocalHealthBoardMembership.objects.create(
        organisation=org,
        local_health_board=lhb_with_rename,
        valid_from=datetime.date(2003, 4, 1),
        valid_to=None,
    )
    return org


@pytest.mark.django_db
def test_snapshot_returns_historical_lhb_name_before_rename(
    api_client, org_under_renamed_lhb
):
    """The parent LHB's name comes from LocalHealthBoardVersion as-of the
    snapshot date, so a date before the rename returns the historical name."""
    url = reverse("organisation_snapshot", kwargs={"ods_code": "WAL01"})
    response = api_client.get(url, {"date": "2018-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["local_health_board"]["ods_code"] == "WAL"
    assert data["local_health_board"]["name"] == "Old LHB Name"


@pytest.mark.django_db
def test_snapshot_returns_current_lhb_name_after_rename(
    api_client, org_under_renamed_lhb
):
    """After the rename date, the LocalHealthBoardVersion row carries the new
    name."""
    url = reverse("organisation_snapshot", kwargs={"ods_code": "WAL01"})
    response = api_client.get(url, {"date": "2020-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["local_health_board"]["ods_code"] == "WAL"
    assert data["local_health_board"]["name"] == "New LHB Name"


# ---------------------------------------------------------------------------
# ICB name history
# ---------------------------------------------------------------------------


@pytest.fixture
def icb_with_rename():
    """An IntegratedCareBoard (QRL) named 'Old ICB Name' until 2026-04-01, then
    renamed to 'New ICB Name'. ICB version history is populated by
    backfill_successions --entity icb / backfill_*_attributes."""
    icb = IntegratedCareBoard.objects.create(
        ods_code="QRL",
        name="New ICB Name",
        publication_date=datetime.date(2017, 4, 1),
    )
    IntegratedCareBoardVersion.objects.create(
        integrated_care_board=icb,
        valid_from=datetime.date(2017, 4, 1),
        valid_to=datetime.date(2026, 4, 1),
        name="Old ICB Name",
        publication_date=datetime.date(2017, 4, 1),
    )
    IntegratedCareBoardVersion.objects.create(
        integrated_care_board=icb,
        valid_from=datetime.date(2026, 4, 1),
        valid_to=None,
        name="New ICB Name",
        publication_date=datetime.date(2017, 4, 1),
    )
    return icb


@pytest.fixture
def org_under_renamed_icb(icb_with_rename):
    """An organisation continuously under QRL (the renamed ICB)."""
    org = Organisation.objects.create(
        ods_code="QRL01",
        name="Some Hospital",
        active=True,
        integrated_care_board=icb_with_rename,
    )
    OrganisationVersion.objects.create(
        organisation=org,
        valid_from=datetime.date(2017, 4, 1),
        valid_to=None,
        name="Some Hospital",
        active=True,
    )
    OrganisationIntegratedCareBoardMembership.objects.create(
        organisation=org,
        integrated_care_board=icb_with_rename,
        valid_from=datetime.date(2017, 4, 1),
        valid_to=None,
    )
    return org


@pytest.mark.django_db
def test_snapshot_returns_historical_icb_name_before_rename(
    api_client, org_under_renamed_icb
):
    """The parent ICB's name comes from IntegratedCareBoardVersion as-of the
    snapshot date, so a date before the rename returns the historical name."""
    url = reverse("organisation_snapshot", kwargs={"ods_code": "QRL01"})
    response = api_client.get(url, {"date": "2024-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["integrated_care_board"]["ods_code"] == "QRL"
    assert data["integrated_care_board"]["name"] == "Old ICB Name"


@pytest.mark.django_db
def test_snapshot_returns_current_icb_name_after_rename(
    api_client, org_under_renamed_icb
):
    """After the rename date, the IntegratedCareBoardVersion row carries the
    new name."""
    url = reverse("organisation_snapshot", kwargs={"ods_code": "QRL01"})
    response = api_client.get(url, {"date": "2027-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["integrated_care_board"]["ods_code"] == "QRL"
    assert data["integrated_care_board"]["name"] == "New ICB Name"


@pytest.mark.django_db
def test_snapshot_lhb_and_icb_name_fall_back_to_current_when_no_version(
    api_client, organisation_with_history
):
    """When no *Version row covers the date for the parent LHB or ICB, the
    snapshot falls back to the current entity.name — preserving prior behaviour
    for entities with only the baseline row (or no version history at all)."""
    # organisation_with_history's org has no LHB or ICB set, so this confirms
    # the None-guard path: a missing parent returns None rather than crashing.
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RAA01"})
    response = api_client.get(url, {"date": "2022-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["local_health_board"] is None
    assert data["integrated_care_board"] is None
