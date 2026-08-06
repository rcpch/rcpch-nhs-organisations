"""
Tests for the backfill_trust_memberships management command.

The command iterates every organisation in the database, fetches its full ODS
record, reads the Rels block for RE6 (is-a-site-of) relationships, and reports
or creates missing OrganisationTrustMembership rows. The ODS network calls are
mocked so the tests are deterministic and offline.
"""
import datetime
from unittest.mock import patch

import pytest
from django.core.management import call_command
from io import StringIO

from rcpch_nhs_organisations.hospitals.models import (
    Organisation,
    OrganisationTrustMembership,
    Trust,
)


# ---------------------------------------------------------------------------
# ODS record builders
# ---------------------------------------------------------------------------


def _rel(target_ods_code, start, end=None, rel_id="RE6", target_role="RO197"):
    """Build a single Rels.Rel entry.

    Defaults to RE6 (is-a-site-of) pointing at an NHS Trust (RO197), which is
    the only rel type the command cares about.
    """
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
        "LastChangeDate": "2021-10-15",
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
def trust_b():
    return Trust.objects.create(ods_code="RBB", name="Trust B")


@pytest.fixture
def org_a():
    return Organisation.objects.create(ods_code="RAA01", name="Org A", active=True)


@pytest.fixture
def org_b():
    return Organisation.objects.create(ods_code="RBB01", name="Org B", active=True)


def _patch_get_organisation(records_by_ods_code):
    """Patch get_organisation to return the given records without network calls."""
    def fake_get_organisation(org_link):
        ods_code = org_link.rsplit("/", 1)[1]
        return records_by_ods_code[ods_code]

    return patch(
        "rcpch_nhs_organisations.hospitals.management.commands.backfill_trust_memberships.get_organisation",
        side_effect=fake_get_organisation,
    )


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dry_run_reports_missing_membership(trust_a, org_a):
    """In dry-run mode, the command reports missing membership rows without
    creating them."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("RAA", "2010-04-01")],
        ),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--dry-run",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "RAA01" in output
    assert "RAA" in output
    assert "would backfill membership row" in output
    assert OrganisationTrustMembership.objects.count() == 0


@pytest.mark.django_db
def test_dry_run_skips_existing_membership(trust_a, org_a):
    """If a membership row already exists for the same interval, the command
    does not report it."""
    OrganisationTrustMembership.objects.create(
        organisation=org_a,
        trust=trust_a,
        valid_from=datetime.date(2010, 4, 1),
        valid_to=None,
    )
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("RAA", "2010-04-01")],
        ),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--dry-run",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "Found (missing): 0" in output


@pytest.mark.django_db
def test_dry_run_skips_trust_not_in_database(org_a):
    """If the RE6 target trust is not in the database, the command reports
    it as skipped (the operator should run backfill_successions first)."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("RZZ", "2010-04-01")],  # RZZ not in DB
        ),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--dry-run",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "trust not in database" in output
    assert "backfill_successions" in output
    assert OrganisationTrustMembership.objects.count() == 0


@pytest.mark.django_db
def test_dry_run_no_rels_block(org_a):
    """If the ODS record has no Rels block, nothing is reported."""
    records = {"RAA01": _ods_record("RAA01", "Org A")}
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--dry-run",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "Found (missing): 0" in output


@pytest.mark.django_db
def test_dry_run_ignores_non_re6_rels(trust_a, org_a):
    """RE5 (managed-by, e.g. ICB commissioning) rels are not trust memberships
    and must be ignored."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("QOP", "2020-04-01", rel_id="RE5", target_role="RO261")],
        ),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--dry-run",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "Found (missing): 0" in output


@pytest.mark.django_db
def test_dry_run_ignores_non_trust_re6_targets(org_a):
    """An RE6 rel pointing at a non-RO197 target (e.g. a Welsh LHB) is not
    a trust membership and must be ignored."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("W110", "2010-04-01", target_role="RO142")],
        ),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--dry-run",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "Found (missing): 0" in output


@pytest.mark.django_db
def test_dry_run_since_window_filters_old_memberships(trust_a, org_a):
    """A membership that ended before the --since window is out of scope and
    is not reported."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("RAA", "2005-04-01", end="2010-04-01")],
        ),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--dry-run",
            "--since", "2020-01-01",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "Found (missing): 0" in output


@pytest.mark.django_db
def test_dry_run_since_window_includes_overlapping_memberships(trust_a, org_a):
    """A membership that started before the --since window but is still open
    (valid_to=None) overlaps the window and is reported."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("RAA", "2010-04-01")],  # open interval
        ),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--dry-run",
            "--since", "2020-01-01",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "Found (missing): 1" in output


# ---------------------------------------------------------------------------
# Non-dry-run mode
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_non_dry_run_creates_membership_on_yes(trust_a, org_a):
    """When the operator answers 'y', the membership row is created."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("RAA", "2010-04-01")],
        ),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="y"):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    membership = OrganisationTrustMembership.objects.get(
        organisation=org_a, trust=trust_a
    )
    assert membership.valid_from == datetime.date(2010, 4, 1)
    assert membership.valid_to is None
    assert "Backfilled: 1" in out.getvalue()


@pytest.mark.django_db
def test_non_dry_run_skips_on_no(trust_a, org_a):
    """When the operator answers 'n', the membership row is not created."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("RAA", "2010-04-01")],
        ),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="n"):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    assert OrganisationTrustMembership.objects.count() == 0
    assert "Skipped/refused: 1" in out.getvalue()


@pytest.mark.django_db
def test_non_dry_run_skips_on_skip(trust_a, org_a):
    """When the operator answers 's', the membership row is not created."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("RAA", "2010-04-01")],
        ),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="s"):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    assert OrganisationTrustMembership.objects.count() == 0
    assert "Skipped/refused: 1" in out.getvalue()


@pytest.mark.django_db
def test_non_dry_run_eoferror_skips(trust_a, org_a):
    """If stdin is closed (EOFError), the membership is skipped."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("RAA", "2010-04-01")],
        ),
    }
    with _patch_get_organisation(records), patch("builtins.input", side_effect=EOFError):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    assert OrganisationTrustMembership.objects.count() == 0
    assert "Skipped/refused: 1" in out.getvalue()


@pytest.mark.django_db
def test_non_dry_run_is_idempotent(trust_a, org_a):
    """Re-running the command does not duplicate membership rows."""
    OrganisationTrustMembership.objects.create(
        organisation=org_a,
        trust=trust_a,
        valid_from=datetime.date(2010, 4, 1),
        valid_to=None,
    )
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("RAA", "2010-04-01")],
        ),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    assert OrganisationTrustMembership.objects.count() == 1
    assert "Found (missing): 0" in out.getvalue()


@pytest.mark.django_db
def test_non_dry_run_creates_closed_membership(trust_a, trust_b, org_a):
    """A historical (closed) membership interval is backfilled with valid_to
    set, recording that the org was under trust_a before it moved to
    trust_b."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[
                _rel("RAA", "2005-04-01", end="2018-04-01"),  # old, closed
                _rel("RBB", "2018-04-01"),                    # current, open
            ],
        ),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="y"):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    memberships = OrganisationTrustMembership.objects.filter(organisation=org_a)
    assert memberships.count() == 2
    old = memberships.get(trust=trust_a)
    new = memberships.get(trust=trust_b)
    assert old.valid_from == datetime.date(2005, 4, 1)
    assert old.valid_to == datetime.date(2018, 4, 1)
    assert new.valid_from == datetime.date(2018, 4, 1)
    assert new.valid_to is None
    assert "Backfilled: 2" in out.getvalue()


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_all_and_since_are_mutually_exclusive(trust_a, org_a):
    """--all and --since cannot be used together."""
    records = {"RAA01": _ods_record("RAA01", "Org A")}
    with _patch_get_organisation(records):
        out = StringIO()
        with pytest.raises(Exception) as exc:
            call_command(
                "backfill_trust_memberships",
                "--all",
                "--since", "2020-01-01",
                stdout=out,
                stderr=StringIO(),
            )
    assert "mutually exclusive" in str(exc.value)


@pytest.mark.django_db
def test_invalid_since_date_rejected(trust_a, org_a):
    """--since must be a valid YYYY-MM-DD date."""
    records = {"RAA01": _ods_record("RAA01", "Org A")}
    with _patch_get_organisation(records):
        out = StringIO()
        with pytest.raises(Exception) as exc:
            call_command(
                "backfill_trust_memberships",
                "--since", "not-a-date",
                stdout=out,
                stderr=StringIO(),
            )
    assert "YYYY-MM-DD" in str(exc.value)


@pytest.mark.django_db
def test_limit_argument(trust_a, org_a, org_b):
    """--limit caps the number of organisations processed."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[_rel("RAA", "2010-04-01")],
        ),
        "RBB01": _ods_record(
            "RBB01", "Org B",
            rels=[_rel("RAA", "2010-04-01")],
        ),
    }
    with _patch_get_organisation(records):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--dry-run",
            "--all",
            "--limit", "1",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert "Organisations processed: 1" in output


# ---------------------------------------------------------------------------
# Multiple memberships / edge cases
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_multiple_rels_for_one_org(trust_a, trust_b, org_a):
    """An organisation with multiple RE6 rels (a chain of trust memberships)
    has all of them backfilled in one run."""
    records = {
        "RAA01": _ods_record(
            "RAA01", "Org A",
            rels=[
                _rel("RAA", "2005-04-01", end="2018-04-01"),
                _rel("RBB", "2018-04-01"),
            ],
        ),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="y"):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    assert OrganisationTrustMembership.objects.filter(organisation=org_a).count() == 2
    assert "Backfilled: 2" in out.getvalue()


@pytest.mark.django_db
def test_rel_with_no_operational_date_falls_back_to_legal(trust_a, org_a):
    """If a rel has no Operational date, the command falls back to the Legal
    interval (some older ODS records only carry the Legal interval)."""
    legal_rel = {
        "id": "RE6",
        "Status": "Active",
        "Date": [{"Type": "Legal", "Start": "2010-04-01"}],
        "Target": {
            "OrgId": {"extension": "RAA"},
            "PrimaryRoleId": {"id": "RO197"},
        },
    }
    records = {
        "RAA01": _ods_record("RAA01", "Org A", rels=[legal_rel]),
    }
    with _patch_get_organisation(records), patch("builtins.input", return_value="y"):
        out = StringIO()
        call_command(
            "backfill_trust_memberships",
            "--all",
            stdout=out,
            stderr=StringIO(),
        )
    membership = OrganisationTrustMembership.objects.get(
        organisation=org_a, trust=trust_a
    )
    assert membership.valid_from == datetime.date(2010, 4, 1)
    assert membership.valid_to is None
