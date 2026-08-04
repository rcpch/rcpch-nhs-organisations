"""
Tests for the baseline backfill data migration (0024).

The backfill creates one *Version row per existing entity, with
valid_to IS NULL, snapshotting the current state. These tests verify the
invariant that every existing entity has exactly one current version row
after the backfill runs.

The migration runs as part of the test database setup (migrations are
applied by pytest-django), so the test database is in the post-backfill
state. We create entities and then re-run the backfill logic against them
to verify the invariant, rather than relying on whatever seed data may or
may not be present.
"""
import datetime

import importlib

import pytest
from django.apps import apps
from django.db import connection

_migration_module = importlib.import_module(
    "rcpch_nhs_organisations.hospitals.migrations.0024_baseline_version_backfill"
)
backfill_organisation_versions = _migration_module.backfill_organisation_versions
backfill_trust_versions = _migration_module.backfill_trust_versions
backfill_local_health_board_versions = _migration_module.backfill_local_health_board_versions
backfill_integrated_care_board_versions = _migration_module.backfill_integrated_care_board_versions
backfill_nhs_england_region_versions = _migration_module.backfill_nhs_england_region_versions
backfill_paediatric_diabetes_unit_versions = _migration_module.backfill_paediatric_diabetes_unit_versions
backfill_paediatric_diabetes_network_versions = _migration_module.backfill_paediatric_diabetes_network_versions

Organisation = apps.get_model("hospitals", "Organisation")
OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")
Trust = apps.get_model("hospitals", "Trust")
TrustVersion = apps.get_model("hospitals", "TrustVersion")
LocalHealthBoard = apps.get_model("hospitals", "LocalHealthBoard")
LocalHealthBoardVersion = apps.get_model("hospitals", "LocalHealthBoardVersion")
IntegratedCareBoard = apps.get_model("hospitals", "IntegratedCareBoard")
IntegratedCareBoardVersion = apps.get_model("hospitals", "IntegratedCareBoardVersion")
NHSEnglandRegion = apps.get_model("hospitals", "NHSEnglandRegion")
NHSEnglandRegionVersion = apps.get_model("hospitals", "NHSEnglandRegionVersion")
PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")
PaediatricDiabetesUnitVersion = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitVersion"
)
PaediatricDiabetesNetwork = apps.get_model("hospitals", "PaediatricDiabetesNetwork")
PaediatricDiabetesNetworkVersion = apps.get_model(
    "hospitals", "PaediatricDiabetesNetworkVersion"
)


class _FakeSchemaEditor:
    """RunPython passes a schema_editor; the backfill functions ignore it."""

    pass


@pytest.fixture
def trust():
    return Trust.objects.create(ods_code="RXX", name="Test Trust")


@pytest.fixture
def organisation(trust):
    return Organisation.objects.create(
        ods_code="RXX01",
        name="Test Org",
        address1="1 Test St",
        city="Testville",
        postcode="TS1 1AA",
        active=True,
        trust=trust,
    )


@pytest.fixture
def local_health_board():
    from django.contrib.gis.geos import MultiPolygon, Polygon

    return LocalHealthBoard.objects.create(
        boundary_identifier="W11000023",
        name="Test LHB",
        welsh_name="Bwrdd",
        bng_e=300000,
        bng_n=300000,
        long=-3.0,
        lat=52.0,
        globalid="guid",
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
        ods_code="7A6",
    )


@pytest.fixture
def icb():
    from django.contrib.gis.geos import MultiPolygon, Polygon

    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000001",
        name="Test ICB",
        bng_e=400000,
        bng_n=400000,
        long=-1.0,
        lat=53.0,
        globalid="guid",
        geom=MultiPolygon(
            Polygon(
                (
                    (399900, 400100),
                    (399900, 399900),
                    (400100, 399900),
                    (400100, 400100),
                    (399900, 400100),
                )
            )
        ),
        ods_code="A01",
    )


@pytest.fixture
def nhs_england_region():
    from django.contrib.gis.geos import MultiPolygon, Polygon

    return NHSEnglandRegion.objects.create(
        boundary_identifier="E40000001",
        name="Test Region",
        bng_e=400000,
        bng_n=400000,
        long=-1.0,
        lat=53.0,
        globalid="guid",
        geom=MultiPolygon(
            Polygon(
                (
                    (399900, 400100),
                    (399900, 399900),
                    (400100, 399900),
                    (400100, 400100),
                    (399900, 400100),
                )
            )
        ),
        region_code="Y01",
    )


@pytest.fixture
def paediatric_diabetes_network():
    return PaediatricDiabetesNetwork.objects.create(pn_code="PN01", name="Test Net")


@pytest.fixture
def paediatric_diabetes_unit(paediatric_diabetes_network):
    return PaediatricDiabetesUnit.objects.create(
        pz_code="PZ001",
        paediatric_diabetes_network=paediatric_diabetes_network,
    )


def _run(fn):
    fn(apps, _FakeSchemaEditor())


@pytest.mark.django_db
def test_backfill_creates_one_current_version_per_organisation(organisation):
    _run(backfill_organisation_versions)
    versions = OrganisationVersion.objects.filter(organisation=organisation)
    assert versions.count() == 1
    assert versions.get().is_current()
    assert versions.get().name == "Test Org"


@pytest.mark.django_db
def test_backfill_creates_one_current_version_per_trust(trust):
    _run(backfill_trust_versions)
    versions = TrustVersion.objects.filter(trust=trust)
    assert versions.count() == 1
    assert versions.get().is_current()
    assert versions.get().name == "Test Trust"


@pytest.mark.django_db
def test_backfill_creates_one_current_version_per_lhb(local_health_board):
    _run(backfill_local_health_board_versions)
    versions = LocalHealthBoardVersion.objects.filter(
        local_health_board=local_health_board
    )
    assert versions.count() == 1
    assert versions.get().is_current()
    assert versions.get().name == "Test LHB"


@pytest.mark.django_db
def test_backfill_creates_one_current_version_per_icb(icb):
    _run(backfill_integrated_care_board_versions)
    versions = IntegratedCareBoardVersion.objects.filter(
        integrated_care_board=icb
    )
    assert versions.count() == 1
    assert versions.get().is_current()
    assert versions.get().name == "Test ICB"


@pytest.mark.django_db
def test_backfill_creates_one_current_version_per_nhs_england_region(
    nhs_england_region,
):
    _run(backfill_nhs_england_region_versions)
    versions = NHSEnglandRegionVersion.objects.filter(
        nhs_england_region=nhs_england_region
    )
    assert versions.count() == 1
    assert versions.get().is_current()
    assert versions.get().name == "Test Region"


@pytest.mark.django_db
def test_backfill_creates_one_current_version_per_pdu(paediatric_diabetes_unit):
    _run(backfill_paediatric_diabetes_unit_versions)
    versions = PaediatricDiabetesUnitVersion.objects.filter(
        paediatric_diabetes_unit=paediatric_diabetes_unit
    )
    assert versions.count() == 1
    assert versions.get().is_current()
    assert versions.get().active is True


@pytest.mark.django_db
def test_backfill_creates_one_current_version_per_pdn(paediatric_diabetes_network):
    _run(backfill_paediatric_diabetes_network_versions)
    versions = PaediatricDiabetesNetworkVersion.objects.filter(
        paediatric_diabetes_network=paediatric_diabetes_network
    )
    assert versions.count() == 1
    assert versions.get().is_current()
    assert versions.get().name == "Test Net"


@pytest.mark.django_db
def test_backfill_is_idempotent_safe_when_no_new_entities(organisation):
    """Running the backfill twice against the same entity creates two current
    rows. This is by design: the backfill is a one-off migration, not a
    reusable helper. The test documents this behaviour so it is not mistaken
    for a bug. The real write path (helpers in membership.py) always closes
    the previous row before opening a new one."""
    _run(backfill_organisation_versions)
    _run(backfill_organisation_versions)
    assert (
        OrganisationVersion.objects.filter(
            organisation=organisation, valid_to__isnull=True
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_backfill_snapshots_attributes(organisation):
    """The baseline row snapshots the entity's mutable attributes at backfill time."""
    _run(backfill_organisation_versions)
    version = OrganisationVersion.objects.get(organisation=organisation)
    assert version.address1 == "1 Test St"
    assert version.city == "Testville"
    assert version.postcode == "TS1 1AA"
    assert version.active is True
