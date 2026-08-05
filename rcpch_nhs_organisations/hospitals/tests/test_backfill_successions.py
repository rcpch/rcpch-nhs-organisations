"""
Tests for the backfill_successions management command.

The command iterates every entity in the database, fetches its full ODS
record, reads the Succs block, and reports or creates missing succession rows.
The ODS network calls are mocked so the tests are deterministic and offline.
"""
import datetime
from unittest.mock import patch

import pytest
from django.apps import apps
from django.core.management import call_command
from io import StringIO

from rcpch_nhs_organisations.hospitals.models import (
    Trust,
    TrustSuccession,
    Organisation,
    OrganisationSuccession,
    PaediatricDiabetesUnit,
    PaediatricDiabetesUnitSuccession,
)

Trust = apps.get_model("hospitals", "Trust")
TrustSuccession = apps.get_model("hospitals", "TrustSuccession")
Organisation = apps.get_model("hospitals", "Organisation")
OrganisationSuccession = apps.get_model("hospitals", "OrganisationSuccession")
PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")
PaediatricDiabetesUnitSuccession = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitSuccession"
)


def _ods_record(ods_code, name, succs=None):
    """Build a minimal ODS organisation record with an optional Succs block."""
    record = {
        "Name": name,
        "LastChangeDate": "2021-10-15",
        "GeoLoc": {"Location": {"AddrLn1": "1 St", "Town": "Town", "PostCode": "PC1"}},
        "Contacts": {"Contact": []},
    }
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
            "PrimaryRoleId": {"id": "RO197"},
        },
    }


@pytest.fixture
def trust_a():
    return Trust.objects.create(ods_code="RAA", name="Trust A")


@pytest.fixture
def trust_b():
    return Trust.objects.create(ods_code="RBB", name="Trust B")


@pytest.fixture
def trust_c():
    return Trust.objects.create(ods_code="RCC", name="Trust C")


def _patch_get_organisation(records_by_ods_code):
    """Patch get_organisation to return the given records without network calls."""
    def fake_get_organisation(org_link):
        # Extract the ODS code from the URL
        ods_code = org_link.rsplit("/", 1)[1]
        return records_by_ods_code[ods_code]

    return patch(
        "rcpch_nhs_organisations.hospitals.management.commands.backfill_successions.get_organisation",
        side_effect=fake_get_organisation,
    )


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dry_run_reports_missing_succession(trust_a, trust_b):
    """In dry-run mode, the command reports missing succession rows without
    creating them."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Successor", "RBB", "2021-10-01")],
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_successions",
            "--entity", "trust",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "RAA" in output
    assert "RBB" in output
    assert "Successor" in output
    assert "2021-10-01" in output
    assert "[dry-run]" in output
    # No succession row was created.
    assert TrustSuccession.objects.count() == 0


@pytest.mark.django_db
def test_dry_run_skips_existing_succession(trust_a, trust_b):
    """If a succession row already exists, the command does not report it."""
    TrustSuccession.objects.create(
        predecessor=trust_a,
        successor=trust_b,
        succession_date=datetime.date(2021, 10, 1),
        succession_type="acquisition",
    )
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Successor", "RBB", "2021-10-01")],
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_successions",
            "--entity", "trust",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "Found (missing): 0" in output
    assert TrustSuccession.objects.count() == 1


@pytest.mark.django_db
def test_dry_run_skips_target_not_in_database(trust_a):
    """If the succession target is not in the database, the command reports
    it as skipped."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Successor", "RZZ", "2021-10-01")],  # RZZ not in DB
        ),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_successions",
            "--entity", "trust",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "target not in database" in output
    assert "RZZ" in output


@pytest.mark.django_db
def test_dry_run_no_succession_events(trust_a):
    """If the ODS record has no Succs block, nothing is reported."""
    records = {"RAA": _ods_record("RAA", "Trust A")}
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_successions",
            "--entity", "trust",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "Found (missing): 0" in output


# ---------------------------------------------------------------------------
# Non-dry-run mode (interactive)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_non_dry_run_creates_succession_on_yes(trust_a, trust_b):
    """When the operator answers 'y', the succession row is created."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Successor", "RBB", "2021-10-01")],
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="y"):
        out = StringIO()
        call_command(
            "backfill_successions",
            "--entity", "trust",
            stdout=out,
            stderr=StringIO(),
        )
    assert TrustSuccession.objects.count() == 1
    row = TrustSuccession.objects.get()
    # "Successor" means trust_a was absorbed into trust_b.
    assert row.predecessor == trust_a
    assert row.successor == trust_b
    assert row.succession_date == datetime.date(2021, 10, 1)
    assert row.succession_type == "merger"  # placeholder
    assert "Backfilled from ODS Succs block" in row.notes


@pytest.mark.django_db
def test_non_dry_run_skips_on_no(trust_a, trust_b):
    """When the operator answers 'n', the succession row is not created."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Successor", "RBB", "2021-10-01")],
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="n"):
        out = StringIO()
        call_command(
            "backfill_successions",
            "--entity", "trust",
            stdout=out,
            stderr=StringIO(),
        )
    assert TrustSuccession.objects.count() == 0


@pytest.mark.django_db
def test_non_dry_run_skips_on_skip(trust_a, trust_b):
    """When the operator answers 's', the succession row is not created."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Successor", "RBB", "2021-10-01")],
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="s"):
        out = StringIO()
        call_command(
            "backfill_successions",
            "--entity", "trust",
            stdout=out,
            stderr=StringIO(),
        )
    assert TrustSuccession.objects.count() == 0


@pytest.mark.django_db
def test_non_dry_run_predecessor_type(trust_a, trust_b):
    """For a 'Predecessor' event (this entity absorbed the target), the
    succession row is predecessor=target, successor=this entity."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Predecessor", "RBB", "2021-10-01")],
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="y"):
        call_command(
            "backfill_successions",
            "--entity", "trust",
            stdout=StringIO(),
            stderr=StringIO(),
        )
    row = TrustSuccession.objects.get()
    # "Predecessor" means trust_a absorbed trust_b.
    assert row.predecessor == trust_b
    assert row.successor == trust_a


@pytest.mark.django_db
def test_non_dry_run_eoferror_skips(trust_a, trust_b):
    """If stdin is closed (EOFError), the succession row is skipped."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Successor", "RBB", "2021-10-01")],
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    with _patch_get_organisation(records), patch("builtins.input", side_effect=EOFError):
        call_command(
            "backfill_successions",
            "--entity", "trust",
            stdout=StringIO(),
            stderr=StringIO(),
        )
    assert TrustSuccession.objects.count() == 0


# ---------------------------------------------------------------------------
# Entity types
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_organisation_entity():
    """The command works for organisations."""
    org_a = Organisation.objects.create(ods_code="RAA01", name="Org A")
    org_b = Organisation.objects.create(ods_code="RBB01", name="Org B")
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            succs=[_succ("Successor", "RBB01", "2021-10-01")],
        ),
        "RBB01": _ods_record("RBB01", "Org B"),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_successions",
            "--entity", "organisation",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "RAA01" in output
    assert "Found (missing): 1" in output


@pytest.mark.django_db
def test_pdu_entity():
    """The command works for paediatric diabetes units."""
    pdu_a = PaediatricDiabetesUnit.objects.create(pz_code="PZ001")
    pdu_b = PaediatricDiabetesUnit.objects.create(pz_code="PZ002")
    records = {
        "PZ001": _ods_record(
            "PZ001", "PZ001",
            succs=[_succ("Successor", "PZ002", "2021-10-01")],
        ),
        "PZ002": _ods_record("PZ002", "PZ002"),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_successions",
            "--entity", "pdu",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "PZ001" in output
    assert "Found (missing): 1" in output


@pytest.mark.django_db
def test_invalid_entity_rejected():
    """An invalid --entity value is rejected."""
    from django.core.management import CommandError

    with pytest.raises(CommandError):
        call_command(
            "backfill_successions",
            "--entity", "invalid",
            "--dry-run",
            stdout=StringIO(),
            stderr=StringIO(),
        )


# ---------------------------------------------------------------------------
# Multiple succession events
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_multiple_succession_events(trust_a, trust_b, trust_c):
    """An entity with multiple succession events (e.g. a split) produces
    multiple succession rows."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[
                _succ("Successor", "RBB", "2021-10-01"),
                _succ("Successor", "RCC", "2021-10-01"),
            ],
        ),
        "RBB": _ods_record("RBB", "Trust B"),
        "RCC": _ods_record("RCC", "Trust C"),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="y"):
        call_command(
            "backfill_successions",
            "--entity", "trust",
            stdout=StringIO(),
            stderr=StringIO(),
        )
    assert TrustSuccession.objects.count() == 2
    # Both rows have trust_a as predecessor (it was absorbed into both).
    rows = TrustSuccession.objects.filter(predecessor=trust_a)
    assert {r.successor for r in rows} == {trust_b, trust_c}
