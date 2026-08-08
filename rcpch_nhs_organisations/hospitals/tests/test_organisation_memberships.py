"""
Tests for the organisation→parent and PDU→network membership tables.

These mirror the entity version tests but for the relationship layer. The
same temporal invariants apply:
- baseline membership is current
- only one current membership per (organisation, relationship-type) pair
- new membership closes the previous one
- as-of query returns the correct parent at a given date
- as-of query before the first membership returns nothing

Parametrised across all seven membership models.
"""
import datetime

import pytest
from django.apps import apps

Organisation = apps.get_model("hospitals", "Organisation")
Trust = apps.get_model("hospitals", "Trust")
LocalHealthBoard = apps.get_model("hospitals", "LocalHealthBoard")
IntegratedCareBoard = apps.get_model("hospitals", "IntegratedCareBoard")
NHSEnglandRegion = apps.get_model("hospitals", "NHSEnglandRegion")
OPENUKNetwork = apps.get_model("hospitals", "OPENUKNetwork")
PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")
PaediatricDiabetesNetwork = apps.get_model("hospitals", "PaediatricDiabetesNetwork")

OrganisationTrustMembership = apps.get_model(
    "hospitals", "OrganisationTrustMembership"
)
OrganisationLocalHealthBoardMembership = apps.get_model(
    "hospitals", "OrganisationLocalHealthBoardMembership"
)
OrganisationIntegratedCareBoardMembership = apps.get_model(
    "hospitals", "OrganisationIntegratedCareBoardMembership"
)
OrganisationNHSEnglandRegionMembership = apps.get_model(
    "hospitals", "OrganisationNHSEnglandRegionMembership"
)
OrganisationOPENUKNetworkMembership = apps.get_model(
    "hospitals", "OrganisationOPENUKNetworkMembership"
)
OrganisationPaediatricDiabetesUnitMembership = apps.get_model(
    "hospitals", "OrganisationPaediatricDiabetesUnitMembership"
)
PaediatricDiabetesUnitNetworkMembership = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitNetworkMembership"
)


# ---------------------------------------------------------------------------
# Geometry helper for boundary fixtures.
# ---------------------------------------------------------------------------


def _square_geom(easting, northing, side=200):
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


# ---------------------------------------------------------------------------
# Fixtures: parent entities and a baseline organisation/PDU.
# ---------------------------------------------------------------------------


@pytest.fixture
def trust():
    return Trust.objects.create(ods_code="RXX", name="Test Trust")


@pytest.fixture
def trust2():
    return Trust.objects.create(ods_code="RYY", name="Test Trust 2")


@pytest.fixture
def local_health_board():
    return LocalHealthBoard.objects.create(
        boundary_identifier="W11000023",
        name="Test LHB",
        welsh_name="Bwrdd",
        bng_e=300000,
        bng_n=300000,
        long=-3.0,
        lat=52.0,
        globalid="guid",
        geom=_square_geom(300000, 300000),
        ods_code="7A6",
    )


@pytest.fixture
def local_health_board2():
    return LocalHealthBoard.objects.create(
        boundary_identifier="W11000024",
        name="Test LHB 2",
        welsh_name="Bwrdd 2",
        bng_e=310000,
        bng_n=310000,
        long=-3.1,
        lat=52.1,
        globalid="guid2",
        geom=_square_geom(310000, 310000),
        ods_code="7A7",
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
def openuk_network():
    return OPENUKNetwork.objects.create(
        name="Test OPEN UK Network",
        boundary_identifier="OPENUK01",
        country="England",
    )


@pytest.fixture
def openuk_network2():
    return OPENUKNetwork.objects.create(
        name="Test OPEN UK Network 2",
        boundary_identifier="OPENUK02",
        country="England",
    )


@pytest.fixture
def paediatric_diabetes_network():
    return PaediatricDiabetesNetwork.objects.create(pn_code="PN01", name="Test Net")


@pytest.fixture
def paediatric_diabetes_network2():
    return PaediatricDiabetesNetwork.objects.create(pn_code="PN02", name="Test Net 2")


@pytest.fixture
def paediatric_diabetes_unit():
    return PaediatricDiabetesUnit.objects.create(pz_code="PZ001")


@pytest.fixture
def paediatric_diabetes_unit2():
    return PaediatricDiabetesUnit.objects.create(pz_code="PZ002")


@pytest.fixture
def organisation(trust):
    return Organisation.objects.create(
        ods_code="RXX01",
        name="Test Org",
        active=True,
        trust=trust,
    )


# ---------------------------------------------------------------------------
# Per-membership fixtures: create a baseline membership row.
# Each returns (membership_row, child_field, parent_field, parent2_fixture_value).
# We use a dict to map fixture name -> (child_field, parent_field, second_parent_fixture).
# ---------------------------------------------------------------------------

# Each entry: (fixture_name, child_field, parent_field, second_parent_fixture_name)
MEMBERSHIP_SPECS = [
    ("trust_membership", "organisation", "trust", "trust2"),
    ("lhb_membership", "organisation", "local_health_board", "local_health_board2"),
    ("icb_membership", "organisation", "integrated_care_board", "icb2"),
    (
        "nhs_england_region_membership",
        "organisation",
        "nhs_england_region",
        "nhs_england_region2",
    ),
    (
        "openuk_membership",
        "organisation",
        "openuk_network",
        "openuk_network2",
    ),
    (
        "pdu_membership",
        "organisation",
        "paediatric_diabetes_unit",
        "paediatric_diabetes_unit2",
    ),
    (
        "pdu_network_membership",
        "paediatric_diabetes_unit",
        "paediatric_diabetes_network",
        "paediatric_diabetes_network2",
    ),
]


@pytest.fixture
def trust_membership(organisation, trust):
    return OrganisationTrustMembership.objects.create(
        organisation=organisation,
        trust=trust,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


@pytest.fixture
def lhb_membership(organisation, local_health_board):
    # Welsh org: clear the trust FK to avoid confusion
    organisation.trust = None
    organisation.save(update_fields=["trust"])
    return OrganisationLocalHealthBoardMembership.objects.create(
        organisation=organisation,
        local_health_board=local_health_board,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


@pytest.fixture
def icb_membership(organisation, icb):
    return OrganisationIntegratedCareBoardMembership.objects.create(
        organisation=organisation,
        integrated_care_board=icb,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


@pytest.fixture
def nhs_england_region_membership(organisation, nhs_england_region):
    return OrganisationNHSEnglandRegionMembership.objects.create(
        organisation=organisation,
        nhs_england_region=nhs_england_region,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


@pytest.fixture
def openuk_membership(organisation, openuk_network):
    return OrganisationOPENUKNetworkMembership.objects.create(
        organisation=organisation,
        openuk_network=openuk_network,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


@pytest.fixture
def pdu_membership(organisation, paediatric_diabetes_unit):
    return OrganisationPaediatricDiabetesUnitMembership.objects.create(
        organisation=organisation,
        paediatric_diabetes_unit=paediatric_diabetes_unit,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


@pytest.fixture
def pdu_network_membership(paediatric_diabetes_unit, paediatric_diabetes_network):
    return PaediatricDiabetesUnitNetworkMembership.objects.create(
        paediatric_diabetes_unit=paediatric_diabetes_unit,
        paediatric_diabetes_network=paediatric_diabetes_network,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )


# Build the parametrised fixture list from the specs.
MEMBERSHIP_FIXTURE_NAMES = [spec[0] for spec in MEMBERSHIP_SPECS]


@pytest.fixture(params=MEMBERSHIP_FIXTURE_NAMES)
def membership_row(request):
    return request.getfixturevalue(request.param)


def _spec_for(fixture_name):
    for spec in MEMBERSHIP_SPECS:
        if spec[0] == fixture_name:
            return spec
    raise AssertionError(f"unknown fixture {fixture_name}")


@pytest.mark.django_db
def test_baseline_membership_is_current(membership_row, request):
    assert membership_row.is_current() is True
    assert membership_row.valid_to is None


@pytest.mark.django_db
def test_only_one_current_membership_per_child(membership_row, request):
    spec = _spec_for(request.node.callspec.id)
    child_field, parent_field, _ = spec[1], spec[2], spec[3]
    child_field, parent_field, second_parent_fixture = spec[1], spec[2], spec[3]
    child = getattr(membership_row, child_field)
    membership_model = membership_row.__class__
    current_count = membership_model.objects.filter(
        **{child_field: child, "valid_to__isnull": True}
    ).count()
    assert current_count == 1


@pytest.mark.django_db
def test_new_membership_closes_previous(membership_row, request):
    """Reassigning to a new parent closes the old row and opens a new one."""
    spec = _spec_for(request.node.callspec.id)
    child_field, parent_field, second_parent_fixture_name = (
        spec[1],
        spec[2],
        spec[3],
    )
    child = getattr(membership_row, child_field)
    membership_model = membership_row.__class__
    new_parent = request.getfixturevalue(second_parent_fixture_name)

    # The helper pattern: close the old row, open a new one.
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
    """The as-of query returns the parent in force on the given date."""
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

    # Before the change: old parent in force.
    before = membership_model.objects.filter(
        **{child_field: child},
        valid_from__lte=datetime.date(2020, 6, 1),
    ).filter(valid_to__gt=datetime.date(2020, 6, 1)).get()
    assert getattr(before, parent_field) == getattr(membership_row, parent_field)

    # After the change: new parent in force.
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
    """Deleting the parent is prevented by on_delete=PROTECT, so history is not lost."""
    spec = _spec_for(request.node.callspec.id)
    parent_field = spec[2]
    parent = getattr(membership_row, parent_field)
    from django.db.models import ProtectedError

    with pytest.raises(ProtectedError):
        parent.delete()
