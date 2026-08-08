"""
Tests for the cron management command's --report-file flag, used by the GitHub
Action for ODS change detection.

The --report-file flag writes the dry-run markdown report to a file instead of
stdout, so the GitHub Action can detect empty (no changes) vs non-empty
(changes detected) without stdout pollution from the ASCII art / status
messages.
"""
import datetime
import os
import tempfile

import pytest
from django.apps import apps
from django.core.management import call_command
from io import StringIO

from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    update_organisation_model_with_ORD_changes,
)

Organisation = apps.get_model("hospitals", "Organisation")
OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")
Trust = apps.get_model("hospitals", "Trust")
TrustVersion = apps.get_model("hospitals", "TrustVersion")


ORD_ORG_RECORD = {
    "Name": "New Org Name",
    "GeoLoc": {
        "Location": {
            "AddrLn1": "2 New St",
            "Town": "Newtown",
            "PostCode": "NW1 1AA",
        }
    },
    "Contacts": {"Contact": []},
}


def _patch_ods(monkeypatch, org_links, records_by_ods_code):
    monkeypatch.setattr(
        "rcpch_nhs_organisations.hospitals.general_functions.ods_update.fetch_updated_organisations",
        lambda time_frame=30: org_links,
    )
    monkeypatch.setattr(
        "rcpch_nhs_organisations.hospitals.general_functions.ods_update.get_organisation",
        lambda org_link: records_by_ods_code[org_link.rsplit("/", 1)[1]],
    )


@pytest.fixture
def trust():
    return Trust.objects.create(
        ods_code="RAA",
        name="Old Trust Name",
        active=True,
    )


@pytest.fixture
def trust_with_baseline(trust):
    TrustVersion.objects.create(
        trust=trust,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name=trust.name,
        active=True,
    )
    return trust


ORD_TRUST_RECORD = {
    "Name": "New Trust Name",
    "GeoLoc": {
        "Location": {
            "AddrLn1": "2 New St",
            "Town": "Newtown",
            "PostCode": "NW1 1AA",
        }
    },
    "Contacts": {"Contact": []},
}


@pytest.mark.django_db
def test_report_file_written_when_changes_found(
    monkeypatch, trust_with_baseline, tmp_path
):
    _patch_ods(
        monkeypatch,
        org_links=[{"OrgLink": "https://ods.example/Organisation/RAA"}],
        records_by_ods_code={"RAA": ORD_TRUST_RECORD},
    )
    report_path = tmp_path / "ods_changes.md"
    call_command(
        "cron",
        "--service",
        "organisations",
        "--dry-run",
        "--report-file",
        str(report_path),
        stdout=StringIO(),
        stderr=StringIO(),
    )
    assert report_path.exists()
    content = report_path.read_text()
    assert "Trust RAA" in content
    assert "Old Trust Name" in content
    assert "New Trust Name" in content


@pytest.mark.django_db
def test_report_file_empty_when_no_changes(monkeypatch, trust_with_baseline, tmp_path):
    """When no changes are found, the report file is empty (or contains only
    whitespace), so the GitHub Action's [ -s ods_changes.md ] check correctly
    skips the issue step."""
    matching_record = {
        "Name": trust_with_baseline.name,
        "GeoLoc": {
            "Location": {
                "AddrLn1": trust_with_baseline.address_line_1,
                "Town": trust_with_baseline.town,
                "PostCode": trust_with_baseline.postcode,
            }
        },
        "Contacts": {"Contact": []},
    }
    _patch_ods(
        monkeypatch,
        org_links=[{"OrgLink": "https://ods.example/Organisation/RAA"}],
        records_by_ods_code={"RAA": matching_record},
    )
    report_path = tmp_path / "ods_changes.md"
    call_command(
        "cron",
        "--service",
        "organisations",
        "--dry-run",
        "--report-file",
        str(report_path),
        stdout=StringIO(),
        stderr=StringIO(),
    )
    assert report_path.exists()
    content = report_path.read_text()
    assert content == ""


# ---------------------------------------------------------------------------
# --time-frame argument validation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_time_frame_passed_through_to_sync(monkeypatch, trust_with_baseline, tmp_path):
    """The --time-frame argument is passed through to the sync function."""
    captured = {}

    def fake_fetch(time_frame=30):
        captured["time_frame"] = time_frame
        # Return a matching record so no changes are found.
        return [
            {
                "OrgLink": "https://ods.example/Organisation/RAA",
                "LastChangeDate": "2024-03-15",
            }
        ]

    monkeypatch.setattr(
        "rcpch_nhs_organisations.hospitals.general_functions.ods_update.fetch_updated_organisations",
        fake_fetch,
    )
    monkeypatch.setattr(
        "rcpch_nhs_organisations.hospitals.general_functions.ods_update.get_organisation",
        lambda org_link: {
            "Name": trust_with_baseline.name,
            "GeoLoc": {
                "Location": {
                    "AddrLn1": trust_with_baseline.address_line_1,
                    "Town": trust_with_baseline.town,
                    "PostCode": trust_with_baseline.postcode,
                }
            },
            "Contacts": {"Contact": []},
        },
    )
    call_command(
        "cron",
        "--service",
        "organisations",
        "--dry-run",
        "--time-frame",
        "185",
        stdout=StringIO(),
        stderr=StringIO(),
    )
    assert captured["time_frame"] == 185


@pytest.mark.django_db
def test_time_frame_rejects_zero(monkeypatch):
    """--time-frame 0 is rejected (must be 1-185)."""
    from django.core.management import CommandError

    with pytest.raises(CommandError):
        call_command(
            "cron",
            "--service",
            "organisations",
            "--dry-run",
            "--time-frame",
            "0",
            stdout=StringIO(),
            stderr=StringIO(),
        )


@pytest.mark.django_db
def test_time_frame_rejects_over_185(monkeypatch):
    """--time-frame 186 is rejected (ODS API hard limit)."""
    from django.core.management import CommandError

    with pytest.raises(CommandError):
        call_command(
            "cron",
            "--service",
            "organisations",
            "--dry-run",
            "--time-frame",
            "186",
            stdout=StringIO(),
            stderr=StringIO(),
        )


@pytest.mark.django_db
def test_time_frame_defaults_to_30(monkeypatch, trust_with_baseline):
    """Without --time-frame, the default of 30 days is used."""
    captured = {}

    def fake_fetch(time_frame=30):
        captured["time_frame"] = time_frame
        return []

    monkeypatch.setattr(
        "rcpch_nhs_organisations.hospitals.general_functions.ods_update.fetch_updated_organisations",
        fake_fetch,
    )
    call_command(
        "cron",
        "--service",
        "organisations",
        "--dry-run",
        stdout=StringIO(),
        stderr=StringIO(),
    )
    assert captured["time_frame"] == 30
