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
    assert data["predecessor_ods_code"] is None
    assert data["successor_ods_code"] == "RJZ30"
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


@pytest.mark.django_db
def test_snapshot_walks_parallel_code_to_predecessor(api_client, trust_a, trust_b):
    """For a parallel code (successor pre-existed, predecessor was the live
    audit code before the succession date), querying the successor at a date
    before the succession date walks to the predecessor.

    Mirrors the North Middlesex scenario: RAPNM (under RAP) → RAL27 (under
    RAL), succession_date 2024-12-31. Both codes were open at 2020, but RAPNM
    was the live audit code until it closed. Querying RAL27 at 2020 should
    return RAPNM under RAP.
    """
    rapnm = Organisation.objects.create(
        ods_code="RAPNM",
        name="North Middlesex Hospital",
        address1="Sterling Way",
        active=True,
        trust=trust_a,  # RAP
    )
    ral27 = Organisation.objects.create(
        ods_code="RAL27",
        name="North Middlesex Hospital",
        address1="Sterling Way",
        active=True,
        trust=trust_b,  # RAL
    )
    # RAPNM: open since 1991, closed 2024-12-31
    OrganisationVersion.objects.create(
        organisation=rapnm,
        valid_from=datetime.date(2020, 12, 1),  # floor
        valid_to=datetime.date(2024, 12, 31),
        name="North Middlesex Hospital",
        address1="Sterling Way",
        active=True,
    )
    # RAL27: open since 2003
    OrganisationVersion.objects.create(
        organisation=ral27,
        valid_from=datetime.date(2020, 12, 1),  # floor
        valid_to=None,
        name="North Middlesex Hospital",
        address1="Sterling Way",
        active=True,
    )
    OrganisationTrustMembership.objects.create(
        organisation=rapnm,
        trust=trust_a,  # RAP
        valid_from=datetime.date(2020, 12, 1),
        valid_to=datetime.date(2024, 12, 31),
    )
    OrganisationTrustMembership.objects.create(
        organisation=ral27,
        trust=trust_b,  # RAL
        valid_from=datetime.date(2020, 12, 1),
        valid_to=None,
    )
    OrganisationSuccession.objects.create(
        predecessor=rapnm,
        successor=ral27,
        succession_date=datetime.date(2024, 12, 31),
        succession_type="code_change",
    )

    # Query the successor (RAL27) at 2020 — before the succession date.
    # Should walk to RAPNM (the live audit code at that date).
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RAL27"})
    response = api_client.get(url, {"date": "2020-12-30"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RAPNM"
    assert data["predecessor_ods_code"] is None
    assert data["successor_ods_code"] == "RAL27"
    assert data["trust"]["ods_code"] == "RAA"  # RAP

    # Query the successor (RAL27) after the succession date — should
    # return RAL27 directly.
    response = api_client.get(url, {"date": "2025-06-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RAL27"
    assert data["predecessor_ods_code"] == "RAPNM"
    assert data["successor_ods_code"] is None
    assert data["trust"]["ods_code"] == "RBB"  # RAL


@pytest.mark.django_db
def test_snapshot_walks_forward_to_successor(api_client, trust_a, trust_b):
    """If the queried predecessor's history ended before on_date but a
    successor exists, the walk goes forward to the successor.

    Mirrors the Ormskirk scenario: RVY02 (under RVY) → RBN52 (under RBN),
    succession_date 2023-07-01. Querying RVY02 at any date after 2023-07-01
    should walk forward to RBN52.
    """
    rvy02 = Organisation.objects.create(
        ods_code="RVY02",
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=True,
        trust=trust_a,  # RVY
    )
    rbn52 = Organisation.objects.create(
        ods_code="RBN52",
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=True,
        trust=trust_b,  # RBN
    )
    # RVY02: open from the floor, closed on the succession date.
    OrganisationVersion.objects.create(
        organisation=rvy02,
        valid_from=datetime.date(2020, 12, 1),
        valid_to=datetime.date(2023, 7, 1),
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=True,
    )
    # RBN52: open from the succession date.
    OrganisationVersion.objects.create(
        organisation=rbn52,
        valid_from=datetime.date(2023, 7, 1),
        valid_to=None,
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=True,
    )
    OrganisationTrustMembership.objects.create(
        organisation=rvy02,
        trust=trust_a,
        valid_from=datetime.date(2020, 12, 1),
        valid_to=datetime.date(2023, 7, 1),
    )
    OrganisationTrustMembership.objects.create(
        organisation=rbn52,
        trust=trust_b,
        valid_from=datetime.date(2023, 7, 1),
        valid_to=None,
    )
    OrganisationSuccession.objects.create(
        predecessor=rvy02,
        successor=rbn52,
        succession_date=datetime.date(2023, 7, 1),
        succession_type="code_change",
    )

    # Query the predecessor (RVY02) at a date after the succession — should
    # walk forward to RBN52.
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RVY02"})
    response = api_client.get(url, {"date": "2024-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RBN52"
    assert data["predecessor_ods_code"] == "RVY02"
    assert data["successor_ods_code"] is None
    assert data["trust"]["ods_code"] == "RBB"  # RBN

    # Query the predecessor (RVY02) at today — should also walk forward.
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RBN52"
    assert data["predecessor_ods_code"] == "RVY02"
    assert data["successor_ods_code"] is None

    # Query the predecessor (RVY02) at a date before the succession — should
    # return RVY02 directly (no walk).
    response = api_client.get(url, {"date": "2022-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RVY02"
    assert data["predecessor_ods_code"] is None
    assert data["successor_ods_code"] == "RBN52"
    assert data["trust"]["ods_code"] == "RAA"  # RVY

    # Query the successor (RBN52) at today — should return RBN52 directly.
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RBN52"})
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RBN52"
    assert data["predecessor_ods_code"] == "RVY02"
    assert data["successor_ods_code"] is None


@pytest.mark.django_db
def test_snapshot_forward_walk_404_on_split(api_client, trust_a, trust_b):
    """If the queried predecessor was split into multiple successors, the
    forward walk is ambiguous and returns 404.

    Mirrors a trust-level split (e.g. South London Healthcare RYQ → RJZ +
    RJ2) applied at organisation level: one predecessor, two successors.
    The model does not enforce 1→1 for organisations, so this is a
    defensive test.
    """
    pred = Organisation.objects.create(
        ods_code="RPRED",
        name="Predecessor Hospital",
        address1="Old Address",
        active=True,
        trust=trust_a,
    )
    succ1 = Organisation.objects.create(
        ods_code="RSUC1",
        name="Successor One",
        address1="New Address 1",
        active=True,
        trust=trust_b,
    )
    succ2 = Organisation.objects.create(
        ods_code="RSUC2",
        name="Successor Two",
        address1="New Address 2",
        active=True,
        trust=trust_b,
    )
    OrganisationVersion.objects.create(
        organisation=pred,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=datetime.date(2023, 1, 1),
        name="Predecessor Hospital",
        address1="Old Address",
        active=True,
    )
    OrganisationVersion.objects.create(
        organisation=succ1,
        valid_from=datetime.date(2023, 1, 1),
        valid_to=None,
        name="Successor One",
        address1="New Address 1",
        active=True,
    )
    OrganisationVersion.objects.create(
        organisation=succ2,
        valid_from=datetime.date(2023, 1, 1),
        valid_to=None,
        name="Successor Two",
        address1="New Address 2",
        active=True,
    )
    OrganisationSuccession.objects.create(
        predecessor=pred,
        successor=succ1,
        succession_date=datetime.date(2023, 1, 1),
        succession_type="split",
    )
    OrganisationSuccession.objects.create(
        predecessor=pred,
        successor=succ2,
        succession_date=datetime.date(2023, 1, 1),
        succession_type="split",
    )

    # Query the predecessor after the split date — ambiguous, should 404.
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RPRED"})
    response = api_client.get(url, {"date": "2024-01-01"})
    assert response.status_code == status.HTTP_404_NOT_FOUND

    # Query the predecessor before the split date — should return pred directly.
    response = api_client.get(url, {"date": "2021-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RPRED"
    assert data["predecessor_ods_code"] is None
    # Two successors → scalar is null (use the detail endpoint's array).
    assert data["successor_ods_code"] is None


@pytest.mark.django_db
def test_snapshot_schema_documents_chain_fields_and_walk_examples(api_client):
    """The OpenAPI schema for the snapshot endpoint must document the
    `predecessor_ods_code` and `successor_ods_code` fields and the three
    walk examples (no walk, backward walk, forward walk).

    Guards against accidental removal of the @extend_schema examples that
    help consumers discover the succession-walk behaviour.
    """
    response = api_client.get("/schema/")
    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    op = schema["paths"]["/organisations/{ods_code}/snapshot/"]["get"]
    resp200 = op["responses"]["200"]

    # The description mentions both chain fields.
    description = resp200.get("description", "")
    assert "predecessor_ods_code" in description
    assert "successor_ods_code" in description

    # drf-spectacular emits examples under content/application/json/examples
    # when OpenApiExample is used on an OpenApiResponse.
    examples = (
        resp200.get("content", {})
        .get("application/json", {})
        .get("examples", {})
    )
    assert examples, (
        "expected the snapshot 200 response to expose the three walk examples"
    )

    # The three walk cases are present (keyed by the OpenApiExample name,
    # sanitized by drf-spectacular — spaces removed, punctuation kept).
    example_keys = set(examples.keys())
    assert any("NoWalk" in k for k in example_keys), (
        f"missing 'No walk' example; got {example_keys}"
    )
    assert any("BackwardWalk" in k for k in example_keys), (
        f"missing 'Backward walk' example; got {example_keys}"
    )
    assert any("ForwardWalk" in k for k in example_keys), (
        f"missing 'Forward walk' example; got {example_keys}"
    )

    # Each example value carries both chain fields.
    for name, example in examples.items():
        value = example.get("value", {})
        assert "predecessor_ods_code" in value, (
            f"example {name!r} missing predecessor_ods_code"
        )
        assert "successor_ods_code" in value, (
            f"example {name!r} missing successor_ods_code"
        )

    # The 404 description mentions the split case (ambiguous forward walk).
    resp404 = op["responses"]["404"]
    assert "split" in resp404.get("description", "")


@pytest.mark.django_db
def test_snapshot_forward_walk_fires_for_inactive_predecessor(
    api_client, trust_a, trust_b
):
    """An inactive predecessor with an open-ended baseline version (e.g.
    created by `mergers --create`) must still walk forward to its successor
    when queried at today.

    Regression test for the RVY02/RBN52 deployment issue: `mergers --create
    RVY02` created a baseline OrganisationVersion with valid_from=today,
    valid_to=None, active=False. The old code checked only whether a version
    row covered on_date, not whether it was active — so the forward walk
    never fired and the snapshot returned RVY02 with null relationships.
    """
    rvy02 = Organisation.objects.create(
        ods_code="RVY02",
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=False,  # inactive — succeeded by RBN52
        trust=trust_a,
    )
    rbn52 = Organisation.objects.create(
        ods_code="RBN52",
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=True,
        trust=trust_b,
    )
    # RVY02: open-ended baseline version (as created by mergers --create).
    # active=False — the entity is no longer live.
    OrganisationVersion.objects.create(
        organisation=rvy02,
        valid_from=datetime.date(2020, 12, 1),
        valid_to=None,  # open-ended — covers today
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=False,
    )
    # RBN52: open since the succession date.
    OrganisationVersion.objects.create(
        organisation=rbn52,
        valid_from=datetime.date(2023, 7, 1),
        valid_to=None,
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=True,
    )
    OrganisationTrustMembership.objects.create(
        organisation=rbn52,
        trust=trust_b,
        valid_from=datetime.date(2023, 7, 1),
        valid_to=None,
    )
    OrganisationSuccession.objects.create(
        predecessor=rvy02,
        successor=rbn52,
        succession_date=datetime.date(2023, 7, 1),
        succession_type="code_change",
    )

    # Query the inactive predecessor at today — should walk forward to
    # RBN52 despite the open-ended version covering today.
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RVY02"})
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RBN52"
    assert data["predecessor_ods_code"] == "RVY02"
    assert data["successor_ods_code"] is None
    assert data["trust"]["ods_code"] == "RBB"  # RBN

    # Query the successor at today — should return RBN52 with predecessor.
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RBN52"})
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RBN52"
    assert data["predecessor_ods_code"] == "RVY02"
    assert data["successor_ods_code"] is None


@pytest.mark.django_db
def test_snapshot_duplicate_succession_rows_treated_as_one(
    api_client, trust_a, trust_b
):
    """Duplicate OrganisationSuccession rows to the same successor (e.g.
    from re-running the backfill with different effective dates) must be
    treated as one successor — the scalar fields populate and the forward
    walk fires.

    Regression test for the RVY02/RBN52 deployment issue: two
    OrganisationSuccession rows linked RVY02 → RBN52 with different dates
    (2023-06-30 and 2023-07-01). The old code used count() == 1, which
    failed because count() was 2, so predecessor_ods_code and
    successor_ods_code were null and the forward walk didn't fire.
    """
    rvy02 = Organisation.objects.create(
        ods_code="RVY02",
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=False,
        trust=trust_a,
    )
    rbn52 = Organisation.objects.create(
        ods_code="RBN52",
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=True,
        trust=trust_b,
    )
    OrganisationVersion.objects.create(
        organisation=rvy02,
        valid_from=datetime.date(2020, 12, 1),
        valid_to=datetime.date(2023, 7, 1),
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=True,
    )
    OrganisationVersion.objects.create(
        organisation=rbn52,
        valid_from=datetime.date(2023, 7, 1),
        valid_to=None,
        name="Ormskirk and District General Hospital",
        address1="Wigan Road",
        active=True,
    )
    OrganisationTrustMembership.objects.create(
        organisation=rbn52,
        trust=trust_b,
        valid_from=datetime.date(2023, 7, 1),
        valid_to=None,
    )
    # Two succession rows to the SAME successor with different dates.
    OrganisationSuccession.objects.create(
        predecessor=rvy02,
        successor=rbn52,
        succession_date=datetime.date(2023, 6, 30),
        succession_type="code_change",
    )
    OrganisationSuccession.objects.create(
        predecessor=rvy02,
        successor=rbn52,
        succession_date=datetime.date(2023, 7, 1),
        succession_type="code_change",
    )

    # Successor at today — predecessor_ods_code should populate despite
    # two rows (both point to the same predecessor).
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RBN52"})
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RBN52"
    assert data["predecessor_ods_code"] == "RVY02"
    assert data["successor_ods_code"] is None

    # Predecessor before the succession — successor_ods_code should populate.
    url = reverse("organisation_snapshot", kwargs={"ods_code": "RVY02"})
    response = api_client.get(url, {"date": "2022-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RVY02"
    assert data["predecessor_ods_code"] is None
    assert data["successor_ods_code"] == "RBN52"

    # Predecessor after the succession — should walk forward to RBN52
    # despite two rows (both point to the same successor).
    response = api_client.get(url, {"date": "2024-01-01"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RBN52"
    assert data["predecessor_ods_code"] == "RVY02"
    assert data["successor_ods_code"] is None


@pytest.mark.django_db
def test_snapshot_closure_returns_inactive_entity_not_404(
    api_client, trust_a
):
    """A closed entity (active=False, no successor) queried after its
    closure date should return its final state, not 404.

    The forward walk finds no successor (it's a closure), so the entity
    itself is returned with its inactive state.
    """
    closed = Organisation.objects.create(
        ods_code="RCLOS",
        name="Closed Hospital",
        address1="Old Address",
        active=False,
        trust=trust_a,
    )
    OrganisationVersion.objects.create(
        organisation=closed,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,  # open-ended, active=False
        name="Closed Hospital",
        address1="Old Address",
        active=False,
    )
    OrganisationTrustMembership.objects.create(
        organisation=closed,
        trust=trust_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )
    # No OrganisationSuccession row — this is a closure with no successor.

    url = reverse("organisation_snapshot", kwargs={"ods_code": "RCLOS"})
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RCLOS"
    assert data["active"] is False
    assert data["predecessor_ods_code"] is None
    assert data["successor_ods_code"] is None
