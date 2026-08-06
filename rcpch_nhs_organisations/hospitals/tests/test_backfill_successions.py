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
    TrustVersion,
    Organisation,
    OrganisationSuccession,
)

Trust = apps.get_model("hospitals", "Trust")
TrustSuccession = apps.get_model("hospitals", "TrustSuccession")
TrustVersion = apps.get_model("hospitals", "TrustVersion")
Organisation = apps.get_model("hospitals", "Organisation")
OrganisationSuccession = apps.get_model("hospitals", "OrganisationSuccession")


def _ods_record(ods_code, name, succs=None, legal_start=None, legal_end=None):
    """Build a minimal ODS organisation record with an optional Succs block.

    `legal_start` / `legal_end` populate the top-level `Date` block's Legal
    entry (used by the command to date the successor's pre-merger name
    backfill).
    """
    record = {
        "Name": name,
        "LastChangeDate": "2021-10-15",
        "GeoLoc": {"Location": {"AddrLn1": "1 St", "Town": "Town", "PostCode": "PC1"}},
        "Contacts": {"Contact": []},
    }
    if legal_start or legal_end:
        legal_date = {"Type": "Legal"}
        if legal_start:
            legal_date["Start"] = legal_start
        if legal_end:
            legal_date["End"] = legal_end
        record["Date"] = [legal_date]
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
    """When the operator answers 'y', the succession row is created AND the
    predecessor is closed (active=False from the succession date), with a
    closure TrustVersion row recording the change."""
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
    # The predecessor is closed.
    trust_a.refresh_from_db()
    assert trust_a.active is False
    # A closure TrustVersion row records active=False from the succession date.
    closure_version = TrustVersion.objects.get(
        trust=trust_a, valid_from=datetime.date(2021, 10, 1), valid_to=None
    )
    assert closure_version.active is False
    # The successor is untouched.
    trust_b.refresh_from_db()
    assert trust_b.active is True
    # The output mentions the closure.
    assert "close" in out.getvalue().lower() or "Closed" in out.getvalue()


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
    succession row is predecessor=target, successor=this entity, and the
    target (predecessor) is closed. The name prompt is answered with a blank
    (skip the name backfill)."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Predecessor", "RBB", "2021-10-01")],
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    # First input: the main y/n/s prompt ("y"). Second input: the pre-merger
    # name prompt (blank → skip name backfill).
    with _patch_get_organisation(records), patch(
        "builtins.input", side_effect=["y", ""]
    ):
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
    # The predecessor (trust_b) is closed.
    trust_b.refresh_from_db()
    assert trust_b.active is False
    # The successor (trust_a) is untouched.
    trust_a.refresh_from_db()
    assert trust_a.active is True
    # No name-change version row was written for the successor (blank input).
    assert TrustVersion.objects.filter(trust=trust_a).count() == 0


@pytest.mark.django_db
def test_non_dry_run_predecessor_type_backfills_successor_name(trust_a, trust_b):
    """For a 'Predecessor' event, if the operator supplies a pre-merger name
    for the successor and the ODS record has a Legal.Start date, a name-change
    version row is backfilled for the successor covering [establishment,
    merger_date)."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Predecessor", "RBB", "2021-10-01")],
            legal_start="1994-04-01",
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    # First input: "y" to the main prompt. Second input: the pre-merger name.
    with _patch_get_organisation(records), patch(
        "builtins.input", side_effect=["y", "Old Name A"]
    ):
        out = StringIO()
        call_command(
            "backfill_successions",
            "--entity", "trust",
            stdout=out,
            stderr=StringIO(),
        )
    # The succession row is created.
    row = TrustSuccession.objects.get()
    assert row.predecessor == trust_b
    assert row.successor == trust_a
    # The successor's pre-merger name is backfilled.
    name_row = TrustVersion.objects.get(
        trust=trust_a,
        valid_from=datetime.date(1994, 4, 1),
        valid_to=datetime.date(2021, 10, 1),
    )
    assert name_row.name == "Old Name A"
    assert name_row.active is True
    # The output mentions the name backfill.
    assert "Backfilled" in out.getvalue()
    assert "Old Name A" in out.getvalue()


@pytest.mark.django_db
def test_non_dry_run_predecessor_name_prompt_eof_skips_name_backfill(
    trust_a, trust_b
):
    """If stdin is closed (EOFError) at the name prompt, the name backfill is
    skipped but the succession row and predecessor closure still proceed."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Predecessor", "RBB", "2021-10-01")],
            legal_start="1994-04-01",
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    # First input: "y". Second input: EOFError at the name prompt.
    with _patch_get_organisation(records), patch(
        "builtins.input", side_effect=["y", EOFError()]
    ):
        call_command(
            "backfill_successions",
            "--entity", "trust",
            stdout=StringIO(),
            stderr=StringIO(),
        )
    # Succession row created, predecessor closed.
    assert TrustSuccession.objects.count() == 1
    trust_b.refresh_from_db()
    assert trust_b.active is False
    # No name-change version row for the successor.
    assert TrustVersion.objects.filter(trust=trust_a).count() == 0


@pytest.mark.django_db
def test_non_dry_run_successor_event_has_no_name_prompt(trust_a, trust_b):
    """A 'Successor' event (this entity was absorbed) does NOT prompt for a
    pre-merger name — this entity is the predecessor being closed, not the
    continuing entity. Only one input is consumed."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Successor", "RBB", "2021-10-01")],
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    # Only one input is expected; if the command prompted for a name, the
    # side_effect list would run out and raise StopIteration.
    with _patch_get_organisation(records), patch(
        "builtins.input", side_effect=["y"]
    ):
        call_command(
            "backfill_successions",
            "--entity", "trust",
            stdout=StringIO(),
            stderr=StringIO(),
        )
    assert TrustSuccession.objects.count() == 1
    # The predecessor (trust_a) is closed — a closure version row is written.
    # No name-change version row is written for either trust: trust_a is the
    # predecessor being closed (not renamed), and trust_b is the successor
    # but a Successor event does not prompt for the successor's pre-merger
    # name. A name-change row would be an active=True row covering a
    # pre-merger interval; assert none exists for either trust.
    assert not TrustVersion.objects.filter(
        trust__in=[trust_a, trust_b], active=True
    ).exists()
    # The closure row for trust_a is the only version row written.
    assert TrustVersion.objects.filter(trust=trust_a).count() == 1
    closure = TrustVersion.objects.get(trust=trust_a)
    assert closure.active is False
    assert closure.valid_from == datetime.date(2021, 10, 1)


@pytest.mark.django_db
def test_dry_run_predecessor_event_reports_name_prompt(trust_a, trust_b):
    """In --dry-run mode, a Predecessor event reports that it would prompt for
    the successor's pre-merger name."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Predecessor", "RBB", "2021-10-01")],
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
    assert "[dry-run] would create succession row" in output
    assert "[dry-run] would close" in output
    assert "[dry-run] would prompt for" in output
    assert "pre-merger name" in output
    # Nothing is actually written.
    assert TrustSuccession.objects.count() == 0


@pytest.mark.django_db
def test_non_dry_run_skips_closure_when_predecessor_already_inactive(trust_a, trust_b):
    """If the predecessor is already inactive, confirming 'y' creates the
    succession row but does NOT write a second closure version row or touch
    the entity row. This makes re-runs idempotent."""
    trust_a.active = False
    trust_a.save(update_fields=["active"])
    # Pre-existing closure version row (e.g. from a previous run or the admin).
    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2021, 10, 1),
        valid_to=None,
        name=trust_a.name,
        active=False,
    )
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
    # Only the pre-existing closure version row exists — no second one written.
    assert TrustVersion.objects.filter(trust=trust_a).count() == 1
    # The output notes the predecessor is already inactive.
    assert "already inactive" in out.getvalue()


@pytest.mark.django_db
def test_dry_run_reports_closure(trust_a, trust_b):
    """In --dry-run mode the output states it would close the predecessor."""
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
    assert "[dry-run] would create succession row" in output
    assert "[dry-run] would close" in output
    # Nothing is actually written.
    assert TrustSuccession.objects.count() == 0
    trust_a.refresh_from_db()
    assert trust_a.active is True


@pytest.mark.django_db
def test_non_dry_run_no_does_not_close(trust_a, trust_b):
    """Answering 'n' creates no succession row AND does not close the
    predecessor."""
    records = {
        "RAA": _ods_record(
            "RAA", "Trust A",
            succs=[_succ("Successor", "RBB", "2021-10-01")],
        ),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="n"):
        call_command(
            "backfill_successions",
            "--entity", "trust",
            stdout=StringIO(),
            stderr=StringIO(),
        )
    assert TrustSuccession.objects.count() == 0
    trust_a.refresh_from_db()
    assert trust_a.active is True
    assert TrustVersion.objects.filter(trust=trust_a).count() == 0


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
