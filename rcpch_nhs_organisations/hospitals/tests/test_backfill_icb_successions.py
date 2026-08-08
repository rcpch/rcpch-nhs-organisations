"""
Tests for the ICB succession backfill (backfill_successions --entity icb).

The command reads the ODS Succs block for each ICB and creates
IntegratedCareBoardSuccession rows, creates missing successor ICBs from
the ODS record, closes predecessors, and auto-classifies known
acquisitions via KNOWN_ICB_ACQUISITIONS.

ODS network calls are mocked so the tests are deterministic and offline.
"""
import datetime
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db.models import Q

from rcpch_nhs_organisations.hospitals.models import (
    IntegratedCareBoard,
    IntegratedCareBoardSuccession,
    IntegratedCareBoardVersion,
)


# ---------------------------------------------------------------------------
# ODS record helpers
# ---------------------------------------------------------------------------


def _icb_ods_record(ods_code, name, succs=None, legal_start=None):
    """Build a minimal ODS record for an ICB with an optional Succs block."""
    record = {
        "Name": name,
        "Status": "Active",
        "GeoLoc": {"Location": {"AddrLn1": "1 St", "Town": "Town", "PostCode": "PC1"}},
        "Contacts": {"Contact": []},
    }
    if legal_start:
        record["Date"] = [{"Type": "Legal", "Start": legal_start}]
    if succs:
        record["Succs"] = {"Succ": succs}
    return record


def _succ(type_, target_ods_code, date):
    """Build a single Succs entry."""
    return {
        "Type": type_,
        "Date": [{"Type": "Legal", "Start": date}],
        "Target": {
            "OrgId": {"extension": target_ods_code},
            "PrimaryRoleId": {"id": "RO261"},
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def icb_a():
    """An existing ICB that will be dissolved (predecessor)."""
    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000001",
        name="NHS Test ICB A",
        ods_code="QAA",
        active=True,
    )


@pytest.fixture
def icb_b():
    """Another existing ICB that will be dissolved (predecessor)."""
    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000002",
        name="NHS Test ICB B",
        ods_code="QBB",
        active=True,
    )


@pytest.fixture
def icb_existing():
    """An existing ICB that gains territory (successor in an acquisition)."""
    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000003",
        name="NHS Test ICB Existing",
        ods_code="QCC",
        active=True,
    )


@pytest.fixture
def icb_a_version(icb_a):
    return IntegratedCareBoardVersion.objects.create(
        integrated_care_board=icb_a,
        valid_from=datetime.date(2022, 7, 1),
        valid_to=None,
        name="NHS Test ICB A",
        active=True,
    )


@pytest.fixture
def icb_b_version(icb_b):
    return IntegratedCareBoardVersion.objects.create(
        integrated_care_board=icb_b,
        valid_from=datetime.date(2022, 7, 1),
        valid_to=None,
        name="NHS Test ICB B",
        active=True,
    )


@pytest.fixture
def icb_existing_version(icb_existing):
    return IntegratedCareBoardVersion.objects.create(
        integrated_care_board=icb_existing,
        valid_from=datetime.date(2022, 7, 1),
        valid_to=None,
        name="NHS Test ICB Existing",
        active=True,
    )


def _patch_get_organisation(records_by_ods_code):
    """Patch get_organisation to return the given records without network calls."""
    def fake_get_organisation(org_link):
        ods_code = org_link.rsplit("/", 1)[1]
        return records_by_ods_code.get(ods_code, {
            "Name": ods_code,
            "Status": "Active",
            "GeoLoc": {"Location": {"AddrLn1": "1 St", "Town": "Town", "PostCode": "PC1"}},
            "Contacts": {"Contact": []},
        })

    return patch(
        "rcpch_nhs_organisations.hospitals.management.commands.backfill_successions.get_organisation",
        side_effect=fake_get_organisation,
    )


def _run_command(*args):
    out = StringIO()
    err = StringIO()
    call_command("backfill_successions", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dry_run_writes_nothing(icb_a, icb_a_version):
    """Dry-run mode reports what would change but writes nothing."""
    records = {
        "QAA": _icb_ods_record(
            "QAA", "NHS Test ICB A",
            succs=[_succ("Successor", "S1NEW", "2026-04-01")],
        ),
        "S1NEW": _icb_ods_record(
            "S1NEW", "NHS New ICB",
            legal_start="2026-04-01",
        ),
    }
    with _patch_get_organisation(records):
        out, _ = _run_command("--entity", "icb", "--dry-run")
    assert "would create" in out or "target not in database" in out
    assert IntegratedCareBoardSuccession.objects.count() == 0
    # No new ICBs created.
    assert IntegratedCareBoard.objects.filter(ods_code="S1NEW").exists() is False


@pytest.mark.django_db
def test_creates_missing_successor_icb(icb_a, icb_a_version):
    """The command creates missing successor ICBs from the ODS record."""
    records = {
        "QAA": _icb_ods_record(
            "QAA", "NHS Test ICB A",
            succs=[_succ("Successor", "S1NEW", "2026-04-01")],
        ),
        "S1NEW": _icb_ods_record(
            "S1NEW", "NHS New ICB",
            legal_start="2026-04-01",
        ),
    }
    with _patch_get_organisation(records):
        _run_command("--entity", "icb", "--yes")
    new_icb = IntegratedCareBoard.objects.get(ods_code="S1NEW")
    assert new_icb.name == "NHS New ICB"
    assert new_icb.active is True
    # Should have a baseline version row.
    assert IntegratedCareBoardVersion.objects.filter(
        integrated_care_board=new_icb
    ).count() >= 1


@pytest.mark.django_db
def test_succession_row_created(icb_a, icb_a_version):
    """Succession rows are created with the correct type and date."""
    records = {
        "QAA": _icb_ods_record(
            "QAA", "NHS Test ICB A",
            succs=[_succ("Successor", "S1NEW", "2026-04-01")],
        ),
        "S1NEW": _icb_ods_record(
            "S1NEW", "NHS New ICB",
            legal_start="2026-04-01",
        ),
    }
    with _patch_get_organisation(records):
        _run_command("--entity", "icb", "--yes")
    succ = IntegratedCareBoardSuccession.objects.get(
        predecessor__ods_code="QAA",
        successor__ods_code="S1NEW",
    )
    assert succ.succession_type == "merger"
    assert succ.succession_date == datetime.date(2026, 4, 1)


@pytest.mark.django_db
def test_predecessor_closed(icb_a, icb_a_version):
    """Predecessor ICBs are set active=False and get a closure version row."""
    records = {
        "QAA": _icb_ods_record(
            "QAA", "NHS Test ICB A",
            succs=[_succ("Successor", "S1NEW", "2026-04-01")],
        ),
        "S1NEW": _icb_ods_record(
            "S1NEW", "NHS New ICB",
            legal_start="2026-04-01",
        ),
    }
    with _patch_get_organisation(records):
        _run_command("--entity", "icb", "--yes")
    icb_a.refresh_from_db()
    assert icb_a.active is False
    closure = IntegratedCareBoardVersion.objects.filter(
        integrated_care_board=icb_a,
        valid_from=datetime.date(2026, 4, 1),
    ).first()
    assert closure is not None
    assert closure.active is False
    assert closure.valid_to is None


@pytest.mark.django_db
def test_known_icb_acquisition_auto_classified(
    icb_a, icb_existing, icb_a_version, icb_existing_version
):
    """QRL-style acquisitions are auto-classified as 'acquisition' via
    KNOWN_ICB_ACQUISITIONS."""
    # Patch KNOWN_ICB_ACQUISITIONS to match our test codes.
    with patch(
        "rcpch_nhs_organisations.hospitals.management.commands.backfill_successions."
        "lookup_known_icb_acquisition"
    ) as mock_lookup:
        mock_lookup.return_value = {
            "successor_ods_code": "QCC",
            "succession_date": datetime.date(2026, 4, 1),
            "legal_start": datetime.date(2022, 7, 1),
            "notes": "test acquisition",
        }
        records = {
            "QAA": _icb_ods_record(
                "QAA", "NHS Test ICB A",
                succs=[_succ("Successor", "QCC", "2026-04-01")],
            ),
            "QCC": _icb_ods_record(
                "QCC", "NHS Test ICB Existing",
            ),
        }
        with _patch_get_organisation(records):
            _run_command("--entity", "icb", "--yes")
    succ = IntegratedCareBoardSuccession.objects.get(
        predecessor__ods_code="QAA",
        successor__ods_code="QCC",
    )
    assert succ.succession_type == "acquisition"


@pytest.mark.django_db
def test_split_creates_multiple_succession_rows(
    icb_a, icb_a_version, icb_b, icb_b_version
):
    """A split (one predecessor → multiple successors) creates multiple rows."""
    records = {
        "QAA": _icb_ods_record(
            "QAA", "NHS Test ICB A",
            succs=[
                _succ("Successor", "S1NEW", "2026-04-01"),
                _succ("Successor", "S2NEW", "2026-04-01"),
            ],
        ),
        "S1NEW": _icb_ods_record(
            "S1NEW", "NHS New ICB 1",
            legal_start="2026-04-01",
        ),
        "S2NEW": _icb_ods_record(
            "S2NEW", "NHS New ICB 2",
            legal_start="2026-04-01",
        ),
    }
    with _patch_get_organisation(records):
        _run_command("--entity", "icb", "--yes")
    succs = IntegratedCareBoardSuccession.objects.filter(
        predecessor__ods_code="QAA"
    )
    assert succs.count() == 2
    assert {s.successor.ods_code for s in succs} == {"S1NEW", "S2NEW"}


@pytest.mark.django_db
def test_idempotent(icb_a, icb_a_version):
    """Running the command twice does not duplicate rows."""
    records = {
        "QAA": _icb_ods_record(
            "QAA", "NHS Test ICB A",
            succs=[_succ("Successor", "S1NEW", "2026-04-01")],
        ),
        "S1NEW": _icb_ods_record(
            "S1NEW", "NHS New ICB",
            legal_start="2026-04-01",
        ),
    }
    with _patch_get_organisation(records):
        _run_command("--entity", "icb", "--yes")
    succ_count = IntegratedCareBoardSuccession.objects.count()
    icb_count = IntegratedCareBoard.objects.count()
    version_count = IntegratedCareBoardVersion.objects.count()

    with _patch_get_organisation(records):
        _run_command("--entity", "icb", "--yes")
    assert IntegratedCareBoardSuccession.objects.count() == succ_count
    assert IntegratedCareBoard.objects.count() == icb_count
    # Version count may increase by establishment rows in Pass 2, but
    # no duplicate succession or ICB rows.


@pytest.mark.django_db
def test_icb_entity_accepted():
    """The --entity icb argument is accepted."""
    out, _ = _run_command("--entity", "icb", "--dry-run")
    assert "Backfilling successions for" in out
    assert "icb" in out
