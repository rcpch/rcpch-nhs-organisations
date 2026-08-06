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
    "LastChangeDate": "2024-03-15",
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
    "LastChangeDate": "2024-03-15",
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

# A record with succession events (merger / acquisition / split) in the
# Succs block, like the real ODS response for a trust that's been through
# a merger. Used to test that the dry-run report surfaces the succession info
# and that the review-gating fires for recent mergers.
#
# The succession dates are set relative to today so they fall within the
# default 30-day time_frame window — the review-gating only fires for
# succession events whose legal date is within the window. A merger from
# 2021 would not trigger the review for a 2026 sync run.
ORD_TRUST_RECORD_WITH_SUCCESSION = {
    "Name": "New Trust Name",
    "LastChangeDate": "2021-10-15",
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
    "Succs": {
        "Succ": [
            {
                "Type": "Successor",
                "Date": [{"Type": "Legal", "Start": "__RECENT__"}],
                "Target": {
                    "OrgId": {"extension": "RM3"},
                    "PrimaryRoleId": {"id": "RO197"},
                },
            },
            {
                "Type": "Predecessor",
                "Date": [{"Type": "Legal", "Start": "__OLD__"}],
                "Target": {
                    "OrgId": {"extension": "RMK"},
                    "PrimaryRoleId": {"id": "RO197"},
                },
                "forwardSuccession": True,
            },
        ]
    },
}


def _org_link(ods_code):
    # The /sync endpoint returns only OrgLink — LastChangeDate is on the
    # full organisation record fetched via get_organisation, not on the
    # /sync list item.
    return {"OrgLink": f"https://ods.example/Organisation/{ods_code}"}


def _succession_record(recent_days_ago=7, old_years_ago=20):
    """Return a copy of ORD_TRUST_RECORD_WITH_SUCCESSION with the
    __RECENT__ and __OLD__ placeholders replaced by real dates relative to
    today. The recent date falls within the default 30-day time_frame window
    (so the review-gating fires); the old date falls well outside it."""
    import copy, datetime as dt
    record = copy.deepcopy(ORD_TRUST_RECORD_WITH_SUCCESSION)
    today = dt.date.today()
    recent = today - dt.timedelta(days=recent_days_ago)
    old = today.replace(year=today.year - old_years_ago)
    for succ in record["Succs"]["Succ"]:
        for d in succ["Date"]:
            if d["Start"] == "__RECENT__":
                d["Start"] = recent.isoformat()
            elif d["Start"] == "__OLD__":
                d["Start"] = old.isoformat()
    return record


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
    assert "Effective date applied:" in report
    assert "ODS last change date: 2024-03-15" in report


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


# ---------------------------------------------------------------------------
# --time-frame argument and LastChangeDate surfacing (backfill workflow)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_time_frame_passed_through_to_fetch(organisation_with_baseline, monkeypatch):
    """The time_frame parameter is passed through to fetch_updated_organisations."""
    captured = {}

    def fake_fetch(time_frame=30):
        captured["time_frame"] = time_frame
        return []

    monkeypatch.setattr(
        "rcpch_nhs_organisations.hospitals.general_functions.ods_update.fetch_updated_organisations",
        fake_fetch,
    )
    update_organisation_model_with_ORD_changes(dry_run=True, time_frame=185)
    assert captured["time_frame"] == 185


@pytest.mark.django_db
def test_dry_run_report_surfaces_ods_change_date(
    organisation_with_baseline, monkeypatch
):
    """The dry-run report includes the ODS LastChangeDate so operators can
    decide whether to apply the change as forward-looking or as a backfill."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA01")],
        records_by_ods_code={"RAA01": ORD_ORG_RECORD},
    )
    stdout = _FakeStdout()
    update_organisation_model_with_ORD_changes(dry_run=True, stdout=stdout)

    report = stdout.text
    assert "ODS last change date: 2024-03-15" in report
    assert "Effective date applied:" in report


@pytest.mark.django_db
def test_dry_run_report_handles_missing_ods_change_date(
    organisation_with_baseline, monkeypatch
):
    """If the ODS response omits LastChangeDate, the report shows 'unknown'
    rather than crashing."""
    record_without_change_date = {
        "Name": "New Org Name",
        # No LastChangeDate key, as older API responses or partial records might omit.
        "GeoLoc": {
            "Location": {
                "AddrLn1": "2 New St",
                "Town": "Newtown",
                "PostCode": "NW1 1AA",
            }
        },
        "Contacts": {"Contact": []},
    }
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA01")],
        records_by_ods_code={"RAA01": record_without_change_date},
    )
    stdout = _FakeStdout()
    update_organisation_model_with_ORD_changes(dry_run=True, stdout=stdout)

    report = stdout.text
    assert "ODS last change date: unknown" in report


@pytest.mark.django_db
def test_dry_run_report_surfaces_ods_change_date_for_trust(
    trust_with_baseline, monkeypatch
):
    """The trust dry-run report also surfaces the ODS LastChangeDate."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": ORD_TRUST_RECORD},
    )
    stdout = _FakeStdout()
    update_organisation_model_with_ORD_changes(dry_run=True, stdout=stdout)

    report = stdout.text
    assert "ODS last change date: 2024-03-15" in report


@pytest.mark.django_db
def test_dry_run_report_surfaces_succession_events(
    trust_with_baseline, monkeypatch
):
    """The dry-run report surfaces the ODS Succs block so operators can see
    whether a name/active change is the consequence of a merger and record
    it manually rather than via the forward-looking sync."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": _succession_record()},
    )
    stdout = _FakeStdout()
    update_organisation_model_with_ORD_changes(dry_run=True, stdout=stdout)

    report = stdout.text
    # The succession events are surfaced.
    assert "succession events" in report
    assert "Successor" in report
    assert "RM3" in report
    assert "Predecessor" in report
    assert "RMK" in report
    # The recent date is in the report.
    import datetime as dt
    recent = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    assert recent in report
    # The guidance to use the admin/backfill helpers is present.
    assert "backfill" in report
    # The LastChangeDate from the full record is surfaced.
    assert "ODS last change date: 2021-10-15" in report


@pytest.mark.django_db
def test_dry_run_report_no_succession_section_when_no_succs(
    organisation_with_baseline, monkeypatch
):
    """If the ODS record has no Succs block, the report does not mention
    succession events."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA01")],
        records_by_ods_code={"RAA01": ORD_ORG_RECORD},
    )
    stdout = _FakeStdout()
    update_organisation_model_with_ORD_changes(dry_run=True, stdout=stdout)

    report = stdout.text
    assert "succession events" not in report


# ---------------------------------------------------------------------------
# Review-gated apply for merger-driven changes (succession events present)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_merger_driven_change_skipped_without_callback(
    trust_with_baseline, monkeypatch
):
    """A change with succession events is skipped when no review_callback is
    provided (e.g. running from a script). The change is not applied."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": _succession_record()},
    )
    changes_found = update_organisation_model_with_ORD_changes(
        dry_run=False, review_callback=None
    )

    assert changes_found is True  # a change was found, but...
    # ...it was not applied.
    trust_with_baseline.refresh_from_db()
    assert trust_with_baseline.name == "Old Trust Name"
    # No new version row was created.
    assert TrustVersion.objects.filter(trust=trust_with_baseline).count() == 1


@pytest.mark.django_db
def test_merger_driven_change_applied_when_callback_accepts(
    trust_with_baseline, monkeypatch
):
    """When the review_callback returns True, the change is applied as a
    forward-looking change."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": _succession_record()},
    )

    def accept_all(change):
        return True

    changes_found = update_organisation_model_with_ORD_changes(
        dry_run=False, review_callback=accept_all
    )

    assert changes_found is True
    trust_with_baseline.refresh_from_db()
    assert trust_with_baseline.name == "New Trust Name"
    # A new version row was created.
    assert TrustVersion.objects.filter(trust=trust_with_baseline).count() == 2


@pytest.mark.django_db
def test_merger_driven_change_skipped_when_callback_refuses(
    trust_with_baseline, monkeypatch
):
    """When the review_callback returns False, the change is skipped."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": _succession_record()},
    )

    def refuse_all(change):
        return False

    changes_found = update_organisation_model_with_ORD_changes(
        dry_run=False, review_callback=refuse_all
    )

    assert changes_found is True  # found, but refused
    trust_with_baseline.refresh_from_db()
    assert trust_with_baseline.name == "Old Trust Name"
    assert TrustVersion.objects.filter(trust=trust_with_baseline).count() == 1


@pytest.mark.django_db
def test_non_merger_change_applied_without_review(
    trust_with_baseline, monkeypatch
):
    """A change without succession events is applied automatically, without
    invoking the review callback."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": ORD_TRUST_RECORD},  # no Succs block
    )

    callback_invoked = []

    def callback(change):
        callback_invoked.append(change)
        return True

    update_organisation_model_with_ORD_changes(
        dry_run=False, review_callback=callback
    )

    # The callback was NOT invoked (no succession events).
    assert callback_invoked == []
    # The change was applied.
    trust_with_baseline.refresh_from_db()
    assert trust_with_baseline.name == "New Trust Name"


@pytest.mark.django_db
def test_review_callback_receives_change_details(
    trust_with_baseline, monkeypatch
):
    """The review callback receives a dict with the entity details, changes,
    and succession events so the operator can make an informed decision."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": _succession_record()},
    )

    received = []

    def callback(change):
        received.append(change)
        return False  # refuse so nothing is applied

    update_organisation_model_with_ORD_changes(
        dry_run=False, review_callback=callback
    )

    assert len(received) == 1
    change = received[0]
    assert change["entity_type"] == "Trust"
    assert change["ods_code"] == "RAA"
    assert change["name"] == "Old Trust Name"
    assert "name" in change["changes"]
    # Only the recent succession event is passed to the callback (the old one
    # is outside the time_frame window and does not trigger the review).
    assert len(change["succession_events"]) == 1
    assert change["succession_events"][0]["type"] == "Successor"
    assert change["succession_events"][0]["target_ods_code"] == "RM3"
    import datetime as dt
    recent = dt.date.today() - dt.timedelta(days=7)
    assert change["succession_events"][0]["date"] == recent
    assert change["ods_change_date"] == "2021-10-15"


@pytest.mark.django_db
def test_old_succession_event_does_not_trigger_review(
    trust_with_baseline, monkeypatch
):
    """A succession event from 20 years ago is part of the entity's permanent
    ODS record but should NOT trigger the review-gating — only recent
    succession events (within the time_frame window) are plausibly related
    to the change being applied."""
    # Use a record where BOTH succession events are old (outside the window).
    import copy, datetime as dt
    record = copy.deepcopy(ORD_TRUST_RECORD_WITH_SUCCESSION)
    today = dt.date.today()
    old = today.replace(year=today.year - 20)
    older = today.replace(year=today.year - 25)
    for succ in record["Succs"]["Succ"]:
        for d in succ["Date"]:
            if d["Start"] == "__RECENT__":
                d["Start"] = old.isoformat()
            elif d["Start"] == "__OLD__":
                d["Start"] = older.isoformat()

    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": record},
    )

    callback_invoked = []

    def callback(change):
        callback_invoked.append(change)
        return True

    update_organisation_model_with_ORD_changes(
        dry_run=False, review_callback=callback
    )

    # The callback was NOT invoked — both succession events are old.
    assert callback_invoked == []
    # The change was applied automatically.
    trust_with_baseline.refresh_from_db()
    assert trust_with_baseline.name == "New Trust Name"


# ---------------------------------------------------------------------------
# Non-merger changes applied at ODS LastChangeDate (not today)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_non_merger_change_applied_at_ods_date(
    organisation_with_baseline, monkeypatch
):
    """A non-merger change (no succession events) is applied at the ODS
    LastChangeDate, not today, so the version row records when the change
    actually happened."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA01")],
        records_by_ods_code={"RAA01": ORD_ORG_RECORD},  # LastChangeDate=2024-03-15
    )
    update_organisation_model_with_ORD_changes(dry_run=False)

    organisation_with_baseline.refresh_from_db()
    assert organisation_with_baseline.name == "New Org Name"

    # The new version row's valid_from is the ODS date, not today.
    new_version = OrganisationVersion.objects.get(
        organisation=organisation_with_baseline, valid_to__isnull=True
    )
    assert new_version.valid_from == datetime.date(2024, 3, 15)

    # The old version row was closed at the ODS date.
    old_version = OrganisationVersion.objects.get(
        organisation=organisation_with_baseline, name="Old Org Name"
    )
    assert old_version.valid_to == datetime.date(2024, 3, 15)


@pytest.mark.django_db
def test_non_merger_trust_change_applied_at_ods_date(
    trust_with_baseline, monkeypatch
):
    """A non-merger trust change is applied at the ODS LastChangeDate."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": ORD_TRUST_RECORD},  # LastChangeDate=2024-03-15
    )
    update_organisation_model_with_ORD_changes(dry_run=False)

    trust_with_baseline.refresh_from_db()
    assert trust_with_baseline.name == "New Trust Name"

    new_version = TrustVersion.objects.get(
        trust=trust_with_baseline, valid_to__isnull=True
    )
    assert new_version.valid_from == datetime.date(2024, 3, 15)


@pytest.mark.django_db
def test_non_merger_change_falls_back_to_today_if_no_ods_date(
    organisation_with_baseline, monkeypatch
):
    """If the ODS record omits LastChangeDate, the change is applied at today's
    date as a fallback."""
    record_without_date = {
        "Name": "New Org Name",
        "GeoLoc": {"Location": {"AddrLn1": "2 New St", "Town": "Newtown", "PostCode": "NW1 1AA"}},
        "Contacts": {"Contact": []},
    }
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA01")],
        records_by_ods_code={"RAA01": record_without_date},
    )
    update_organisation_model_with_ORD_changes(dry_run=False)

    new_version = OrganisationVersion.objects.get(
        organisation=organisation_with_baseline, valid_to__isnull=True
    )
    assert new_version.valid_from == datetime.date.today()


@pytest.mark.django_db
def test_dry_run_report_shows_backfill_date_for_non_merger(
    organisation_with_baseline, monkeypatch
):
    """The dry-run report shows the ODS date as the effective date for
    non-merger changes (with 'backfilled at ODS change date' annotation)."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA01")],
        records_by_ods_code={"RAA01": ORD_ORG_RECORD},
    )
    stdout = _FakeStdout()
    update_organisation_model_with_ORD_changes(dry_run=True, stdout=stdout)

    report = stdout.text
    assert "Effective date applied: 2024-03-15" in report
    assert "backfilled at ODS change date" in report


@pytest.mark.django_db
def test_dry_run_report_shows_forward_looking_date_for_merger(
    trust_with_baseline, monkeypatch
):
    """The dry-run report shows today's date as the effective date for
    merger-driven changes (with 'forward-looking — merger-driven change
    requires review' annotation)."""
    _patch_ods(
        monkeypatch,
        org_links=[_org_link("RAA")],
        records_by_ods_code={"RAA": _succession_record()},
    )
    stdout = _FakeStdout()
    update_organisation_model_with_ORD_changes(dry_run=True, stdout=stdout)

    report = stdout.text
    assert "Effective date if applied:" in report
    assert "forward-looking" in report
    assert "requires review" in report
