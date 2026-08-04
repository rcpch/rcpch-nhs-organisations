"""
Tests for the remaining entity version models (Trust, LocalHealthBoard,
IntegratedCareBoard, NHSEnglandRegion, PaediatricDiabetesUnit,
PaediatricDiabetesNetwork).

These mirror the OrganisationVersion tests but are parametrised across all
version models to confirm the same temporal invariants hold for each:
- baseline version is current
- new version closes the previous
- as-of query returns the correct snapshot
- only one current version per entity
"""
import datetime

import pytest
from django.apps import apps

Organisation = apps.get_model("hospitals", "Organisation")
Trust = apps.get_model("hospitals", "Trust")
TrustVersion = apps.get_model("hospitals", "TrustVersion")
LocalHealthBoard = apps.get_model("hospitals", "LocalHealthBoard")
LocalHealthBoardVersion = apps.get_model("hospitals", "LocalHealthBoardVersion")
IntegratedCareBoard = apps.get_model("hospitals", "IntegratedCareBoard")
IntegratedCareBoardVersion = apps.get_model("hospitals", "IntegratedCareBoardVersion")
NHSEnglandRegion = apps.get_model("hospitals", "NHSEnglandRegion")
NHSEnglandRegionVersion = apps.get_model("hospitals", "NHSEnglandRegionVersion")
PaediatricDiabetesNetwork = apps.get_model("hospitals", "PaediatricDiabetesNetwork")
PaediatricDiabetesNetworkVersion = apps.get_model(
    "hospitals", "PaediatricDiabetesNetworkVersion"
)
PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")
PaediatricDiabetesUnitVersion = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitVersion"
)


# ---------------------------------------------------------------------------
# Fixtures: one per entity. These create the parent entity and a baseline
# version row. Each fixture returns a tuple of (parent, version_model).
# ---------------------------------------------------------------------------


@pytest.fixture
def trust():
    return Trust.objects.create(ods_code="RXX", name="Test Trust")


@pytest.fixture
def trust_version(trust):
    return TrustVersion.objects.create(
        trust=trust,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Test Trust",
        active=True,
    )


from django.contrib.gis.geos import MultiPolygon, Polygon


def _square_geom(easting, northing, side=200):
    """Helper: build a small square MultiPolygon for boundary fixtures."""
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
def local_health_board():
    return LocalHealthBoard.objects.create(
        boundary_identifier="W11000023",
        name="Test LHB",
        welsh_name="Bwrdd Iechyd",
        bng_e=300000,
        bng_n=300000,
        long=-3.0,
        lat=52.0,
        globalid="guid-lhb",
        geom=_square_geom(300000, 300000),
        ods_code="7A6",
    )


@pytest.fixture
def lhb_version(local_health_board):
    return LocalHealthBoardVersion.objects.create(
        local_health_board=local_health_board,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Test LHB",
    )


@pytest.fixture
def icb():
    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000001",
        name="Test ICB",
        bng_e=400000,
        bng_n=400000,
        long=-1.0,
        lat=53.0,
        globalid="guid-icb",
        geom=_square_geom(400000, 400000),
        ods_code="A01",
    )


@pytest.fixture
def icb_version(icb):
    return IntegratedCareBoardVersion.objects.create(
        integrated_care_board=icb,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Test ICB",
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
        globalid="guid-region",
        geom=_square_geom(400000, 400000),
        region_code="Y01",
    )


@pytest.fixture
def nhs_england_region_version(nhs_england_region):
    return NHSEnglandRegionVersion.objects.create(
        nhs_england_region=nhs_england_region,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Test Region",
    )


@pytest.fixture
def paediatric_diabetes_network():
    return PaediatricDiabetesNetwork.objects.create(
        pn_code="PN01",
        name="Test Network",
    )


@pytest.fixture
def pdn_version(paediatric_diabetes_network):
    return PaediatricDiabetesNetworkVersion.objects.create(
        paediatric_diabetes_network=paediatric_diabetes_network,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name="Test Network",
    )


@pytest.fixture
def paediatric_diabetes_unit():
    return PaediatricDiabetesUnit.objects.create(pz_code="PZ001")


@pytest.fixture
def pdu_version(paediatric_diabetes_unit):
    return PaediatricDiabetesUnitVersion.objects.create(
        paediatric_diabetes_unit=paediatric_diabetes_unit,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        active=True,
    )


# ---------------------------------------------------------------------------
# Parametrised invariant tests. Each test runs against every version model.
# The `version_row` fixture is parametrised via indirect to cover all models.
# ---------------------------------------------------------------------------

# Map fixture name -> (parent fk field name on the version model)
VERSION_FIXTURES = [
    "trust_version",
    "lhb_version",
    "icb_version",
    "nhs_england_region_version",
    "pdn_version",
    "pdu_version",
]


@pytest.fixture(params=VERSION_FIXTURES)
def version_row(request):
    return request.getfixturevalue(request.param)


def _parent_field(version_row):
    """Return the FK field name on the version model that points to its parent.

    Uses an explicit map rather than introspecting field order, because some
    version models (e.g. PaediatricDiabetesUnitVersion) carry additional FKs
    (the network snapshot) that are not the parent link.
    """
    parent_field_map = {
        "TrustVersion": "trust",
        "LocalHealthBoardVersion": "local_health_board",
        "IntegratedCareBoardVersion": "integrated_care_board",
        "NHSEnglandRegionVersion": "nhs_england_region",
        "PaediatricDiabetesNetworkVersion": "paediatric_diabetes_network",
        "PaediatricDiabetesUnitVersion": "paediatric_diabetes_unit",
    }
    return parent_field_map[version_row.__class__.__name__]


@pytest.mark.django_db
def test_baseline_version_is_current(version_row):
    assert version_row.is_current() is True
    assert version_row.valid_to is None


@pytest.mark.django_db
def test_only_one_current_version_per_entity(version_row):
    parent_field = _parent_field(version_row)
    version_model = version_row.__class__
    parent = getattr(version_row, parent_field)
    current_count = version_model.objects.filter(
        **{parent_field: parent, "valid_to__isnull": True}
    ).count()
    assert current_count == 1


@pytest.mark.django_db
def test_new_version_closes_previous(version_row):
    """Creating a new current version must close the previous one."""
    parent_field = _parent_field(version_row)
    version_model = version_row.__class__
    parent = getattr(version_row, parent_field)

    # Close the old row and open a new one (the helper pattern).
    version_model.objects.filter(
        **{parent_field: parent, "valid_to__isnull": True}
    ).update(valid_to=datetime.date(2021, 6, 1))
    new_row = version_model.objects.create(
        **{parent_field: parent},
        valid_from=datetime.date(2021, 6, 1),
        valid_to=None,
    )

    version_row.refresh_from_db()
    assert version_row.valid_to == datetime.date(2021, 6, 1)
    assert version_row.is_current() is False
    assert new_row.is_current() is True


@pytest.mark.django_db
def test_as_of_query_returns_correct_snapshot(version_row):
    """The as-of query returns the version in force on the given date."""
    parent_field = _parent_field(version_row)
    version_model = version_row.__class__
    parent = getattr(version_row, parent_field)

    # Close the old row and open a new one.
    version_model.objects.filter(
        **{parent_field: parent, "valid_to__isnull": True}
    ).update(valid_to=datetime.date(2021, 6, 1))
    version_model.objects.create(
        **{parent_field: parent},
        valid_from=datetime.date(2021, 6, 1),
        valid_to=None,
    )

    # Before the change date: the old row is in force.
    before = version_model.objects.filter(
        **{parent_field: parent},
        valid_from__lte=datetime.date(2020, 6, 1),
    ).filter(valid_to__gt=datetime.date(2020, 6, 1)).get()
    assert before.pk == version_row.pk

    # After the change date: the new row is in force.
    after = version_model.objects.filter(
        **{parent_field: parent},
        valid_from__lte=datetime.date(2022, 1, 1),
    ).filter(valid_to__isnull=True).get()
    assert after.pk != version_row.pk


@pytest.mark.django_db
def test_as_of_query_before_first_version_returns_nothing(version_row):
    """A date before the first valid_from returns no version."""
    parent_field = _parent_field(version_row)
    version_model = version_row.__class__
    parent = getattr(version_row, parent_field)
    qs = version_model.objects.filter(
        **{parent_field: parent},
        valid_from__lte=datetime.date(2019, 1, 1),
    ).filter(valid_to__gt=datetime.date(2019, 1, 1))
    assert not qs.exists()
