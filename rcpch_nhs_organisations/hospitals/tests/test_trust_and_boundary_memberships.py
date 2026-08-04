"""
Tests for the trust-level and boundary membership tables added in the second
batch of relationship-membership models:

- TrustIntegratedCareBoardMembership (trust → ICB)
- TrustNHSEnglandRegionMembership (trust → NHS England region)
- OrganisationLondonBoroughMembership (org → London borough)
- OrganisationLocalAuthorityDistrictMembership (org → LAD)
- OrganisationLowerLayerSuperOutputAreaMembership (org → LSOA)

Same temporal invariants as the first batch of membership tests, parametrised
across all five models.
"""
import datetime

import pytest
from django.apps import apps
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db.models import ProtectedError

Trust = apps.get_model("hospitals", "Trust")
IntegratedCareBoard = apps.get_model("hospitals", "IntegratedCareBoard")
NHSEnglandRegion = apps.get_model("hospitals", "NHSEnglandRegion")
LondonBorough = apps.get_model("hospitals", "LondonBorough")
LocalAuthorityDistrict = apps.get_model("hospitals", "LocalAuthorityDistrict")
LowerLayerSuperOutputArea = apps.get_model(
    "hospitals", "LowerLayerSuperOutputArea"
)
Organisation = apps.get_model("hospitals", "Organisation")

TrustIntegratedCareBoardMembership = apps.get_model(
    "hospitals", "TrustIntegratedCareBoardMembership"
)
TrustNHSEnglandRegionMembership = apps.get_model(
    "hospitals", "TrustNHSEnglandRegionMembership"
)
OrganisationLondonBoroughMembership = apps.get_model(
    "hospitals", "OrganisationLondonBoroughMembership"
)
OrganisationLocalAuthorityDistrictMembership = apps.get_model(
    "hospitals", "OrganisationLocalAuthorityDistrictMembership"
)
OrganisationLowerLayerSuperOutputAreaMembership = apps.get_model(
    "hospitals", "OrganisationLowerLayerSuperOutputAreaMembership"
)


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def trust():
    return Trust.objects.create(ods_code="RXX", name="Test Trust")


@pytest.fixture
def trust2():
    return Trust.objects.create(ods_code="RYY", name="Test Trust 2")


@pytest.fixture
def icb():
    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000001",
        name="Test ICB",
        bng_e=400000,
        bng_n=400000,
        long=-1.0,
        lat=53.0,
        globalid="guid",
        geom=_square_geom(400000, 400000),
        ods_code="A01",
    )


@pytest.fixture
def icb2():
    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000002",
        name="Test ICB 2",
        bng_e=410000,
        bng_n=410000,
        long=-1.1,
        lat=53.1,
        globalid="guid2",
        geom=_square_geom(410000, 410000),
        ods_code="A02",
    )


@pytest.fixture
def nhs_england_region():
    return NHSEnglandRegion.objects.create(
        boundary_identifier="E40000001",
        name="Test Region",
        bng_e=400000,
        bng_n=400000,
        long=-1.0,
        lat=53.0,
        globalid="guid",
        geom=_square_geom(400000, 400000),
        region_code="Y01",
    )


@pytest.fixture
def nhs_england_region2():
    return NHSEnglandRegion.objects.create(
        boundary_identifier="E40000002",
        name="Test Region 2",
        bng_e=410000,
        bng_n=410000,
        long=-1.1,
        lat=53.1,
        globalid="guid2",
        geom=_square_geom(410000, 410000),
        region_code="Y02",
    )


@pytest.fixture
def london_borough():
    return LondonBorough.objects.create(
        name="Test Borough",
        gss_code="E09000001",
        hectares=1000.0,
        nonld_area=0.0,
        ons_inner="1",
        geom=_square_geom(500000, 200000),
    )


@pytest.fixture
def london_borough2():
    return LondonBorough.objects.create(
        name="Test Borough 2",
        gss_code="E09000002",
        hectares=1000.0,
        nonld_area=0.0,
        ons_inner="1",
        geom=_square_geom(510000, 210000),
    )


@pytest.fixture
def local_authority_district():
    return LocalAuthorityDistrict.objects.create(
        lad24cd="LAD001",
        lad24nm="Test District",
        lad24nmw="Test District Welsh",
        bng_e=350000,
        bng_n=400000,
        long=-3.0,
        lat=53.0,
        globalid="guid1",
        geom=_square_geom(350000, 400000),
    )


@pytest.fixture
def local_authority_district2():
    return LocalAuthorityDistrict.objects.create(
        lad24cd="LAD002",
        lad24nm="Test District 2",
        lad24nmw="Test District 2 Welsh",
        bng_e=360000,
        bng_n=410000,
        long=-3.1,
        lat=53.1,
        globalid="guid2",
        geom=_square_geom(360000, 410000),
    )


@pytest.fixture
def lsoa():
    return LowerLayerSuperOutputArea.objects.create(
        lsoa11cd="E01000001",
        lsoa11nm="Test LSOA",
        lsoa11nmw="Test LSOA Welsh",
        bng_e=350000,
        bng_n=400000,
        long=-3.0,
        lat=53.0,
        globalid="guid1",
        geom=_square_geom(350000, 400000),
    )


@pytest.fixture
def lsoa2():
    return LowerLayerSuperOutputArea.objects.create(
        lsoa11cd="E01000002",
        lsoa11nm="Test LSOA 2",
        lsoa11nmw="Test LSOA 2 Welsh",
        bng_e=360000,
        bng_n=410000,
        long=-3.1,
        lat=53.1,
        globalid="guid2",
        geom=_square_geom(360000, 410000),
    )


@pytest.fixture
def organisation(trust):
    return Organisation.objects.create(
        ods_code="RXX01",
        name="Test Org",
        active=True,
        trust=trust,
    )


# ---------------------------------------------------------------------------
# Per-membership fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def trust_icb_membership(trust, icb):
    return TrustIntegratedCareBoardMembership.objects.create(
        trust=trust,
        integrated_care_board=icb,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


@pytest.fixture
def trust_nhs_england_region_membership(trust, nhs_england_region):
    return TrustNHSEnglandRegionMembership.objects.create(
        trust=trust,
        nhs_england_region=nhs_england_region,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


@pytest.fixture
def london_borough_membership(organisation, london_borough):
    return OrganisationLondonBoroughMembership.objects.create(
        organisation=organisation,
        london_borough=london_borough,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


@pytest.fixture
def local_authority_district_membership(organisation, local_authority_district):
    return OrganisationLocalAuthorityDistrictMembership.objects.create(
        organisation=organisation,
        local_authority_district=local_authority_district,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


@pytest.fixture
def lsoa_membership(organisation, lsoa):
    return OrganisationLowerLayerSuperOutputAreaMembership.objects.create(
        organisation=organisation,
        lower_layer_super_output_area=lsoa,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


# (fixture_name, child_field, parent_field, second_parent_fixture_name)
MEMBERSHIP_SPECS = [
    ("trust_icb_membership", "trust", "integrated_care_board", "icb2"),
    (
        "trust_nhs_england_region_membership",
        "trust",
        "nhs_england_region",
        "nhs_england_region2",
    ),
    (
        "london_borough_membership",
        "organisation",
        "london_borough",
        "london_borough2",
    ),
    (
        "local_authority_district_membership",
        "organisation",
        "local_authority_district",
        "local_authority_district2",
    ),
    ("lsoa_membership", "organisation", "lower_layer_super_output_area", "lsoa2"),
]


MEMBERSHIP_FIXTURE_NAMES = [spec[0] for spec in MEMBERSHIP_SPECS]


@pytest.fixture(params=MEMBERSHIP_FIXTURE_NAMES)
def membership_row(request):
    return request.getfixturevalue(request.param)


def _spec_for(fixture_name):
    for spec in MEMBERSHIP_SPECS:
        if spec[0] == fixture_name:
            return spec
    raise AssertionError(f"unknown fixture {fixture_name}")


# ---------------------------------------------------------------------------
# Parametrised invariant tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_baseline_membership_is_current(membership_row):
    assert membership_row.is_current() is True
    assert membership_row.valid_to is None


@pytest.mark.django_db
def test_only_one_current_membership_per_child(membership_row, request):
    spec = _spec_for(request.node.callspec.id)
    child_field = spec[1]
    child = getattr(membership_row, child_field)
    membership_model = membership_row.__class__
    current_count = membership_model.objects.filter(
        **{child_field: child, "valid_to__isnull": True}
    ).count()
    assert current_count == 1


@pytest.mark.django_db
def test_new_membership_closes_previous(membership_row, request):
    spec = _spec_for(request.node.callspec.id)
    child_field, parent_field, second_parent_fixture_name = (
        spec[1],
        spec[2],
        spec[3],
    )
    child = getattr(membership_row, child_field)
    membership_model = membership_row.__class__
    new_parent = request.getfixturevalue(second_parent_fixture_name)

    membership_model.objects.filter(
        **{child_field: child, "valid_to__isnull": True}
    ).update(valid_to=datetime.date(2021, 6, 1))
    new_row = membership_model.objects.create(
        **{child_field: child, parent_field: new_parent},
        valid_from=datetime.date(2021, 6, 1),
        valid_to=None,
    )

    membership_row.refresh_from_db()
    assert membership_row.valid_to == datetime.date(2021, 6, 1)
    assert membership_row.is_current() is False
    assert new_row.is_current() is True
    assert getattr(new_row, parent_field) == new_parent


@pytest.mark.django_db
def test_as_of_query_returns_correct_parent(membership_row, request):
    spec = _spec_for(request.node.callspec.id)
    child_field, parent_field, second_parent_fixture_name = (
        spec[1],
        spec[2],
        spec[3],
    )
    child = getattr(membership_row, child_field)
    membership_model = membership_row.__class__
    new_parent = request.getfixturevalue(second_parent_fixture_name)

    membership_model.objects.filter(
        **{child_field: child, "valid_to__isnull": True}
    ).update(valid_to=datetime.date(2021, 6, 1))
    membership_model.objects.create(
        **{child_field: child, parent_field: new_parent},
        valid_from=datetime.date(2021, 6, 1),
        valid_to=None,
    )

    before = membership_model.objects.filter(
        **{child_field: child},
        valid_from__lte=datetime.date(2020, 6, 1),
    ).filter(valid_to__gt=datetime.date(2020, 6, 1)).get()
    assert getattr(before, parent_field) == getattr(membership_row, parent_field)

    after = membership_model.objects.filter(
        **{child_field: child},
        valid_from__lte=datetime.date(2022, 1, 1),
    ).filter(valid_to__isnull=True).get()
    assert getattr(after, parent_field) == new_parent


@pytest.mark.django_db
def test_as_of_query_before_first_membership_returns_nothing(membership_row, request):
    spec = _spec_for(request.node.callspec.id)
    child_field = spec[1]
    child = getattr(membership_row, child_field)
    membership_model = membership_row.__class__
    qs = membership_model.objects.filter(
        **{child_field: child},
        valid_from__lte=datetime.date(2019, 1, 1),
    ).filter(valid_to__gt=datetime.date(2019, 1, 1))
    assert not qs.exists()


@pytest.mark.django_db
def test_protect_on_delete_preserves_history(membership_row, request):
    spec = _spec_for(request.node.callspec.id)
    parent_field = spec[2]
    parent = getattr(membership_row, parent_field)
    with pytest.raises(ProtectedError):
        parent.delete()
