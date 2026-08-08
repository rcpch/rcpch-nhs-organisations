"""
Tests for the backfill_icb_memberships management command.

The command iterates every trust in the database, fetches its full ODS
record, reads the Rels block for RE5/RE8 relationships pointing at ICBs
(RO261), and reports or creates missing TrustIntegratedCareBoardMembership
rows. CCG (RO210) and STP (RO132) targets are ignored. ODS network calls
are mocked so the tests are deterministic and offline.
"""
import datetime
from unittest.mock import patch

import pytest
from django.core.management import call_command
from io import StringIO

from rcpch_nhs_organisations.hospitals.models import (
    IntegratedCareBoard,
    Trust,
    TrustIntegratedCareBoardMembership,
)


# ---------------------------------------------------------------------------
# ODS record builders
# ---------------------------------------------------------------------------


def _icb_rel(target_ods_code, start, end=None, rel_id="RE5", target_role="RO261"):
    """Build a single Rels.Rel entry pointing at an ICB."""
    date = {"Type": "Operational", "Start": start}
    if end is not None:
        date["End"] = end
    return {
        "id": rel_id,
        "Status": "Active" if end is None else "Inactive",
        "Date": [date],
        "Target": {
            "OrgId": {"extension": target_ods_code},
            "PrimaryRoleId": {"id": target_role},
        },
    }


def _ods_record(ods_code, name, rels=None):
    """Build a minimal ODS organisation record with an optional Rels block."""
    record = {
        "Name": name,
        "Status": "Active",
        "GeoLoc": {"Location": {"AddrLn1": "1 St", "Town": "Town", "PostCode": "PC1"}},
        "Contacts": {"Contact": []},
    }
    if rels:
        record["Rels"] = {"Rel": rels}
    return record


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def trust_a():
    return Trust.objects.create(ods_code="RAA", name="Trust A")


@pytest.fixture
def icb_a():
    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000001",
        name="NHS Test ICB A",
        ods_code="QAA",
        active=True,
    )


@pytest.fixture
def icb_b():
    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000002",
        name="NHS Test ICB B",
        ods_code="QBB",
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
        "rcpch_nhs_organisations.hospitals.management.commands.backfill_icb_memberships.get_organisation",
        side_effect=fake_get_organisation,
    )


def _run_command(*args):
    out = StringIO()
    err = StringIO()
    call_command("backfill_icb_memberships", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dry_run_writes_nothing(trust_a, icb_a):
    """Dry-run mode reports what would change but writes nothing."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            rels=[_icb_rel("QAA", "2020-04-01")],
        ),
    }
    with _patch_get_organisation(records):
        out, _ = _run_command("--dry-run", "--all")
    assert "would backfill" in out
    assert TrustIntegratedCareBoardMembership.objects.count() == 0


@pytest.mark.django_db
def test_backfills_icb_membership(trust_a, icb_a):
    """The command creates a TrustIntegratedCareBoardMembership row from the ODS rel."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            rels=[_icb_rel("QAA", "2020-04-01")],
        ),
    }
    with _patch_get_organisation(records):
        _run_command("--yes", "--all")
    m = TrustIntegratedCareBoardMembership.objects.get(
        trust=trust_a, integrated_care_board=icb_a
    )
    assert m.valid_from == datetime.date(2020, 4, 1)
    assert m.valid_to is None  # open interval (current)


@pytest.mark.django_db
def test_backfills_historical_and_current(trust_a, icb_a, icb_b):
    """The command backfills both historical (closed) and current (open) memberships."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            rels=[
                _icb_rel("QAA", "2020-04-01", "2026-04-01"),  # closed
                _icb_rel("QBB", "2026-04-01"),                 # open (current)
            ],
        ),
    }
    with _patch_get_organisation(records):
        _run_command("--yes", "--all")
    old = TrustIntegratedCareBoardMembership.objects.get(
        trust=trust_a, integrated_care_board=icb_a
    )
    assert old.valid_from == datetime.date(2020, 4, 1)
    assert old.valid_to == datetime.date(2026, 4, 1)
    new = TrustIntegratedCareBoardMembership.objects.get(
        trust=trust_a, integrated_care_board=icb_b
    )
    assert new.valid_from == datetime.date(2026, 4, 1)
    assert new.valid_to is None


@pytest.mark.django_db
def test_ignores_ccg_and_stp_rels(trust_a, icb_a):
    """CCG (RO210) and STP (RO132) targets are ignored — only ICBs (RO261) are recovered."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            rels=[
                _icb_rel("Q01", "2002-04-01", "2006-06-30", target_role="RO132"),  # STP
                _icb_rel("Q56", "2014-09-01", "2015-03-31", target_role="RO210"),  # CCG
                _icb_rel("QAA", "2020-04-01", target_role="RO261"),                # ICB
            ],
        ),
    }
    with _patch_get_organisation(records):
        _run_command("--yes", "--all")
    # Only the ICB membership should exist.
    assert TrustIntegratedCareBoardMembership.objects.count() == 1
    m = TrustIntegratedCareBoardMembership.objects.get()
    assert m.integrated_care_board == icb_a


@pytest.mark.django_db
def test_handles_re8_rels(trust_a, icb_a):
    """RE8 rels (operates / is operated by) are also recovered, not just RE5."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            rels=[
                _icb_rel("QAA", "2020-04-01", "2023-06-30", rel_id="RE5"),
                _icb_rel("QAA", "2023-07-01", rel_id="RE8"),
            ],
        ),
    }
    with _patch_get_organisation(records):
        _run_command("--yes", "--all")
    # Both RE5 and RE8 point at the same ICB, so two rows are created
    # (with different intervals). This is correct — they represent
    # different operational periods.
    memberships = TrustIntegratedCareBoardMembership.objects.filter(
        trust=trust_a, integrated_care_board=icb_a
    ).order_by("valid_from")
    assert memberships.count() == 2
    assert memberships[0].valid_from == datetime.date(2020, 4, 1)
    assert memberships[0].valid_to == datetime.date(2023, 6, 30)
    assert memberships[1].valid_from == datetime.date(2023, 7, 1)
    assert memberships[1].valid_to is None


@pytest.mark.django_db
def test_skips_icb_not_in_database(trust_a):
    """If the ICB is not in the database, the row is skipped with a warning."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            rels=[_icb_rel("QXX", "2020-04-01")],
        ),
    }
    with _patch_get_organisation(records):
        out, _ = _run_command("--yes", "--all")
    assert "not in database" in out
    assert TrustIntegratedCareBoardMembership.objects.count() == 0


@pytest.mark.django_db
def test_idempotent(trust_a, icb_a):
    """Running the command twice does not duplicate rows."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            rels=[_icb_rel("QAA", "2020-04-01")],
        ),
    }
    with _patch_get_organisation(records):
        _run_command("--yes", "--all")
    count = TrustIntegratedCareBoardMembership.objects.count()
    with _patch_get_organisation(records):
        _run_command("--yes", "--all")
    assert TrustIntegratedCareBoardMembership.objects.count() == count


@pytest.mark.django_db
def test_since_window_filters_old_rels(trust_a, icb_a):
    """The --since window filters out memberships that ended before the window."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            rels=[
                _icb_rel("QAA", "2020-04-01", "2021-03-31"),  # ended before 2022
                _icb_rel("QAA", "2022-04-01"),                 # current
            ],
        ),
    }
    with _patch_get_organisation(records):
        _run_command("--yes", "--since", "2022-01-01")
    # Only the current membership (from 2022-04-01) should be backfilled.
    memberships = TrustIntegratedCareBoardMembership.objects.filter(
        trust=trust_a, integrated_care_board=icb_a
    )
    assert memberships.count() == 1
    assert memberships[0].valid_from == datetime.date(2022, 4, 1)


@pytest.mark.django_db
def test_no_rels_no_output(trust_a):
    """A trust with no ICB rels produces no output and no rows."""
    records = {
        "RAA": _ods_record("RAA", "Trust A"),
    }
    with _patch_get_organisation(records):
        out, _ = _run_command("--yes", "--all")
    assert "Trusts with ICB rels: 0" in out
    assert TrustIntegratedCareBoardMembership.objects.count() == 0
