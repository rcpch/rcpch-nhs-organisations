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
        long=-3.1,
        lat=53.1,
        globalid="globalid2",
        geom=MultiPolygon(Polygon(((0, 0), (1, 1), (1, 0), (0, 0)))),
    )
    return [lad1, lad2]


@pytest.mark.django_db
def test_list_local_authority_districts(api_client, local_authority_districts):
    url = reverse("local_authority_district-list")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2


@pytest.mark.django_db
def test_within_radius(api_client, local_authority_districts):
    url = reverse("local_authority_district-within-radius")
    response = api_client.get(url, {"lat": 53.0, "long": -3.0, "radius": 10000})
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2

    response = api_client.get(url, {"lat": 53.1, "long": -3.1, "radius": 1000})
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2
