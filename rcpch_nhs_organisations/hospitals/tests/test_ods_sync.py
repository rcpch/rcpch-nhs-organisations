"""
Tests for the refactored ODS sync (update_organisation_model_with_ORD_changes)
and its --dry-run mode.

The ODS network calls are mocked so the tests are deterministic and offline.
The tests cover:

- attribute changes are routed through the temporal helpers (a *Version row
  is created, the previous one is closed)
- the denormalised main row is updated
- dry-run mode writes a markdown report and makes no DB changes
- dry-run returns True when changes are found, False when not
- non-dry-run returns True when changes are applied
- entities not in the database are skipped
"""
import datetime
from unittest.mock import patch

import pytest
from django.apps import apps

from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    update_organisation_model_with_ORD_changes,
)

Organisation = apps.get_model("hospitals", "Organisation")
OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")
Trust = apps.get_model("hospitals", "Trust")
TrustVersion = apps.get_model("hospitals", "TrustVersion")


@pytest.fixture
def trust():
    return Trust.objects.create(
        ods_code="RAA",
        name="Old Trust Name",
        address_line_1="1 Old St",
        town="Oldtown",
        postcode="OL1 1AA",
        active=True,
    )


@pytest.fixture
def organisation(trust):
    return Organisation.objects.create(
        ods_code="RAA01",
        name="Old Org Name",
        address1="1 Old St",
        city="Oldtown",
        postcode="OL1 1AA",
        active=True,
        trust=trust,
    )


@pytest.fixture
def organisation_with_baseline(organisation):
    OrganisationVersion.objects.create(
        organisation=organisation,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name=organisation.name,
        address1=organisation.address1,
        city=organisation.city,
        postcode=organisation.postcode,
        active=organisation.active,
    )
    return organisation


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


# A fake ORD record for an organisation whose name and address have changed.
ORD_ORG_RECORD = {
    "Name": "New Org Name",
    "GeoLoc": {
        "Location": {
            "AddrLn1": "2 New St",
            "AddrLn2": "Suite B",
            "AddrLn3": None,
            "Town": "Newtown",
            "County": "Newshire",
            "PostCode": "NW1 1AA",
        }
    },
    "Contacts": {
        "Contact": [
            {"type": "http", "value": "https://new.example"},
            {"type": "tel", "value": "0207 123 4567"},
        ]
    },
}

ORD_TRUST_RECORD = {
    "Name": "New Trust Name",
    "GeoLoc": {
        "Location": {
            "AddrLn1": "2 New St",
            "AddrLn2": "Trust Suite",
            "Town": "Newtown",
            "PostCode": "NW1 1AA",
        }
    },
    "Contacts": {
        "Contact": [
            {"type": "http", "value": "https://trust.example"},
            {"type": "tel", "value": "0207 999 9999"},
        ]
    },
}


def _org_link(ods_code):
    return {"OrgLink": f"https://ods.example/Organisation/{ods_code}"}


def _patch_ods(monkeypatch, org_links, records_by_ods_code):
    """Patch the ODS fetch helpers used by the sync."""
    monkeypatch.setattr(
        "rcpch_nhs_organisations.hospitals.general_functions.ods_update.fetch_updated_organisations",
        lambda time_frame=30: org_links,
    )
    monkeypatch.setattr(
        "rcpch_nhs_organisations.hospitals.general_functions.ods_update.get_organisation",
        lambda org_link: records_by_ods_code[org_link.rsplit("/", 1)[1]],
    )


# ---------------------------------------------------------------------------
# Non-dry-run: writes go through the temporal helpers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sync_updates_organisation_through_temporal_helper(
    organisation_with_baseline, monkeypatch
):
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA01")],
        records_by_ods_code={"RAA01": ORD_ORG_RECORD},
    )
    changes_found = update_organisation_model_with_ORD_changes(dry_run=False)

    assert changes_found is True
    organisation_with_baseline.refresh_from_db()
    assert organisation_with_baseline.name == "New Org Name"
    assert organisation_with_baseline.address1 == "2 New St"
    assert organisation_with_baseline.city == "Newtown"
    assert organisation_with_baseline.postcode == "NW1 1AA"

    # A new current version row was opened, the previous one closed.
    versions = OrganisationVersion.objects.filter(
        organisation=organisation_with_baseline
    ).order_by("valid_from")
    assert versions.count() == 2
    assert versions[0].valid_to is not None
    assert versions[0].name == "Old Org Name"
    assert versions[1].valid_to is None
    assert versions[1].name == "New Org Name"


@pytest.mark.django_db
def test_sync_updates_trust_through_temporal_helper(
    trust_with_baseline, monkeypatch
):
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": ORD_TRUST_RECORD},
    )
    changes_found = update_organisation_model_with_ORD_changes(dry_run=False)

    assert changes_found is True
    trust_with_baseline.refresh_from_db()
    assert trust_with_baseline.name == "New Trust Name"
    assert trust_with_baseline.address_line_1 == "2 New St"
    assert trust_with_baseline.town == "Newtown"
    assert trust_with_baseline.website == "https://trust.example"

    versions = TrustVersion.objects.filter(trust=trust_with_baseline).order_by(
        "valid_from"
    )
    assert versions.count() == 2
    assert versions[0].valid_to is not None
    assert versions[0].name == "Old Trust Name"
    assert versions[1].valid_to is None
    assert versions[1].name == "New Trust Name"


@pytest.mark.django_db
def test_sync_skips_entities_not_in_database(monkeypatch):
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("ZZZ99")],
        records_by_ods_code={"ZZZ99": ORD_ORG_RECORD},
    )
    changes_found = update_organisation_model_with_ORD_changes(dry_run=False)
    assert changes_found is False


@pytest.mark.django_db
def test_sync_returns_false_when_no_changes(organisation_with_baseline, monkeypatch):
    """If the ORD record matches the current state, no change is reported."""
    matching_record = {
        "Name": organisation_with_baseline.name,
        "GeoLoc": {
            "Location": {
                "AddrLn1": organisation_with_baseline.address1,
                "Town": organisation_with_baseline.city,
                "PostCode": organisation_with_baseline.postcode,
            }
        },
        "Contacts": {"Contact": []},
    }
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA01")],
        records_by_ods_code={"RAA01": matching_record},
    )
    changes_found = update_organisation_model_with_ORD_changes(dry_run=False)
    assert changes_found is False


# ---------------------------------------------------------------------------
# Dry-run: no writes, markdown report
# ---------------------------------------------------------------------------


class _FakeStdout:
    def __init__(self):
        self.parts = []

    def write(self, text):
        self.parts.append(text)

    @property
    def text(self):
        return "".join(self.parts)


@pytest.mark.django_db
def test_dry_run_makes_no_db_changes(organisation_with_baseline, monkeypatch):
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA01")],
        records_by_ods_code={"RAA01": ORD_ORG_RECORD},
    )
    stdout = _FakeStdout()
    changes_found = update_organisation_model_with_ORD_changes(
        dry_run=True, stdout=stdout
    )

    assert changes_found is True
    # The main row is unchanged.
    organisation_with_baseline.refresh_from_db()
    assert organisation_with_baseline.name == "Old Org Name"
    # No new version row was created.
    assert OrganisationVersion.objects.filter(
        organisation=organisation_with_baseline
    ).count() == 1


@pytest.mark.django_db
def test_dry_run_report_contains_old_and_new_values(
    organisation_with_baseline, monkeypatch
):
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA01")],
        records_by_ods_code={"RAA01": ORD_ORG_RECORD},
    )
    stdout = _FakeStdout()
    update_organisation_model_with_ORD_changes(dry_run=True, stdout=stdout)

    report = stdout.text
    assert "RAA01" in report
    assert "Old Org Name" in report
    assert "New Org Name" in report
    assert "| Field | Old | New |" in report
    assert "Effective date:" in report


@pytest.mark.django_db
def test_dry_run_returns_false_when_no_changes(
    organisation_with_baseline, monkeypatch
):
    matching_record = {
        "Name": organisation_with_baseline.name,
        "GeoLoc": {
            "Location": {
                "AddrLn1": organisation_with_baseline.address1,
                "Town": organisation_with_baseline.city,
                "PostCode": organisation_with_baseline.postcode,
            }
        },
        "Contacts": {"Contact": []},
    }
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA01")],
        records_by_ods_code={"RAA01": matching_record},
    )
    stdout = _FakeStdout()
    changes_found = update_organisation_model_with_ORD_changes(
        dry_run=True, stdout=stdout
    )
    assert changes_found is False
    assert stdout.text == ""


@pytest.mark.django_db
def test_dry_run_report_for_trust(trust_with_baseline, monkeypatch):
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": ORD_TRUST_RECORD},
    )
    stdout = _FakeStdout()
    update_organisation_model_with_ORD_changes(dry_run=True, stdout=stdout)

    report = stdout.text
    assert "Trust RAA" in report
    assert "Old Trust Name" in report
    assert "New Trust Name" in report
