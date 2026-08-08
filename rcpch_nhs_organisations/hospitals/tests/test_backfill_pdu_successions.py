"""
Tests for the backfill_pdu_successions management command.

The command reads the curated PDU history from pdu_history.py (generated
from Master_PDU_Lookup.xlsx) and writes PDU version rows, network
memberships, lead-organisation memberships, and succession rows into the
temporal layer. It also creates missing PDU rows (inactive predecessors
and never-participated codes) and reassigns lead organisations on
succession.

These tests use a small subset of the real constants (patched into the
command's namespace) so they are deterministic and do not depend on the
full spreadsheet.
"""
import datetime
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db.models import Q

from rcpch_nhs_organisations.hospitals.models import (
    Organisation,
    PaediatricDiabetesNetwork,
    PaediatricDiabetesUnit,
    PaediatricDiabetesUnitSuccession,
    PaediatricDiabetesUnitVersion,
    PaediatricDiabetesUnitNetworkMembership,
    OrganisationPaediatricDiabetesUnitMembership,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def network_eoe():
    return PaediatricDiabetesNetwork.objects.create(
        pn_code="PN06", name="East of England"
    )


@pytest.fixture
def network_lse():
    return PaediatricDiabetesNetwork.objects.create(
        pn_code="PN05", name="London & South East"
    )


@pytest.fixture
def network_wales():
    return PaediatricDiabetesNetwork.objects.create(
        pn_code="PN07", name="Wales"
    )


@pytest.fixture
def lead_org_a():
    return Organisation.objects.create(
        ods_code="RWF01", name="Tunbridge Wells Hospital"
    )


@pytest.fixture
def lead_org_b():
    return Organisation.objects.create(
        ods_code="RWF02", name="Maidstone Hospital"
    )


@pytest.fixture
def welsh_lead_org():
    return Organisation.objects.create(
        ods_code="7A2AA", name="GLANGWILI HOSPITAL"
    )


# A small PDU_HISTORY with:
# - PZ216: an active PDU that merges into PZ253 (single state, inactive)
# - PZ253: the successor (single state, active)
# - PZ056: a Welsh inactive predecessor that merges into PZ244
# - PZ244: the Welsh successor
# - PZ013: a never-participated code (closure with successor PZ167)
# - PZ167: the successor of the never-participated code
SMALL_PDU_HISTORY = [
    {
        "pz_code": "PZ216",
        "unit_name": "Tunbridge Wells Hospital",
        "states": [
            {
                "first_audit_year": "2009-10",
                "last_audit_year": "2024-25",
                "active": False,
                "ods_site": "RWF01",
                "ods_trust": "RWF",
                "icb_lhb": "England - NHS Kent and Medway Integrated Care Board",
                "regional_network": "London & South East",
                "nhs_england_region": "South East",
                "country": "England",
                "reason_for_change": "Merged",
            },
        ],
        "replaced_by": "PZ253",
        "notes": None,
    },
    {
        "pz_code": "PZ253",
        "unit_name": "Maidstone and Tunbridge Wells",
        "states": [
            {
                "first_audit_year": "2025-26",
                "last_audit_year": None,
                "active": True,
                "ods_site": "RWF01",
                "ods_trust": "RWF",
                "icb_lhb": "England - NHS Kent and Medway Integrated Care Board",
                "regional_network": "London & South East",
                "nhs_england_region": "South East",
                "country": "England",
                "reason_for_change": None,
            },
        ],
        "replaced_by": None,
        "notes": None,
    },
    {
        "pz_code": "PZ056",
        "unit_name": "West Wales General Hospital",
        "states": [
            {
                "first_audit_year": "2004-05",
                "last_audit_year": "2018-19",
                "active": False,
                "ods_site": "7A2AA",
                "ods_trust": None,
                "icb_lhb": "Wales - Hywel Dda University Health Board",
                "regional_network": "Wales",
                "nhs_england_region": "Wales",
                "country": "Wales",
                "reason_for_change": "Merged",
            },
        ],
        "replaced_by": "PZ244",
        "notes": None,
    },
    {
        "pz_code": "PZ244",
        "unit_name": "Hywel Dda University Health Board",
        "states": [
            {
                "first_audit_year": "2019-20",
                "last_audit_year": None,
                "active": True,
                "ods_site": "7A2AA",
                "ods_trust": None,
                "icb_lhb": "Wales - Hywel Dda University Health Board",
                "regional_network": "Wales",
                "nhs_england_region": "Wales",
                "country": "Wales",
                "reason_for_change": None,
            },
        ],
        "replaced_by": None,
        "notes": None,
    },
    {
        "pz_code": "PZ013",
        "unit_name": "University Hospitals of Morecambe Bay NHS Trust",
        "states": [
            {
                "first_audit_year": "-",
                "last_audit_year": None,
                "active": False,
                "ods_site": "RTX01",
                "ods_trust": None,
                "icb_lhb": None,
                "regional_network": None,
                "nhs_england_region": None,
                "country": None,
                "reason_for_change": None,
            },
        ],
        "replaced_by": "PZ167",
        "notes": None,
    },
    {
        "pz_code": "PZ167",
        "unit_name": "University Hospitals of Morecambe Bay",
        "states": [
            {
                "first_audit_year": "2004-05",
                "last_audit_year": None,
                "active": True,
                "ods_site": "RTX01",
                "ods_trust": "RTX",
                "icb_lhb": "England - NHS Lancashire and South Cumbria ICB",
                "regional_network": "North West",
                "nhs_england_region": "North West",
                "country": "England",
                "reason_for_change": None,
            },
        ],
        "replaced_by": None,
        "notes": None,
    },
]

SMALL_PDU_SUCCESSIONS = [
    {
        "predecessor": "PZ216",
        "successor": "PZ253",
        "succession_date": datetime.date(2025, 4, 1),
        "succession_type": "merger",
        "notes": "Tunbridge Wells Hospital (PZ216) -> PZ253.",
    },
    {
        "predecessor": "PZ056",
        "successor": "PZ244",
        "succession_date": datetime.date(2019, 4, 1),
        "succession_type": "merger",
        "notes": "West Wales General Hospital (PZ056) -> PZ244.",
    },
    {
        "predecessor": "PZ013",
        "successor": "PZ167",
        "succession_date": datetime.date(2004, 4, 1),
        "succession_type": "closure",
        "notes": "Allocated but never participated; allocation transferred to PZ167.",
    },
]


@pytest.fixture
def patched_constants():
    """Patch the command's constants with the small test set."""
    with patch(
        "rcpch_nhs_organisations.hospitals.management.commands.backfill_pdu_successions.PDU_HISTORY",
        SMALL_PDU_HISTORY,
    ), patch(
        "rcpch_nhs_organisations.hospitals.management.commands.backfill_pdu_successions.PDU_SUCCESSIONS",
        SMALL_PDU_SUCCESSIONS,
    ):
        yield


def _run_command(*args, patched=True):
    """Call the command and return (stdout, stderr)."""
    out = StringIO()
    err = StringIO()
    call_command("backfill_pdu_successions", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Audit-year-to-date conversion
# ---------------------------------------------------------------------------


def test_audit_year_to_date_normal():
    from rcpch_nhs_organisations.hospitals.management.commands.backfill_pdu_successions import (
        audit_year_to_date,
    )

    assert audit_year_to_date("2024-25") == datetime.date(2024, 4, 1)
    assert audit_year_to_date("2003-04") == datetime.date(2003, 4, 1)
    assert audit_year_to_date("2026-27") == datetime.date(2026, 4, 1)


def test_audit_year_to_date_edge_cases():
    from rcpch_nhs_organisations.hospitals.management.commands.backfill_pdu_successions import (
        audit_year_to_date,
    )

    assert audit_year_to_date("-") is None
    assert audit_year_to_date(None) is None
    assert audit_year_to_date("") is None
    assert audit_year_to_date("   ") is None


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dry_run_writes_nothing(patched_constants, network_eoe, network_wales, lead_org_a, welsh_lead_org):
    """Dry-run mode reports what would change but writes nothing."""
    out, _ = _run_command("--dry-run")
    assert "would create PDU" in out or "would backfill" in out
    # No PDUs, versions, memberships, or successions should exist.
    assert PaediatricDiabetesUnit.objects.count() == 0
    assert PaediatricDiabetesUnitVersion.objects.count() == 0
    assert PaediatricDiabetesUnitSuccession.objects.count() == 0
    assert OrganisationPaediatricDiabetesUnitMembership.objects.count() == 0
    assert PaediatricDiabetesUnitNetworkMembership.objects.count() == 0


# ---------------------------------------------------------------------------
# PDU creation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_creates_missing_pdus(
    patched_constants, network_eoe, network_wales, lead_org_a, welsh_lead_org
):
    """The command creates PDU rows that don't exist (inactive predecessors)."""
    _run_command("--yes")
    # PZ216 (inactive predecessor) should be created.
    pz216 = PaediatricDiabetesUnit.objects.get(pz_code="PZ216")
    assert pz216.active is False
    assert pz216.unit_name == "Tunbridge Wells Hospital"
    assert pz216.lead_organisation == lead_org_a

    # PZ253 (successor, active) should be created.
    pz253 = PaediatricDiabetesUnit.objects.get(pz_code="PZ253")
    assert pz253.active is True

    # PZ056 (Welsh inactive predecessor) should be created.
    pz056 = PaediatricDiabetesUnit.objects.get(pz_code="PZ056")
    assert pz056.active is False
    assert pz056.lead_organisation == welsh_lead_org


@pytest.mark.django_db
def test_never_participated_created_inactive(
    patched_constants, network_eoe, network_wales, lead_org_a, welsh_lead_org
):
    """Never-participated codes are created with active=False."""
    _run_command("--yes")
    pz013 = PaediatricDiabetesUnit.objects.get(pz_code="PZ013")
    assert pz013.active is False


# ---------------------------------------------------------------------------
# Successions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_succession_row_created(
    patched_constants, network_eoe, network_wales, lead_org_a, welsh_lead_org
):
    """Succession rows are created with the correct type and date."""
    _run_command("--yes")
    succ = PaediatricDiabetesUnitSuccession.objects.get(
        predecessor__pz_code="PZ216", successor__pz_code="PZ253"
    )
    assert succ.succession_type == "merger"
    assert succ.succession_date == datetime.date(2025, 4, 1)


@pytest.mark.django_db
def test_never_participated_succession_is_closure(
    patched_constants, network_eoe, network_wales, lead_org_a, welsh_lead_org
):
    """Never-participated codes get succession_type='closure' with successor set."""
    _run_command("--yes")
    succ = PaediatricDiabetesUnitSuccession.objects.get(
        predecessor__pz_code="PZ013", successor__pz_code="PZ167"
    )
    assert succ.succession_type == "closure"
    assert succ.successor is not None


@pytest.mark.django_db
def test_predecessor_closed(
    patched_constants, network_eoe, network_wales, lead_org_a, welsh_lead_org
):
    """Predecessor PDUs are set active=False and get a closure version row."""
    _run_command("--yes")
    pz216 = PaediatricDiabetesUnit.objects.get(pz_code="PZ216")
    assert pz216.active is False
    # Closure version row from the succession date forward.
    closure = PaediatricDiabetesUnitVersion.objects.filter(
        paediatric_diabetes_unit=pz216, valid_from=datetime.date(2025, 4, 1)
    ).first()
    assert closure is not None
    assert closure.active is False
    assert closure.valid_to is None  # current state: inactive


# ---------------------------------------------------------------------------
# Lead-organisation reassignment
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_lead_org_reassigned_on_succession(
    patched_constants, network_eoe, network_wales, lead_org_a, welsh_lead_org
):
    """The predecessor's lead org is reassigned to the successor PDU."""
    _run_command("--yes")
    # The lead org (RWF01) should have two membership rows:
    # one closed on the succession date (-> PZ216), one open (-> PZ253).
    memberships = OrganisationPaediatricDiabetesUnitMembership.objects.filter(
        organisation__ods_code="RWF01"
    ).order_by("valid_from")
    assert memberships.count() == 2
    old, new = list(memberships)
    assert old.paediatric_diabetes_unit.pz_code == "PZ216"
    assert old.valid_to == datetime.date(2025, 4, 1)
    assert new.paediatric_diabetes_unit.pz_code == "PZ253"
    assert new.valid_from == datetime.date(2025, 4, 1)
    assert new.valid_to is None

    # The denormalised FK on the Organisation should point to the successor.
    lead_org_a.refresh_from_db()
    assert lead_org_a.paediatric_diabetes_unit.pz_code == "PZ253"


# ---------------------------------------------------------------------------
# As-of queries
# ---------------------------------------------------------------------------


def _pdu_as_of(ods_code, on_date):
    """Helper: which PDU was this organisation under on the given date?"""
    m = OrganisationPaediatricDiabetesUnitMembership.objects.filter(
        organisation__ods_code=ods_code,
        valid_from__lte=on_date,
    ).filter(
        Q(valid_to__gt=on_date) | Q(valid_to__isnull=True),
    ).first()
    return m.paediatric_diabetes_unit.pz_code if m else None


@pytest.mark.django_db
def test_as_of_query_before_and_after_merger(
    patched_constants, network_eoe, network_wales, lead_org_a, welsh_lead_org
):
    """As-of query returns the predecessor before the succession date and the successor after."""
    _run_command("--yes")
    # Before the merger (2025-04-01): RWF01 was under PZ216.
    assert _pdu_as_of("RWF01", datetime.date(2024, 1, 1)) == "PZ216"
    # After the merger: RWF01 is under PZ253.
    assert _pdu_as_of("RWF01", datetime.date(2025, 5, 1)) == "PZ253"
    assert _pdu_as_of("RWF01", datetime.date(2026, 1, 1)) == "PZ253"


@pytest.mark.django_db
def test_as_of_query_welsh_pdu(
    patched_constants, network_eoe, network_wales, lead_org_a, welsh_lead_org
):
    """Welsh PDU as-of query: Glangwili was under PZ056 before 2019, PZ244 after."""
    _run_command("--yes")
    assert _pdu_as_of("7A2AA", datetime.date(2018, 1, 1)) == "PZ056"
    assert _pdu_as_of("7A2AA", datetime.date(2019, 5, 1)) == "PZ244"
    assert _pdu_as_of("7A2AA", datetime.date(2026, 1, 1)) == "PZ244"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_idempotent(
    patched_constants, network_eoe, network_wales, lead_org_a, welsh_lead_org
):
    """Running the command twice does not duplicate rows."""
    _run_command("--yes")
    pdu_count = PaediatricDiabetesUnit.objects.count()
    version_count = PaediatricDiabetesUnitVersion.objects.count()
    succession_count = PaediatricDiabetesUnitSuccession.objects.count()
    membership_count = OrganisationPaediatricDiabetesUnitMembership.objects.count()
    network_membership_count = PaediatricDiabetesUnitNetworkMembership.objects.count()

    # Run again.
    _run_command("--yes")

    assert PaediatricDiabetesUnit.objects.count() == pdu_count
    assert PaediatricDiabetesUnitVersion.objects.count() == version_count
    assert PaediatricDiabetesUnitSuccession.objects.count() == succession_count
    assert (
        OrganisationPaediatricDiabetesUnitMembership.objects.count()
        == membership_count
    )
    assert (
        PaediatricDiabetesUnitNetworkMembership.objects.count()
        == network_membership_count
    )


# ---------------------------------------------------------------------------
# Network memberships
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_network_membership_written(
    patched_constants, network_eoe, network_lse, network_wales, lead_org_a, welsh_lead_org
):
    """Network membership rows are written for both historical and current states."""
    _run_command("--yes")
    pz216 = PaediatricDiabetesUnit.objects.get(pz_code="PZ216")
    memberships = PaediatricDiabetesUnitNetworkMembership.objects.filter(
        paediatric_diabetes_unit=pz216
    )
    assert memberships.count() >= 1
    assert memberships.first().paediatric_diabetes_network.name == "London & South East"
    # Verify the Welsh PDU's network membership is written too.
    pz244 = PaediatricDiabetesUnit.objects.get(pz_code="PZ244")
    welsh_membership = PaediatricDiabetesUnitNetworkMembership.objects.filter(
        paediatric_diabetes_unit=pz244
    ).first()
    assert welsh_membership is not None
    assert welsh_membership.paediatric_diabetes_network.name == "Wales"
