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
Trust = apps.get_model("hospitals", "Trust")
Organisation = apps.get_model("hospitals", "Organisation")
PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")


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


@pytest.mark.django_db
def test_jersey_boundary_identifier_is_JEY(api_client):
    """
    Jersey is a Crown Dependency, not part of the UK, so its boundary
    identifier is JEY (the GADM GID_0 value and ISO 3166-1 alpha-3 code) —
    NOT an E-prefixed GSS code. E92000003 is the North East region of
    England and was erroneously assigned to Jersey by migration 0010.
    """
    Country.objects.all().delete()
    Country.objects.create(
        boundary_identifier="JEY",
        name="Jersey",
        welsh_name="",
        bng_e=394883,
        bng_n=370883,
        long=-2.07811,
        lat=53.235,
        globalid="jersey-globalid",
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

    # The detail endpoint must retrieve Jersey by JEY, not by E92000003.
    url = reverse("country-detail", args=["JEY"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["boundary_identifier"] == "JEY"
    assert response.data["name"] == "Jersey"

    # The old, erroneous code must no longer resolve.
    old_url = reverse("country-detail", args=["E92000003"])
    old_response = api_client.get(old_url)
    assert old_response.status_code == status.HTTP_404_NOT_FOUND


def test_jersey_constant_uses_JEY():
    """Guard against the Jersey boundary identifier constant regressing
    to the erroneous E92000003 value."""
    from rcpch_nhs_organisations.hospitals.constants.country_codes import (
        COUNTRY_CODES,
    )

    jersey = next(c for c in COUNTRY_CODES if c["country_ons_name"] == "Jersey")
    assert jersey["country_ons_code"] == "JEY"


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


# ---------------------------------------------------------------------------
# /paediatric_diabetes_units/{pz_code}/parent/ endpoint
#
# The `parent` field must be derived from the PDU's lead_organisation, not
# from an arbitrary .first() child organisation. A PDU's child organisations
# can span multiple trusts after a split (e.g. PZ247 has sites under both R0A
# Manchester University and RM3 Northern Care Alliance); picking the first
# child in default ordering returned whichever happened to sort first, which
# was wrong. The lead_organisation FK is the source of truth.
# ---------------------------------------------------------------------------


@pytest.fixture
def england_country():
    Country.objects.all().delete()
    return Country.objects.create(
        boundary_identifier="E92000001",
        name="England",
        welsh_name="Lloegr",
        bng_e=394883,
        bng_n=370883,
        long=-2.07811,
        lat=53.235,
        globalid="england-test-globalid",
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


@pytest.fixture
def split_pdu_with_two_trusts(england_country):
    """A PDU with two child organisations under different trusts, mirroring
    the PZ247 scenario: North Manchester General (R0A66, trust R0A Manchester
    University) and Trafford General (RM321, trust RM3 Northern Care Alliance).

    The PDU's lead_organisation is set to the R0A66 site. The `parent` endpoint
    must return R0A (Manchester University), not RM3 (Northern Care Alliance).
    """
    Trust.objects.all().delete()
    Organisation.objects.all().delete()
    PaediatricDiabetesUnit.objects.all().delete()

    trust_r0a = Trust.objects.create(ods_code="R0A", name="MANCHESTER UNIVERSITY NHS FOUNDATION TRUST")
    trust_rm3 = Trust.objects.create(ods_code="RM3", name="NORTHERN CARE ALLIANCE NHS FOUNDATION TRUST")

    # Create Trafford General first so that a .first() query would return it —
    # this is the regression condition. If the serializer uses .first() it will
    # pick RM321 and return Northern Care Alliance; if it uses lead_organisation
    # it will return R0A66's trust (Manchester University).
    trafford = Organisation.objects.create(
        ods_code="RM321",
        name="TRAFFORD GENERAL HOSPITAL",
        trust=trust_rm3,
        country=england_country,
    )
    north_manchester = Organisation.objects.create(
        ods_code="R0A66",
        name="NORTH MANCHESTER GENERAL HOSPITAL",
        trust=trust_r0a,
        country=england_country,
    )

    pdu = PaediatricDiabetesUnit.objects.create(
        pz_code="PZ247",
        active=True,
        lead_organisation=north_manchester,
    )
    # Attach both organisations to the PDU. The FK on Organisation is the
    # current-state link; the temporal membership table is not needed for this
    # test because the serializer reads the current-state FK.
    trafford.paediatric_diabetes_unit = pdu
    trafford.save(update_fields=["paediatric_diabetes_unit"])
    north_manchester.paediatric_diabetes_unit = pdu
    north_manchester.save(update_fields=["paediatric_diabetes_unit"])

    return {
        "pdu": pdu,
        "lead_org": north_manchester,
        "lead_trust": trust_r0a,
        "other_org": trafford,
        "other_trust": trust_rm3,
    }


@pytest.mark.django_db
def test_pdu_parent_returns_lead_organisation_trust(api_client, split_pdu_with_two_trusts):
    """The /parent/ endpoint must return the trust of the PDU's
    lead_organisation, not the trust of an arbitrary .first() child.

    Regression test for PZ247: the PDU has two child organisations under
    different trusts (R0A Manchester University and RM3 Northern Care
    Alliance). The lead_organisation is North Manchester General (R0A66),
    so the parent must be Manchester University (R0A).
    """
    url = reverse("paediatric_diabetes_unit-parent", args=["PZ247"])
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    parent = response.data["parent"]
    assert parent["ods_code"] == "R0A"
    assert parent["name"] == "MANCHESTER UNIVERSITY NHS FOUNDATION TRUST"
    # Sanity check: the primary_organisation field must agree with the parent.
    primary = response.data["primary_organisation"]
    assert primary["ods_code"] == "R0A66"
    assert primary["name"] == "NORTH MANCHESTER GENERAL HOSPITAL"


@pytest.mark.django_db
def test_pdu_parent_returns_null_when_lead_unset_and_multiple_children(
    api_client, split_pdu_with_two_trusts
):
    """When lead_organisation is NULL and the PDU has multiple child
    organisations under different trusts, the parent must be null rather than
    an arbitrary .first() child's trust. The API surfaces the gap instead of
    hiding it.
    """
    pdu = split_pdu_with_two_trusts["pdu"]
    pdu.lead_organisation = None
    pdu.save(update_fields=["lead_organisation"])

    url = reverse("paediatric_diabetes_unit-parent", args=["PZ247"])
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["parent"] is None
    assert response.data["primary_organisation"] is None


# ---------------------------------------------------------------------------
# Trust detail endpoint — predecessors / successors chain arrays
# ---------------------------------------------------------------------------

TrustSuccession = apps.get_model("hospitals", "TrustSuccession")


@pytest.fixture
def trust_chain():
    """Build a small trust succession graph covering the four cases:

      RVL → RAL  (acquisition, 1→1)
      RGQ → RJL  (full merger, 2→1)
      RDE → RJL  (full merger, 2→1)
      RYQ → RJZ  (split, 1→2)
      RYQ → RJ2  (split, 1→2)
      ROLD → None (closure, 1→0)
    """
    rvl = Trust.objects.create(ods_code="RVL", name="BARNET AND CHASE FARM HOSPITALS NHS TRUST")
    ral = Trust.objects.create(ods_code="RAL", name="ROYAL FREE LONDON NHS FOUNDATION TRUST")
    rgq = Trust.objects.create(ods_code="RGQ", name="IPSWICH HOSPITAL NHS TRUST")
    rde = Trust.objects.create(ods_code="RDE", name="COLCHESTER UNIVERSITY HOSPITALS NHS FOUNDATION TRUST")
    rjl = Trust.objects.create(ods_code="RJL", name="EAST SUFFOLK AND NORTH ESSEX NHS FOUNDATION TRUST")
    ryq = Trust.objects.create(ods_code="RYQ", name="SOUTH LONDON HEALTHCARE NHS TRUST")
    rjz = Trust.objects.create(ods_code="RJZ", name="KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST")
    rj2 = Trust.objects.create(ods_code="RJ2", name="LEWISHAM AND GREENWICH NHS TRUST")
    rold = Trust.objects.create(ods_code="ROLD", name="CLOSED TRUST")

    TrustSuccession.objects.create(
        predecessor=rvl, successor=ral,
        succession_date=datetime.date(2014, 1, 1), succession_type="acquisition",
    )
    TrustSuccession.objects.create(
        predecessor=rgq, successor=rjl,
        succession_date=datetime.date(2018, 1, 1), succession_type="merger",
    )
    TrustSuccession.objects.create(
        predecessor=rde, successor=rjl,
        succession_date=datetime.date(2018, 1, 1), succession_type="merger",
    )
    TrustSuccession.objects.create(
        predecessor=ryq, successor=rjz,
        succession_date=datetime.date(2013, 1, 1), succession_type="split",
    )
    TrustSuccession.objects.create(
        predecessor=ryq, successor=rj2,
        succession_date=datetime.date(2013, 1, 1), succession_type="split",
    )
    TrustSuccession.objects.create(
        predecessor=rold, successor=None,
        succession_date=datetime.date(2020, 1, 1), succession_type="closure",
    )
    return {
        "rvl": rvl, "ral": ral, "rgq": rgq, "rde": rde, "rjl": rjl,
        "ryq": ryq, "rjz": rjz, "rj2": rj2, "rold": rold,
    }


@pytest.mark.django_db
def test_trust_detail_returns_predecessors_and_successors_arrays(api_client, trust_chain):
    """The trust detail endpoint must return `predecessors` and `successors`
    arrays populated from TrustSuccession, ordered by succession_date.
    """
    # RAL has one predecessor (RVL, acquisition).
    url = reverse("trusts-detail", args=["RAL"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RAL"
    assert data["predecessors"] == [
        {
            "ods_code": "RVL",
            "name": "BARNET AND CHASE FARM HOSPITALS NHS TRUST",
            "succession_date": "2014-01-01",
            "succession_type": "acquisition",
        }
    ]
    assert data["successors"] == []

    # RVL has one successor (RAL, acquisition).
    url = reverse("trusts-detail", args=["RVL"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RVL"
    assert data["predecessors"] == []
    assert data["successors"] == [
        {
            "ods_code": "RAL",
            "name": "ROYAL FREE LONDON NHS FOUNDATION TRUST",
            "succession_date": "2014-01-01",
            "succession_type": "acquisition",
        }
    ]


@pytest.mark.django_db
def test_trust_detail_full_merger_lists_two_predecessors(api_client, trust_chain):
    """A full merger (2→1) — the successor lists both predecessors, each
    predecessor lists the successor. RGQ + RDE → RJL.
    """
    url = reverse("trusts-detail", args=["RJL"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RJL"
    assert len(data["predecessors"]) == 2
    pred_codes = {p["ods_code"] for p in data["predecessors"]}
    assert pred_codes == {"RGQ", "RDE"}
    for p in data["predecessors"]:
        assert p["succession_date"] == "2018-01-01"
        assert p["succession_type"] == "merger"
    assert data["successors"] == []

    # Each predecessor sees RJL as its successor.
    for code in ("RGQ", "RDE"):
        url = reverse("trusts-detail", args=[code])
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["successors"]) == 1
        assert data["successors"][0]["ods_code"] == "RJL"
        assert data["successors"][0]["succession_type"] == "merger"


@pytest.mark.django_db
def test_trust_detail_split_lists_two_successors(api_client, trust_chain):
    """A split (1→2) — the predecessor lists both successors, each successor
    lists the predecessor. RYQ → RJZ + RJ2.
    """
    url = reverse("trusts-detail", args=["RYQ"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RYQ"
    assert data["predecessors"] == []
    assert len(data["successors"]) == 2
    succ_codes = {s["ods_code"] for s in data["successors"]}
    assert succ_codes == {"RJZ", "RJ2"}
    for s in data["successors"]:
        assert s["succession_date"] == "2013-01-01"
        assert s["succession_type"] == "split"

    # Each successor sees RYQ as its predecessor.
    for code in ("RJZ", "RJ2"):
        url = reverse("trusts-detail", args=[code])
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["predecessors"]) == 1
        assert data["predecessors"][0]["ods_code"] == "RYQ"
        assert data["predecessors"][0]["succession_type"] == "split"


@pytest.mark.django_db
def test_trust_detail_closure_returns_empty_successors(api_client, trust_chain):
    """A closure (1→0) — the predecessor has no successor. The `successors`
    array is empty (closures have successor=None, which is excluded).
    """
    url = reverse("trusts-detail", args=["ROLD"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "ROLD"
    assert data["predecessors"] == []
    assert data["successors"] == []


@pytest.mark.django_db
def test_trust_detail_no_succession_returns_empty_arrays(api_client):
    """A trust with no succession links returns empty arrays for both fields."""
    Trust.objects.create(ods_code="RSTA", name="STANDALONE TRUST")
    url = reverse("trusts-detail", args=["RSTA"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["predecessors"] == []
    assert data["successors"] == []


# ---------------------------------------------------------------------------
# Organisation / ICB / PDU / LHB detail endpoints — predecessors / successors
# ---------------------------------------------------------------------------

OrganisationSuccession = apps.get_model("hospitals", "OrganisationSuccession")
IntegratedCareBoard = apps.get_model("hospitals", "IntegratedCareBoard")
IntegratedCareBoardSuccession = apps.get_model(
    "hospitals", "IntegratedCareBoardSuccession"
)
LocalHealthBoard = apps.get_model("hospitals", "LocalHealthBoard")
PaediatricDiabetesUnitSuccession = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitSuccession"
)


@pytest.fixture
def trust_pair():
    """Two standalone trusts for the organisation succession fixture."""
    return (
        Trust.objects.create(ods_code="RAA", name="Trust A"),
        Trust.objects.create(ods_code="RBB", name="Trust B"),
    )


@pytest.fixture
def organisation_chain(trust_pair):
    """Organisation succession: RVY02 → RBN52 (code_change, 1→1)."""
    trust_a, trust_b = trust_pair
    rvy02 = Organisation.objects.create(
        ods_code="RVY02", name="ORMSKIRK HOSPITAL", trust=trust_a,
    )
    rbn52 = Organisation.objects.create(
        ods_code="RBN52", name="ORMSKIRK HOSPITAL", trust=trust_b,
    )
    OrganisationSuccession.objects.create(
        predecessor=rvy02, successor=rbn52,
        succession_date=datetime.date(2023, 7, 1),
        succession_type="code_change",
    )
    return {"rvy02": rvy02, "rbn52": rbn52}


@pytest.mark.django_db
def test_organisation_detail_returns_predecessors_and_successors(
    api_client, organisation_chain
):
    """The organisation detail endpoint returns predecessors / successors
    arrays populated from OrganisationSuccession."""
    # Successor (RBN52) sees its predecessor.
    url = reverse("organisation-detail", args=["RBN52"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RBN52"
    assert data["predecessors"] == [
        {
            "ods_code": "RVY02",
            "name": "ORMSKIRK HOSPITAL",
            "succession_date": "2023-07-01",
            "succession_type": "code_change",
        }
    ]
    assert data["successors"] == []

    # Predecessor (RVY02) sees its successor.
    url = reverse("organisation-detail", args=["RVY02"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "RVY02"
    assert data["predecessors"] == []
    assert data["successors"] == [
        {
            "ods_code": "RBN52",
            "name": "ORMSKIRK HOSPITAL",
            "succession_date": "2023-07-01",
            "succession_type": "code_change",
        }
    ]


@pytest.fixture
def icb_chain():
    """ICB succession: QOLD → QNEW (merger, 1→1)."""
    qold = IntegratedCareBoard.objects.create(
        ods_code="QOLD", name="OLD ICB",
    )
    qnew = IntegratedCareBoard.objects.create(
        ods_code="QNEW", name="NEW ICB",
    )
    IntegratedCareBoardSuccession.objects.create(
        predecessor=qold, successor=qnew,
        succession_date=datetime.date(2026, 4, 1),
        succession_type="merger",
    )
    return {"qold": qold, "qnew": qnew}


@pytest.mark.django_db
def test_icb_detail_returns_predecessors_and_successors(api_client, icb_chain):
    """The ICB detail endpoint returns predecessors / successors arrays
    populated from IntegratedCareBoardSuccession."""
    url = reverse("integrated_care_board-detail", args=["QNEW"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "QNEW"
    assert data["predecessors"] == [
        {
            "ods_code": "QOLD",
            "name": "OLD ICB",
            "succession_date": "2026-04-01",
            "succession_type": "merger",
        }
    ]
    assert data["successors"] == []

    url = reverse("integrated_care_board-detail", args=["QOLD"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "QOLD"
    assert data["predecessors"] == []
    assert data["successors"] == [
        {
            "ods_code": "QNEW",
            "name": "NEW ICB",
            "succession_date": "2026-04-01",
            "succession_type": "merger",
        }
    ]


@pytest.fixture
def pdu_chain():
    """PDU succession: PZ001 → PZ002 (merger, 1→1). Uses pz_code as the
    identifier field. `name` is a property on PaediatricDiabetesUnit, so
    `unit_name` is set instead.
    """
    pz001 = PaediatricDiabetesUnit.objects.create(pz_code="PZ001", unit_name="Old PDU")
    pz002 = PaediatricDiabetesUnit.objects.create(pz_code="PZ002", unit_name="New PDU")
    PaediatricDiabetesUnitSuccession.objects.create(
        predecessor=pz001, successor=pz002,
        succession_date=datetime.date(2026, 1, 1),
        succession_type="merger",
    )
    return {"pz001": pz001, "pz002": pz002}


@pytest.mark.django_db
def test_pdu_detail_returns_predecessors_and_successors(api_client, pdu_chain):
    """The PDU detail endpoint returns predecessors / successors arrays
    populated from PaediatricDiabetesUnitSuccession. The identifier field
    is pz_code (not ods_code) but the JSON key is still `ods_code` for API
    consistency."""
    url = reverse("paediatric_diabetes_unit-detail", args=["PZ002"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["pz_code"] == "PZ002"
    assert data["predecessors"] == [
        {
            "ods_code": "PZ001",
            "name": "Old PDU",
            "succession_date": "2026-01-01",
            "succession_type": "merger",
        }
    ]
    assert data["successors"] == []

    url = reverse("paediatric_diabetes_unit-detail", args=["PZ001"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["pz_code"] == "PZ001"
    assert data["predecessors"] == []
    assert data["successors"] == [
        {
            "ods_code": "PZ002",
            "name": "New PDU",
            "succession_date": "2026-01-01",
            "succession_type": "merger",
        }
    ]


@pytest.fixture
def lhb_standalone():
    """A Local Health Board. LHBs have no succession table, so the chain
    arrays must always be empty."""
    return LocalHealthBoard.objects.create(
        ods_code="7A4",
        name="Betsi Cadwaladr University Local Health Board",
        welsh_name="Bwrdd Iechyd Prifysgol Betsi Cadwaladr",
        bng_e=270000,
        bng_n=340000,
        long=-3.5,
        lat=53.2,
        globalid="globalid-lhb",
        geom=MultiPolygon(
            Polygon(
                (
                    (269900, 340100),
                    (269900, 339900),
                    (270100, 339900),
                    (270100, 340100),
                    (269900, 340100),
                )
            )
        ),
    )


@pytest.mark.django_db
def test_lhb_detail_returns_empty_chain_arrays(api_client, lhb_standalone):
    """LocalHealthBoard has no succession table — predecessors / successors
    are always empty arrays, included for API consistency with the other
    entity detail endpoints."""
    url = reverse("local_health_board-detail", args=["7A4"])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ods_code"] == "7A4"
    assert data["predecessors"] == []
    assert data["successors"] == []
