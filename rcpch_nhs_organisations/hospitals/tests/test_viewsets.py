import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.apps import apps


@pytest.fixture
def api_client():
    return APIClient()


LocalAuthorityDistrict = apps.get_model("hospitals", "LocalAuthorityDistrict")


@pytest.fixture
def local_authority_districts():
    LocalAuthorityDistrict.objects.all().delete()  # Clear the table
    lad1 = LocalAuthorityDistrict.objects.create(
        lad24cd="LAD001",
        lad24nm="Test District 1",
        lad24nmw="Test District 1 Welsh",
        bng_e=123456,
        bng_n=654321,
        long=-3.0,
        lat=53.0,
        globalid="globalid1",
        geom=MultiPolygon(Polygon(((0, 0), (1, 1), (1, 0), (0, 0)))),
    )
    lad2 = LocalAuthorityDistrict.objects.create(
        lad24cd="LAD002",
        lad24nm="Test District 2",
        lad24nmw="Test District 2 Welsh",
        bng_e=123457,
        bng_n=654322,
        long=-2.0,
        lat=52,
        globalid="globalid2",
        geom=MultiPolygon(Polygon(((0, 0), (1, 1), (1, 0), (0, 0)))),
    )
    lad3 = LocalAuthorityDistrict.objects.create(
        lad24cd="LAD003",
        lad24nm="Test District 3",
        lad24nmw="Test District 3 Welsh",
        bng_e=123458,
        bng_n=654323,
        long=-1.0,
        lat=54,
        globalid="globalid3",
        geom=MultiPolygon(Polygon(((0, 0), (1, 1), (1, 0), (0, 0)))),
    )
    return [lad1, lad2, lad3]


@pytest.mark.django_db
def test_list_local_authority_districts(api_client, local_authority_districts):
    url = reverse("local_authority_district-list")
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["features"]) == 3


@pytest.mark.django_db
def test_within_radius(api_client, local_authority_districts):
    url = reverse("local_authority_district-within-radius")
    response = api_client.get(
        url, {"lat": 53.0, "long": -3.0, "radius": 500000}
    )  # within 500km
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["features"]) == 3

    response = api_client.get(
        url, {"lat": 53.0, "long": -3.0, "radius": 5}
    )  # within 5 km
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["features"]) == 1
