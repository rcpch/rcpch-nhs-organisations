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
        bng_e=350000,
        bng_n=400000,
        long=-3.0,
        lat=53.0,
        globalid="globalid1",
        geom=MultiPolygon(
            Polygon(
                (
                    (349900, 400100),
                    (349900, 399900),
                    (350100, 399900),
                    (350100, 400100),
                    (349900, 400100),
                )
            )
        ),
    )
    lad2 = LocalAuthorityDistrict.objects.create(
        lad24cd="LAD002",
        lad24nm="Test District 2",
        lad24nmw="Test District 2 Welsh",
        bng_e=350100,
        bng_n=400100,
        long=-3.0,
        lat=53.0,
        globalid="globalid2",
        geom=MultiPolygon(
            Polygon(
                (
                    (350000, 400200),
                    (350000, 400000),
                    (350200, 400000),
                    (350200, 400200),
                    (350000, 400200),
                )
            )
        ),
    )
    lad3 = LocalAuthorityDistrict.objects.create(
        lad24cd="LAD003",
        lad24nm="Test District 3",
        lad24nmw="Test District 3 Welsh",
        bng_e=350200,
        bng_n=400200,
        long=-3.0,
        lat=53.0,
        globalid="globalid3",
        geom=MultiPolygon(
            Polygon(
                (
                    (350100, 400300),
                    (350100, 400100),
                    (350300, 400100),
                    (350300, 400300),
                    (350100, 400300),
                )
            )
        ),
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
