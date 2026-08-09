import datetime

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
Country = apps.get_model("hospitals", "Country")
OPENUKNetwork = apps.get_model("hospitals", "OPENUKNetwork")


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
    url = reverse("local_authority_districts-list")
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 3


@pytest.mark.django_db
def test_within_radius(api_client, local_authority_districts):
    url = reverse("local_authority_districts-within-radius")
    response = api_client.get(
        url, {"lat": 53.0, "long": -3.0, "radius": 500000}
    )  # within 500km
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 3

    response = api_client.get(
        url, {"lat": 53.0, "long": -3.0, "radius": 5}
    )  # within 5 km
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 0


@pytest.fixture
def countries():
    Country.objects.all().delete()  # Clear the table
    england = Country.objects.create(
        boundary_identifier="E92000001",
        name="England",
        welsh_name="Lloegr",
        bng_e=394883,
        bng_n=370883,
        long=-2.07811,
        lat=53.235,
        globalid="f6b76559-3626-49b8-b50b-bd15efcb0505",
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
    wales = Country.objects.create(
        boundary_identifier="W92000004",
        name="Wales",
        welsh_name="Cymru",
        bng_e=300000,
        bng_n=300000,
        long=-3.5,
        lat=52.5,
        globalid="a1b2c3d4-0000-0000-0000-000000000000",
        geom=MultiPolygon(
            Polygon(
                (
                    (299900, 300100),
                    (299900, 299900),
                    (300100, 299900),
                    (300100, 300100),
                    (299900, 300100),
                )
            )
        ),
    )
    return [england, wales]


@pytest.mark.django_db
def test_list_countries(api_client, countries):
    url = reverse("country-list")
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2
    # The full payload includes the geometry column.
    assert "geom" in response.data[0]


@pytest.mark.django_db
def test_retrieve_country_by_boundary_identifier(api_client, countries):
    # lookup_field is boundary_identifier, not the PK.
    url = reverse("country-detail", args=["E92000001"])
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["boundary_identifier"] == "E92000001"
    assert response.data["name"] == "England"


@pytest.mark.django_db
def test_retrieve_country_unknown_boundary_identifier_404(api_client, countries):
    url = reverse("country-detail", args=["Z92000099"])
    response = api_client.get(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_countries_fields_query_omits_geom(api_client, countries):
    url = reverse("country-list")
    response = api_client.get(url, {"fields": "boundary_identifier,name"})

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2
    # Only the requested fields are returned.
    assert set(response.data[0].keys()) == {"boundary_identifier", "name"}
    assert "geom" not in response.data[0]


@pytest.mark.django_db
def test_retrieve_country_fields_query_omits_geom(api_client, countries):
    url = reverse("country-detail", args=["E92000001"])
    response = api_client.get(url, {"fields": "boundary_identifier,name"})

    assert response.status_code == status.HTTP_200_OK
    assert set(response.data.keys()) == {"boundary_identifier", "name"}
    assert "geom" not in response.data


@pytest.mark.django_db
def test_list_countries_fields_query_ignores_unknown_fields(api_client, countries):
    # Unknown field names are silently dropped; the valid ones are still returned.
    url = reverse("country-list")
    response = api_client.get(
        url, {"fields": "boundary_identifier,name,does_not_exist"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert set(response.data[0].keys()) == {"boundary_identifier", "name"}


@pytest.fixture
def openuk_networks():
    OPENUKNetwork.objects.all().delete()  # Clear the table
    net1 = OPENUKNetwork.objects.create(
        name="North Thames Paediatric Epilepsy Network",
        boundary_identifier="E38000001",
        country="England",
        publication_date=datetime.date(2023, 4, 1),
    )
    net2 = OPENUKNetwork.objects.create(
        name="South Thames Paediatric Epilepsy Network",
        boundary_identifier="E38000002",
        country="England",
        publication_date=datetime.date(2023, 4, 1),
    )
    return [net1, net2]


@pytest.mark.django_db
def test_list_openuk_networks(api_client, openuk_networks):
    url = reverse("openuk_network-list")
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2


@pytest.mark.django_db
def test_retrieve_openuk_network_by_boundary_identifier(api_client, openuk_networks):
    # lookup_field is boundary_identifier, not the PK.
    url = reverse("openuk_network-detail", args=["E38000001"])
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["boundary_identifier"] == "E38000001"
    assert response.data["name"] == "North Thames Paediatric Epilepsy Network"


@pytest.mark.django_db
def test_retrieve_openuk_network_unknown_boundary_identifier_404(
    api_client, openuk_networks
):
    url = reverse("openuk_network-detail", args=["E99999999"])
    response = api_client.get(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_filter_openuk_networks_by_country(api_client, openuk_networks):
    url = reverse("openuk_network-list")
    response = api_client.get(url, {"country": "England"})

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2


@pytest.mark.django_db
def test_filter_openuk_networks_by_boundary_identifier(
    api_client, openuk_networks
):
    url = reverse("openuk_network-list")
    response = api_client.get(url, {"boundary_identifier": "E38000002"})

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["boundary_identifier"] == "E38000002"
