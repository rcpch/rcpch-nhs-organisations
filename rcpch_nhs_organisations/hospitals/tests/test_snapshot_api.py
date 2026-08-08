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
from django.contrib.gis.geos import MultiPolygon, Polygon
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
OrganisationSuccession = apps.get_model("hospitals", "OrganisationSuccession")
Trust = apps.get_model("hospitals", "Trust")


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
