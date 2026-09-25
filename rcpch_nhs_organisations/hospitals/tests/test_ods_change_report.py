"""
Tests for the ods_change_report management command, which runs the three ODS
change-detection dry-run checks and prints a combined markdown report between
sentinel markers, for the GitHub workflow to extract from the Container Apps
job console logs.

The ODS network calls are mocked so the tests are deterministic and offline.
"""
import datetime
from contextlib import ExitStack
from io import StringIO
from unittest.mock import patch

import pytest
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError

from rcpch_nhs_organisations.hospitals.management.commands.ods_change_report import (
    REPORT_END_MARKER,
    REPORT_START_MARKER,
)

Trust = apps.get_model("hospitals", "Trust")
TrustVersion = apps.get_model("hospitals", "TrustVersion")

ODS_UPDATE_MODULE = (
    "rcpch_nhs_organisations.hospitals.general_functions.ods_update"
)
BACKFILL_COMMAND_MODULE = (
    "rcpch_nhs_organisations.hospitals.management.commands.backfill_successions"
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


def _matching_record(trust):
    """Build an ODS record that matches the trust row, so the cron dry-run
    finds no changes for it."""
    return {
        "Name": trust.name,
        "GeoLoc": {
            "Location": {
                "AddrLn1": trust.address_line_1,
                "Town": trust.town,
                "PostCode": trust.postcode,
            }
        },
        "Contacts": {"Contact": []},
    }


def _patch_ods(records_by_ods_code, org_links):
    """Patch the ODS network functions used by all three checks.

    Unknown ODS codes (e.g. the ICBs seeded by data migrations) get an empty
    record with no Succs block, so the succession backfill skips them."""
    def fake_get_organisation(org_link):
        ods_code = org_link.rsplit("/", 1)[1]
        return records_by_ods_code.get(ods_code) or _ods_record(
            ods_code, f"Organisation {ods_code}"
        )

    stack = ExitStack()
    stack.enter_context(patch(
        f"{ODS_UPDATE_MODULE}.fetch_updated_organisations",
        lambda time_frame=30: org_links,
    ))
    stack.enter_context(patch(
        f"{ODS_UPDATE_MODULE}.get_organisation",
        side_effect=fake_get_organisation,
    ))
    stack.enter_context(patch(
        f"{BACKFILL_COMMAND_MODULE}.get_organisation",
        side_effect=fake_get_organisation,
    ))
    return stack


@pytest.fixture
def trust_a():
    return Trust.objects.create(ods_code="RAA", name="Old Trust Name", active=True)


@pytest.fixture
def trust_b():
    return Trust.objects.create(ods_code="RBB", name="Trust B", active=True)


@pytest.fixture
def baselines(trust_a, trust_b):
    for trust in (trust_a, trust_b):
        TrustVersion.objects.create(
            trust=trust,
            valid_from=datetime.date(2020, 1, 1),
            valid_to=None,
            name=trust.name,
            active=True,
        )


def _extract_report(output):
    """Return the text between the sentinel markers."""
    start = output.index(REPORT_START_MARKER) + len(REPORT_START_MARKER)
    end = output.index(REPORT_END_MARKER)
    return output[start:end]


# ---------------------------------------------------------------------------
# Combined report
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_combined_report_printed_between_markers(trust_a, trust_b, baselines):
    """Findings from both the ODS sync and the trust succession backfill are
    combined under section headings between the sentinel markers."""
    records = {
        # Name change: the ODS sync dry-run reports it.
        "RAA": _ods_record("RAA", "New Trust Name"),
        # Succession event pointing at RAA with no succession row: the trust
        # succession backfill dry-run reports it.
        "RBB": _ods_record(
            "RBB", "Trust B",
            succs=[_succ("Successor", "RAA", "2021-10-01")],
        ),
    }
    org_links = [
        {"OrgLink": "https://ods.example/Organisation/RAA"},
        {"OrgLink": "https://ods.example/Organisation/RBB"},
    ]
    out = StringIO()
    with _patch_ods(records, org_links):
        call_command("ods_change_report", stdout=out, stderr=StringIO())
    report = _extract_report(out.getvalue())
    assert "## ODS sync changes (trusts + organisations)" in report
    assert "## Trust succession backfill" in report
    assert "New Trust Name" in report
    assert "would create succession row" in report


@pytest.mark.django_db
def test_no_changes_prints_empty_report(trust_a, trust_b, baselines):
    """When no check finds anything, the text between the markers is empty,
    so the workflow does not open an issue."""
    records = {
        "RAA": _matching_record(trust_a),
        "RBB": _matching_record(trust_b),
    }
    org_links = [
        {"OrgLink": "https://ods.example/Organisation/RAA"},
        {"OrgLink": "https://ods.example/Organisation/RBB"},
    ]
    out = StringIO()
    with _patch_ods(records, org_links):
        call_command("ods_change_report", stdout=out, stderr=StringIO())
    assert _extract_report(out.getvalue()).strip() == ""


# ---------------------------------------------------------------------------
# Blob upload
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_report_uploaded_to_blob(trust_a, trust_b, baselines, monkeypatch):
    """When ODS_REPORT_STORAGE_ACCOUNT_NAME is set, the combined report is
    uploaded to the configured blob — even when empty, so a successful run
    always overwrites any previous report."""
    pytest.importorskip("azure.storage.blob")
    from azure import identity as azure_identity
    from azure.storage import blob as azure_blob

    uploaded = {}

    class FakeBlobClient:
        def __init__(self, account_url, container_name, blob_name, credential):
            uploaded["account_url"] = account_url
            uploaded["container_name"] = container_name
            uploaded["blob_name"] = blob_name

        def upload_blob(self, data, overwrite=False):
            uploaded["data"] = data
            uploaded["overwrite"] = overwrite

    monkeypatch.setattr(azure_blob, "BlobClient", FakeBlobClient)
    monkeypatch.setattr(azure_identity, "DefaultAzureCredential", lambda: "credential")
    monkeypatch.setenv("ODS_REPORT_STORAGE_ACCOUNT_NAME", "rcpchodsreports")

    records = {
        "RAA": _matching_record(trust_a),
        "RBB": _matching_record(trust_b),
    }
    org_links = [
        {"OrgLink": "https://ods.example/Organisation/RAA"},
        {"OrgLink": "https://ods.example/Organisation/RBB"},
    ]
    out = StringIO()
    with _patch_ods(records, org_links):
        call_command("ods_change_report", stdout=out, stderr=StringIO())

    assert uploaded["account_url"] == "https://rcpchodsreports.blob.core.windows.net"
    assert uploaded["container_name"] == "ods-change-reports"
    assert uploaded["blob_name"] == "ods-change-report.md"
    assert uploaded["overwrite"] is True


# ---------------------------------------------------------------------------
# Check failures
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_check_failure_raises_command_error_and_reports_it(
    trust_a, trust_b, baselines
):
    """If one check raises, the remaining checks still run, the failure is
    reported in a Check failures section, and the command exits non-zero so
    the job execution is marked Failed."""
    records = {
        "RAA": _ods_record("RAA", "Old Trust Name"),
        "RBB": _ods_record("RBB", "Trust B"),
    }
    org_links = [{"OrgLink": "https://ods.example/Organisation/RAA"}]
    out = StringIO()
    with _patch_ods(records, org_links):
        with patch(
            f"{ODS_UPDATE_MODULE}.fetch_updated_organisations",
            side_effect=RuntimeError("ODS API unavailable"),
        ):
            with pytest.raises(CommandError):
                call_command("ods_change_report", stdout=out, stderr=StringIO())
    output = out.getvalue()
    assert REPORT_START_MARKER in output
    assert REPORT_END_MARKER in output
    assert "## Check failures" in output
    assert "ODS API unavailable" in output