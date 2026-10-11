"""
Tests for the reconcile_ods engine, command, apply path, and admin queue.

All ODS network calls are mocked (fetch_roster, deep_fetch,
fetch_updated_organisations) so the tests are deterministic and offline, mirroring
the existing offline-mock strategy (see testing.md).
"""
import datetime
from contextlib import ExitStack
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from rcpch_nhs_organisations.hospitals.models import (
    IntegratedCareBoard,
    NHSEnglandRegion,
    OdsSyncRun,
    Organisation,
    OrganisationSuccession,
    OrganisationTrustMembership,
    OrganisationVersion,
    PendingOdsChange,
    Trust,
    TrustSuccession,
)
from rcpch_nhs_organisations.hospitals.general_functions.reconcile import (
    ReconcileEngine,
    TokenBucketRateLimiter,
    build_report,
)
from rcpch_nhs_organisations.hospitals.general_functions.reconcile.apply import (
    apply_pending_change,
    ApplyError,
)

FLOOR = datetime.date(2020, 12, 1)


# ---------------------------------------------------------------------------
# ODS record builders
# ---------------------------------------------------------------------------


def _rel(target_ods_code, start, end=None, rel_id="RE6", target_role="RO197"):
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


def _succ(target_ods_code, succ_type, legal_date):
    return {
        "Type": succ_type,
        "Target": {"OrgId": {"extension": target_ods_code}},
        "Date": [{"Type": "Legal", "Start": legal_date}],
    }


def _detail(
    ods_code,
    name,
    *,
    status="Active",
    last_change="2024-01-01",
    legal_start="2001-04-01",
    op_end=None,
    rels=None,
    succs=None,
    postcode=None,
):
    date = [{"Type": "Legal", "Start": legal_start}]
    if op_end is not None:
        date.append({"Type": "Operational", "Start": legal_start, "End": op_end})
    location = {}
    if postcode is not None:
        location["PostCode"] = postcode
    record = {
        "Name": name,
        "OrgId": {"extension": ods_code},
        "Status": status,
        "LastChangeDate": last_change,
        "Date": date,
        "GeoLoc": {"Location": location},
        "Contacts": {"Contact": []},
    }
    if rels:
        record["Rels"] = {"Rel": rels}
    if succs:
        record["Succs"] = {"Succ": succs}
    return record


def _roster(ods_code, name, status="Active", last_change="2024-01-01"):
    return {
        "OrgId": ods_code,
        "Name": name,
        "Status": status,
        "LastChangeDate": last_change,
    }


def _postcode_item(ods_code, name, *, status="Active", primary_role="RO198"):
    """A directory roster item as returned by a ``PostCode=`` query, carrying the
    bare-string ``PrimaryRoleId`` the candidate-successor filter reads."""
    return {
        "OrgId": ods_code,
        "Name": name,
        "Status": status,
        "PrimaryRoleId": primary_role,
    }


# ---------------------------------------------------------------------------
# Patch helpers
# ---------------------------------------------------------------------------

ENGINE = "rcpch_nhs_organisations.hospitals.general_functions.reconcile.engine"
APPLY = "rcpch_nhs_organisations.hospitals.general_functions.reconcile.apply"
COMMAND = "rcpch_nhs_organisations.hospitals.management.commands.reconcile_ods"


def _patch_engine(roster_map=None, details=None, flagged_links=None, postcode_map=None):
    """Patch the ODS sources the engine uses. Returns an ExitStack."""
    roster_map = roster_map or {}
    details = details or {}
    postcode_map = postcode_map or {}

    def fake_fetch_roster(filter_param, role_id, rate_limiter=None, **kwargs):
        # Keyed by role_id so existing fixtures (e.g. "RO197") keep working.
        return roster_map.get(role_id, [])

    def fake_deep_fetch(ods_code, rate_limiter=None):
        return details.get(ods_code)

    def fake_fetch_updated(time_frame=30):
        return flagged_links or []

    def fake_fetch_by_postcode(postcode, rate_limiter=None, **kwargs):
        return postcode_map.get(postcode, [])

    stack = ExitStack()
    stack.enter_context(patch(f"{ENGINE}.fetch_roster", side_effect=fake_fetch_roster))
    stack.enter_context(patch(f"{ENGINE}.deep_fetch", side_effect=fake_deep_fetch))
    stack.enter_context(
        patch(f"{ENGINE}.fetch_by_postcode", side_effect=fake_fetch_by_postcode)
    )
    stack.enter_context(
        patch(f"{ENGINE}.fetch_updated_organisations", side_effect=fake_fetch_updated)
    )
    return stack


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def trust_a():
    return Trust.objects.create(ods_code="RAA", name="Trust A")


@pytest.fixture
def trust_b():
    return Trust.objects.create(ods_code="RBB", name="Trust B")


# ---------------------------------------------------------------------------
# Rate limiter (unit, no DB)
# ---------------------------------------------------------------------------


def test_rate_limiter_throttles_under_limit():
    """The limiter admits at most `rate` calls per second on a fake clock."""
    clock = {"t": 0.0}
    slept = []

    def now():
        return clock["t"]

    def sleep(seconds):
        slept.append(seconds)
        clock["t"] += seconds

    limiter = TokenBucketRateLimiter(rate=10.0, now=now, sleep=sleep)
    # Burst of 25 acquisitions: the first 10 are free (full bucket), the rest
    # force sleeps. Total simulated time must respect the 10/s rate.
    for _ in range(25):
        limiter.acquire()
    # 25 tokens at 10/s with a 10-token bucket needs ~1.5s of sleeping.
    assert 1.4 <= clock["t"] <= 1.6
    # The 15 throttled calls each waited ~1/rate seconds.
    assert len(slept) == 15
    # The sustained throttle rate stays well under the ODS ceiling of 5000/300.
    assert limiter.rate <= 5000 / 300


# ---------------------------------------------------------------------------
# Roster fetch: pagination + ICB role selector (unit, no DB)
# ---------------------------------------------------------------------------


ODS_SOURCES = "rcpch_nhs_organisations.hospitals.general_functions.reconcile.ods_sources"


class _FakeResponse:
    def __init__(self, rows):
        self._rows = rows

    def raise_for_status(self):
        pass

    def json(self):
        return {"Organisations": self._rows}


def test_fetch_roster_paginates_past_500():
    """The roster is fetched across pages: a full first page (500) triggers a
    second request, and the first page must NOT send Offset (ODS 406s Offset=0)."""
    from rcpch_nhs_organisations.hospitals.general_functions.reconcile.ods_sources import (
        fetch_roster,
    )

    page1 = [{"OrgId": f"T{i:03d}", "Name": "x", "Status": "Active"} for i in range(500)]
    page2 = [{"OrgId": f"U{i:03d}", "Name": "y", "Status": "Active"} for i in range(44)]
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        return _FakeResponse(page1 if "Offset" not in url else page2)

    with patch.dict("os.environ", {"NHS_ODS_API_URL": "https://ods.example/ORD"}):
        with patch(f"{ODS_SOURCES}.requests.get", side_effect=fake_get):
            rows = fetch_roster("PrimaryRoleId", "RO197")

    assert len(rows) == 544
    assert len(calls) == 2
    assert "Offset" not in calls[0]  # first page omits Offset (avoids HTTP 406)
    assert "Offset=500" in calls[1]


def test_fetch_roster_single_short_page_stops():
    """A first page shorter than the limit means no second request."""
    from rcpch_nhs_organisations.hospitals.general_functions.reconcile.ods_sources import (
        fetch_roster,
    )

    page = [{"OrgId": "RAA", "Name": "x", "Status": "Active"}]
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        return _FakeResponse(page)

    with patch.dict("os.environ", {"NHS_ODS_API_URL": "https://ods.example/ORD"}):
        with patch(f"{ODS_SOURCES}.requests.get", side_effect=fake_get):
            rows = fetch_roster("PrimaryRoleId", "RO197")

    assert len(rows) == 1
    assert len(calls) == 1


def test_icb_roster_selector_uses_non_primary_ro318():
    """ICBs are selected by the ICB-specific role RO318 via the ``Roles`` query,
    not the over-broad primary role RO261 (which also returns SMHPCs, shared
    care records and commissioning alliances)."""
    from rcpch_nhs_organisations.hospitals.general_functions.reconcile.ods_sources import (
        LEVEL_ROSTER_FILTERS,
    )

    assert LEVEL_ROSTER_FILTERS["icb"] == ("Roles", "RO318")
    assert LEVEL_ROSTER_FILTERS["trust"] == ("PrimaryRoleId", "RO197")
    assert LEVEL_ROSTER_FILTERS["lhb"] == ("PrimaryRoleId", "RO142")


def test_is_effectively_active_end_date_aware():
    """is_effectively_active trusts the end date over the (unreliable) Status
    flag: Active + no end → active; Active + past end → closed; Inactive →
    closed; Active + future end → active."""
    from rcpch_nhs_organisations.hospitals.general_functions.reconcile.ods_sources import (
        is_effectively_active,
    )

    today = datetime.date(2026, 1, 1)
    assert is_effectively_active(_detail("RAA", "x"), as_of=today) is True
    assert (
        is_effectively_active(_detail("RAA", "x", op_end="2013-10-01"), as_of=today)
        is False
    )
    assert (
        is_effectively_active(_detail("RAA", "x", status="Inactive"), as_of=today)
        is False
    )
    assert (
        is_effectively_active(_detail("RAA", "x", op_end="2030-01-01"), as_of=today)
        is True
    )


# ---------------------------------------------------------------------------
# Roster reconciliation (trust / icb)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_trust_roster_add_detected(trust_a):
    """A trust active in ODS but not in the DB is flagged roster-add."""
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "New Trust")]}
    details = {"RAA": _detail("RAA", "Trust A")}
    with _patch_engine(roster, details):
        result = ReconcileEngine(["trust"], since=None).detect()
    adds = [c for c in result.changes if c.change_class == "roster-add"]
    assert len(adds) == 1
    assert adds[0].ods_code == "RBB"


@pytest.mark.django_db
def test_trust_retire_detected_when_inactive_in_ods(trust_a):
    """A trust active in the DB but Inactive in ODS is flagged retire."""
    roster = {"RO197": [_roster("RAA", "Trust A", status="Inactive")]}
    details = {"RAA": _detail("RAA", "Trust A", status="Inactive")}
    with _patch_engine(roster, details):
        result = ReconcileEngine(["trust"], since=None).detect()
    retires = [c for c in result.changes if c.change_class == "retire"]
    assert len(retires) == 1
    assert retires[0].ods_code == "RAA"


@pytest.mark.django_db
def test_zombie_roster_add_skipped(trust_a):
    """A trust ODS still stamps Active but whose end date has passed (a long-dead
    trust ODS never cleaned up) is NOT flagged as a new roster add."""
    roster = {
        "RO197": [_roster("RAA", "Trust A"), _roster("RZZ", "Dissolved Trust")]
    }
    details = {
        "RAA": _detail("RAA", "Trust A"),
        # ODS Status Active but an Operational End in the past: effectively dead.
        "RZZ": _detail("RZZ", "Dissolved Trust", op_end="2013-10-01"),
    }
    with _patch_engine(roster, details):
        result = ReconcileEngine(["trust"], since=None).detect()
    adds = [c for c in result.changes if c.change_class == "roster-add"]
    assert adds == []


@pytest.mark.django_db
def test_absent_but_effectively_active_not_retired(trust_a):
    """A held trust absent from the (English) roster roles but still effectively
    active in ODS (no end date) is NOT retired — it simply sits outside the
    queried roles (the Welsh LHB / Crown-dependency case)."""
    # Roster omits RAA entirely; a deep fetch shows it is still open.
    roster = {"RO197": []}
    details = {"RAA": _detail("RAA", "Trust A")}  # Active, no end date
    with _patch_engine(roster, details):
        result = ReconcileEngine(["trust"], since=None).detect()
    retires = [c for c in result.changes if c.change_class == "retire"]
    assert retires == []


@pytest.mark.django_db
def test_absent_and_effectively_closed_is_retired(trust_a):
    """A held trust absent from the roster AND effectively closed in ODS (past
    end date) is retired."""
    roster = {"RO197": []}
    details = {"RAA": _detail("RAA", "Trust A", op_end="2015-04-01")}
    with _patch_engine(roster, details):
        result = ReconcileEngine(["trust"], since=None).detect()
    retires = [c for c in result.changes if c.change_class == "retire"]
    assert len(retires) == 1
    assert retires[0].ods_code == "RAA"
    assert retires[0].payload["reason"] == "absent-from-roster"


@pytest.mark.django_db
def test_retire_skipped_for_diverged_organisation():
    """A curated divergence (diverged_from_ods) is never re-flagged."""
    Organisation.objects.create(
        ods_code="R1APF", name="Covercroft", active=True, diverged_from_ods=True
    )
    details = {"R1APF": _detail("R1APF", "Covercroft", status="Inactive")}
    with _patch_engine({}, details):
        result = ReconcileEngine(["organisation"], since=None).detect()
    assert not [c for c in result.changes if c.change_class == "retire"]


# ---------------------------------------------------------------------------
# Attribute changes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_attribute_change_detected_and_auto_safe(trust_a):
    """A rename with no succession in the window is auto-safe (not structural)."""
    roster = {"RO197": [_roster("RAA", "Trust A")]}
    details = {"RAA": _detail("RAA", "Trust A Renamed")}
    with _patch_engine(roster, details):
        result = ReconcileEngine(["trust"], since=None).detect()
    attrs = [c for c in result.changes if c.change_class == "attribute"]
    assert len(attrs) == 1
    assert attrs[0].auto_safe is True
    assert attrs[0].payload["changes"]["name"] == ["Trust A", "Trust A Renamed"]


@pytest.mark.django_db
def test_attribute_change_not_auto_safe_with_merger_in_window(trust_a, trust_b):
    """A rename accompanied by a succession in the window must be reviewed."""
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "Trust B")]}
    details = {
        "RAA": _detail(
            "RAA",
            "Trust A Renamed",
            succs=[_succ("RBB", "Successor", "2024-01-01")],
        ),
        "RBB": _detail("RBB", "Trust B"),
    }
    with _patch_engine(roster, details):
        result = ReconcileEngine(["trust"], since=None).detect()
    attr = next(c for c in result.changes if c.change_class == "attribute")
    assert attr.auto_safe is False


# ---------------------------------------------------------------------------
# Successions and the temporal floor
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_succession_detected(trust_a, trust_b):
    """A Successor event with both entities held and no existing row is queued."""
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "Trust B")]}
    details = {
        "RAA": _detail("RAA", "Trust A", succs=[_succ("RBB", "Successor", "2024-04-01")]),
        "RBB": _detail("RBB", "Trust B"),
    }
    with _patch_engine(roster, details):
        result = ReconcileEngine(["trust"], since=None).detect()
    succ = [c for c in result.changes if c.change_class == "succession"]
    assert len(succ) == 1
    assert succ[0].payload["predecessor_ods_code"] == "RAA"
    assert succ[0].payload["successor_ods_code"] == "RBB"


@pytest.mark.django_db
def test_succession_skipped_when_row_exists(trust_a, trust_b):
    """An already-recorded succession row is not re-reported."""
    TrustSuccession.objects.create(
        predecessor=trust_a,
        successor=trust_b,
        succession_date=datetime.date(2024, 4, 1),
        succession_type="acquisition",
    )
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "Trust B")]}
    details = {
        "RAA": _detail("RAA", "Trust A", succs=[_succ("RBB", "Successor", "2024-04-01")]),
        "RBB": _detail("RBB", "Trust B"),
    }
    with _patch_engine(roster, details):
        result = ReconcileEngine(["trust"], since=None).detect()
    assert not [c for c in result.changes if c.change_class == "succession"]


@pytest.mark.django_db
def test_prefloor_succession_collapsed_into_count(trust_a, trust_b):
    """A succession event before 2020-12-01 is dropped into the legacy-skip count."""
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "Trust B")]}
    details = {
        "RAA": _detail("RAA", "Trust A", succs=[_succ("RBB", "Successor", "2013-10-01")]),
        "RBB": _detail("RBB", "Trust B"),
    }
    with _patch_engine(roster, details):
        result = ReconcileEngine(["trust"], since=None).detect()
    assert not [c for c in result.changes if c.change_class == "succession"]
    assert result.legacy_skips == 1


# ---------------------------------------------------------------------------
# Organisation level — closed set, relationships, superseded codes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_organisation_relationship_reparenting_detected(trust_a, trust_b):
    """An org whose ODS RE6 parent differs from its DB trust is flagged relationship."""
    org = Organisation.objects.create(ods_code="RAA01", name="Org A", trust=trust_a)
    details = {
        "RAA01": _detail("RAA01", "Org A", rels=[_rel("RBB", "2024-01-01")]),
    }
    with _patch_engine({}, details):
        result = ReconcileEngine(["organisation"], since=None).detect()
    rel = [c for c in result.changes if c.change_class == "relationship"]
    assert len(rel) == 1
    assert rel[0].payload == {
        "relationship": "organisation-trust",
        "old_ods_code": "RAA",
        "new_ods_code": "RBB",
    }
    assert rel[0].summary


@pytest.mark.django_db
def test_organisation_superseded_code_detected(trust_a):
    """A held org Inactive in ODS with a Successor event is flagged superseded-code."""
    Organisation.objects.create(ods_code="RAP01", name="North Mid", trust=trust_a, active=True)
    details = {
        "RAP01": _detail(
            "RAP01",
            "North Mid",
            status="Inactive",
            succs=[_succ("RAL27", "Successor", "2024-07-01")],
        ),
    }
    with _patch_engine({}, details):
        result = ReconcileEngine(["organisation"], since=None).detect()
    superseded = [c for c in result.changes if c.change_class == "superseded-code"]
    assert len(superseded) == 1
    assert superseded[0].payload["successor_ods_code"] == "RAL27"


@pytest.mark.django_db
def test_organisation_superseded_code_detected_by_end_date(trust_a):
    """ODS leaves a re-coded site stamped Active past its end date. The engine
    must still treat it as closed (end-date-aware) and, with an own Successor,
    flag superseded-code."""
    Organisation.objects.create(
        ods_code="RAP01", name="North Mid", trust=trust_a, active=True
    )
    details = {
        "RAP01": _detail(
            "RAP01",
            "North Mid",
            status="Active",  # ODS stale Active flag
            op_end="2024-12-31",  # but a past end date
            succs=[_succ("RAL27", "Successor", "2025-01-01")],
        ),
    }
    with _patch_engine({}, details):
        result = ReconcileEngine(["organisation"], since=None).detect()
    superseded = [c for c in result.changes if c.change_class == "superseded-code"]
    assert len(superseded) == 1
    assert superseded[0].payload["successor_ods_code"] == "RAL27"


@pytest.mark.django_db
def test_organisation_parallel_code_via_parent_trust_bridge():
    """The North Middlesex pattern: a held site ODS has effectively closed (past
    end date) with no own Succs, but its held parent trust has an ODS successor.
    The engine surfaces a parallel-code review item recording the trust bridge,
    without auto-picking a successor site."""
    rap = Trust.objects.create(ods_code="RAP", name="North Mid Trust", active=False)
    Organisation.objects.create(
        ods_code="RAPNM", name="North Middlesex Hospital", trust=rap, active=True
    )
    details = {
        # Site: ODS stale Active, but a past Legal/Operational end, no Succs,
        # still parented on RAP.
        "RAPNM": _detail(
            "RAPNM",
            "North Middlesex Hospital",
            status="Active",
            op_end="2024-12-31",
            rels=[_rel("RAP", "2001-04-01")],
        ),
        # Parent trust RAP: succeeded by RAL on 2025-01-01.
        "RAP": _detail(
            "RAP",
            "North Mid Trust",
            succs=[_succ("RAL", "Successor", "2025-01-01")],
        ),
    }
    with _patch_engine({}, details):
        result = ReconcileEngine(["organisation"], since=None).detect()
    parallel = [c for c in result.changes if c.change_class == "parallel-code"]
    assert len(parallel) == 1
    payload = parallel[0].payload
    assert payload["predecessor_trust"] == "RAP"
    assert payload["successor_trust"] == "RAL"
    assert payload["reason"] == "parent-trust-succession-bridge"
    # Must not be auto-applied or mis-classified as a plain retirement.
    assert not parallel[0].auto_safe
    assert not [c for c in result.changes if c.change_class == "retire"]


@pytest.mark.django_db
def test_parallel_code_surfaces_candidate_successor_code():
    """The RAL27 pattern: a closed site (RAPNM) whose parent trust RAP was
    succeeded by RAL. An active RO198 site (RAL27) at the predecessor's postcode
    whose open RE6 parent is RAL is surfaced as a candidate successor — for
    review only, not auto-picked. A co-located site under a different trust and
    an inactive site at the same postcode are excluded, and matching ignores
    names entirely."""
    rap = Trust.objects.create(ods_code="RAP", name="North Mid Trust", active=False)
    Organisation.objects.create(
        ods_code="RAPNM", name="North Middlesex Hospital", trust=rap, active=True
    )
    postcode = "N18 1QX"
    details = {
        "RAPNM": _detail(
            "RAPNM",
            "North Middlesex Hospital",
            status="Active",
            op_end="2024-12-31",
            rels=[_rel("RAP", "2001-04-01")],
            postcode=postcode,
        ),
        "RAP": _detail(
            "RAP",
            "North Mid Trust",
            succs=[_succ("RAL", "Successor", "2025-01-01")],
        ),
        # The genuine successor site: open, active, parented on the successor
        # trust RAL, and ALREADY OPEN before the predecessor closed (legal_start
        # 2003, predecessor closed 2024-12-31) — a true parallel code. Note the
        # DELIBERATELY different name: selection must not depend on the name.
        "RAL27": _detail(
            "RAL27",
            "NORTH MIDDLESEX SITE (RENAMED)",
            status="Active",
            legal_start="2003-04-01",
            rels=[_rel("RAL", "2003-04-01")],
            postcode=postcode,
        ),
        # A freshly-minted departmental code under the SAME successor trust at
        # the SAME postcode, created on the merger date (legal_start == the
        # predecessor's end). ODS mints dozens of these on a trust merger; the
        # temporal "pre-existing parallel" filter must exclude it.
        "RALW1": _detail(
            "RALW1",
            "WARD 1",
            status="Active",
            legal_start="2025-01-01",
            rels=[_rel("RAL", "2025-01-01")],
            postcode=postcode,
        ),
        # A co-located site under a DIFFERENT trust — must not be offered.
        "RXX99": _detail(
            "RXX99",
            "Unrelated Co-located Clinic",
            status="Active",
            rels=[_rel("RXX", "2010-04-01")],
            postcode=postcode,
        ),
    }
    postcode_map = {
        postcode: [
            _postcode_item("RAL27", "NORTH MIDDLESEX SITE (RENAMED)"),
            _postcode_item("RALW1", "WARD 1"),
            _postcode_item("RXX99", "Unrelated Co-located Clinic"),
            # An inactive co-located site under the successor trust — excluded
            # by the roster Status filter before any deep fetch.
            _postcode_item("RAL88", "Closed RAL Site", status="Inactive"),
            # A non-RO198 role at the same postcode (e.g. a GP practice) —
            # excluded by the role filter.
            _postcode_item("G123", "A GP Practice", primary_role="RO177"),
        ]
    }
    with _patch_engine({}, details, postcode_map=postcode_map):
        result = ReconcileEngine(["organisation"], since=None).detect()
    parallel = [c for c in result.changes if c.change_class == "parallel-code"]
    assert len(parallel) == 1
    change = parallel[0]
    assert change.payload["candidate_successors"] == ["RAL27"]
    assert "RALW1" not in change.payload["candidate_successors"]
    assert "RAL27" in change.summary
    # Surfaced for review only — never auto-picked or auto-applied.
    assert not change.auto_safe
    assert "replacement_ods_code" not in change.payload


@pytest.mark.django_db
def test_parallel_code_no_candidate_when_postcode_has_no_successor_site():
    """If no active RO198 site at the predecessor's postcode sits under the
    successor trust, the candidate list is empty and the review item still
    fires (the reviewer must find the successor by hand)."""
    rap = Trust.objects.create(ods_code="RAP", name="North Mid Trust", active=False)
    Organisation.objects.create(
        ods_code="RAPNM", name="North Middlesex Hospital", trust=rap, active=True
    )
    postcode = "N18 1QX"
    details = {
        "RAPNM": _detail(
            "RAPNM",
            "North Middlesex Hospital",
            status="Active",
            op_end="2024-12-31",
            rels=[_rel("RAP", "2001-04-01")],
            postcode=postcode,
        ),
        "RAP": _detail(
            "RAP",
            "North Mid Trust",
            succs=[_succ("RAL", "Successor", "2025-01-01")],
        ),
        # Only a co-located site under a different trust exists.
        "RXX99": _detail(
            "RXX99",
            "Unrelated Co-located Clinic",
            status="Active",
            rels=[_rel("RXX", "2010-04-01")],
            postcode=postcode,
        ),
    }
    postcode_map = {postcode: [_postcode_item("RXX99", "Unrelated Co-located Clinic")]}
    with _patch_engine({}, details, postcode_map=postcode_map):
        result = ReconcileEngine(["organisation"], since=None).detect()
    parallel = [c for c in result.changes if c.change_class == "parallel-code"]
    assert len(parallel) == 1
    assert parallel[0].payload["candidate_successors"] == []


@pytest.mark.django_db
def test_wythenshawe_parallel_open_codes_not_flagged():
    """A genuinely persistent divergence — two parallel codes BOTH open in ODS
    (no end date, Status Active) — is left alone: it is not resolvable by the
    end-date discriminator and must not be flagged closed."""
    trust = Trust.objects.create(ods_code="RM3", name="MFT", active=True)
    Organisation.objects.create(
        ods_code="RM325", name="Wythenshawe", trust=trust, active=True
    )
    details = {
        "RM325": _detail("RM325", "Wythenshawe", status="Active"),  # open, no end
    }
    with _patch_engine({}, details):
        result = ReconcileEngine(["organisation"], since=None).detect()
    assert not [
        c
        for c in result.changes
        if c.change_class in {"retire", "superseded-code", "parallel-code"}
    ]


@pytest.mark.django_db
def test_closed_set_new_org_not_imported(trust_a):
    """The organisation level never roster-adds: a new ODS site is not imported."""
    # No organisations held; roster is irrelevant for organisations.
    with _patch_engine({}, {}):
        result = ReconcileEngine(["organisation"], since=None).detect()
    assert not [c for c in result.changes if c.change_class == "roster-add"]
    assert Organisation.objects.count() == 0


# ---------------------------------------------------------------------------
# Incremental window
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_incremental_window_restricts_deep_fetch(trust_a, trust_b):
    """In incremental mode only /sync-flagged entities are deep-fetched."""
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "Trust B")]}
    details = {
        "RAA": _detail("RAA", "Trust A Renamed"),
        "RBB": _detail("RBB", "Trust B Renamed"),
    }
    # Only RAA is flagged by /sync.
    flagged = [{"OrgLink": "https://x/ORD/2-0-0/organisations/RAA"}]
    since = datetime.date.today() - datetime.timedelta(days=10)
    with _patch_engine(roster, details, flagged_links=flagged):
        result = ReconcileEngine(["trust"], since=since).detect()
    attrs = [c for c in result.changes if c.change_class == "attribute"]
    assert {c.ods_code for c in attrs} == {"RAA"}


# ---------------------------------------------------------------------------
# Persistence / idempotency
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dry_run_writes_nothing(trust_a):
    """persist with write_queue off (plain dry-run) creates no rows."""
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "New")]}
    details = {"RAA": _detail("RAA", "Trust A")}
    with _patch_engine(roster, details):
        engine = ReconcileEngine(["trust"], since=None, apply=False, write_queue=False)
        result = engine.detect()
        engine.persist(result)
    assert PendingOdsChange.objects.count() == 0


@pytest.mark.django_db
def test_queue_is_idempotent(trust_a):
    """Two identical detection + queue passes create exactly one row."""
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "New")]}
    details = {"RAA": _detail("RAA", "Trust A")}
    for _ in range(2):
        with _patch_engine(roster, details):
            engine = ReconcileEngine(["trust"], since=None, write_queue=True)
            engine.persist(engine.detect())
    assert PendingOdsChange.objects.filter(change_class="roster-add").count() == 1


@pytest.mark.django_db
def test_terminal_change_not_requeued(trust_a):
    """A dismissed/applied row is not re-queued on a later run."""
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "New")]}
    details = {"RAA": _detail("RAA", "Trust A")}
    with _patch_engine(roster, details):
        engine = ReconcileEngine(["trust"], since=None, write_queue=True)
        engine.persist(engine.detect())
    row = PendingOdsChange.objects.get(change_class="roster-add")
    row.status = PendingOdsChange.STATUS_DISMISSED
    row.save()
    # Second run: must not create a new row or revert the dismissal.
    with _patch_engine(roster, details):
        engine = ReconcileEngine(["trust"], since=None, write_queue=True)
        engine.persist(engine.detect())
    assert PendingOdsChange.objects.filter(change_class="roster-add").count() == 1
    row.refresh_from_db()
    assert row.status == PendingOdsChange.STATUS_DISMISSED


# ---------------------------------------------------------------------------
# Apply path
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_apply_attribute_writes_version_row(trust_a):
    """Applying an auto-safe attribute change writes a temporal version row."""
    roster = {"RO197": [_roster("RAA", "Trust A")]}
    details = {"RAA": _detail("RAA", "Trust A Renamed", last_change="2024-05-01")}
    with _patch_engine(roster, details):
        engine = ReconcileEngine(["trust"], since=None, apply=True)
        engine.persist(engine.detect())
    trust_a.refresh_from_db()
    assert trust_a.name == "Trust A Renamed"


@pytest.mark.django_db
def test_apply_relationship_reassigns_trust(trust_a, trust_b):
    """Approve & apply on a relationship change re-points the org and writes a
    membership row."""
    org = Organisation.objects.create(ods_code="RAA01", name="Org A", trust=trust_a)
    change = PendingOdsChange.objects.create(
        level="organisation",
        ods_code="RAA01",
        change_class="relationship",
        effective_date=datetime.date(2024, 1, 1),
        payload={
            "relationship": "organisation-trust",
            "old_ods_code": "RAA",
            "new_ods_code": "RBB",
        },
    )
    apply_pending_change(change)
    org.refresh_from_db()
    assert org.trust_id == trust_b.pk
    assert OrganisationTrustMembership.objects.filter(
        organisation=org, trust=trust_b, valid_to__isnull=True
    ).exists()


@pytest.mark.django_db
def test_apply_relationship_errors_when_parent_missing(trust_a):
    """Applying a relationship change raises when the new parent is absent."""
    Organisation.objects.create(ods_code="RAA01", name="Org A", trust=trust_a)
    change = PendingOdsChange.objects.create(
        level="organisation",
        ods_code="RAA01",
        change_class="relationship",
        payload={
            "relationship": "organisation-trust",
            "old_ods_code": "RAA",
            "new_ods_code": "RZZ",
        },
    )
    with pytest.raises(ApplyError):
        apply_pending_change(change)


# ---------------------------------------------------------------------------
# Overlap detector
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_overlap_detector_flags_two_open_version_rows(trust_a):
    """check_overlaps flags an entity with two open version rows."""
    OrganisationVersion  # imported for clarity
    from rcpch_nhs_organisations.hospitals.models import TrustVersion

    TrustVersion.objects.create(trust=trust_a, valid_from=datetime.date(2021, 1, 1), name="A")
    TrustVersion.objects.create(trust=trust_a, valid_from=datetime.date(2022, 1, 1), name="A")
    problems = ReconcileEngine(["trust"], since=None).check_overlaps()
    assert any("open rows" in p for p in problems)


@pytest.mark.django_db
def test_overlap_detector_passes_on_clean_data(trust_a):
    """A clean temporal layer yields no overlap problems."""
    from rcpch_nhs_organisations.hospitals.models import TrustVersion

    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2021, 1, 1),
        valid_to=datetime.date(2022, 1, 1),
        name="A",
    )
    TrustVersion.objects.create(trust=trust_a, valid_from=datetime.date(2022, 1, 1), name="B")
    assert ReconcileEngine(["trust"], since=None).check_overlaps() == []


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_report_is_categorised_and_collapses_legacy(trust_a, trust_b):
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "Trust B"), _roster("RCC", "New")]}
    details = {
        "RAA": _detail("RAA", "Trust A", succs=[_succ("RBB", "Successor", "2013-10-01")]),
        "RBB": _detail("RBB", "Trust B Renamed"),
    }
    with _patch_engine(roster, details):
        result = ReconcileEngine(["trust"], since=None).detect()
    report = build_report(result)
    assert "## Trusts" in report
    assert "New entities in ODS" in report  # RCC roster-add
    assert "Collapsed 1 legacy" in report


def test_empty_report_is_blank_string():
    from rcpch_nhs_organisations.hospitals.general_functions.reconcile import (
        DetectionResult,
    )

    assert build_report(DetectionResult()) == ""


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_command_dry_run_writes_report_file_and_run_row(tmp_path, trust_a):
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "New")]}
    details = {"RAA": _detail("RAA", "Trust A")}
    report_file = tmp_path / "report.md"
    with _patch_engine(roster, details):
        call_command(
            "reconcile_ods",
            "--levels",
            "trust",
            "--mode",
            "backfill",
            "--dry-run",
            "--report-file",
            str(report_file),
            stdout=StringIO(),
            stderr=StringIO(),
        )
    content = report_file.read_text()
    assert "RBB" in content
    # A plain dry-run writes nothing to the queue.
    assert PendingOdsChange.objects.count() == 0
    # The run is recorded.
    run = OdsSyncRun.objects.latest("started_at")
    assert run.status == OdsSyncRun.STATUS_SUCCESS
    assert run.dry_run is True


@pytest.mark.django_db
def test_command_dry_run_queue_flag_populates_queue(trust_a):
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "New")]}
    details = {"RAA": _detail("RAA", "Trust A")}
    with _patch_engine(roster, details):
        call_command(
            "reconcile_ods",
            "--levels",
            "trust",
            "--mode",
            "backfill",
            "--dry-run",
            "--queue",
            stdout=StringIO(),
            stderr=StringIO(),
        )
    assert PendingOdsChange.objects.filter(change_class="roster-add").count() == 1


@pytest.mark.django_db
def test_command_check_overlaps_passes_on_clean_db(trust_a):
    with _patch_engine({"RO197": [_roster("RAA", "Trust A")]}, {"RAA": _detail("RAA", "Trust A")}):
        call_command(
            "reconcile_ods",
            "--levels",
            "trust",
            "--mode",
            "backfill",
            "--dry-run",
            "--check-overlaps",
            stdout=StringIO(),
            stderr=StringIO(),
        )


@pytest.mark.django_db
def test_command_upload_blob_emits_markers_and_uploads(trust_a):
    """--upload-blob prints the report between the sentinel markers and calls the
    shared blob uploader (the monthly Azure-job transport). The upload itself is
    mocked so no network/azure dependency is needed."""
    from rcpch_nhs_organisations.hospitals.general_functions.ods_report_blob import (
        REPORT_START_MARKER,
        REPORT_END_MARKER,
    )

    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "New")]}
    details = {"RAA": _detail("RAA", "Trust A")}
    out = StringIO()
    with _patch_engine(roster, details), patch(
        f"{COMMAND}.upload_report"
    ) as mock_upload:
        call_command(
            "reconcile_ods",
            "--levels",
            "trust",
            "--mode",
            "incremental",
            "--dry-run",
            "--queue",
            "--upload-blob",
            stdout=out,
            stderr=StringIO(),
        )
    output = out.getvalue()
    assert REPORT_START_MARKER in output
    assert REPORT_END_MARKER in output
    assert mock_upload.called
    # The queue was still populated (the job both queues and raises the issue).
    assert PendingOdsChange.objects.filter(change_class="roster-add").count() == 1


# ---------------------------------------------------------------------------
# Re-run safety over already-backfilled data, dedup-key parity, and the
# superseded-code apply path (doc section: Idempotency and re-run safety)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_rerun_over_matching_ods_detects_nothing(trust_a, trust_b):
    """A run over data that already matches ODS detects no structural change and
    queues nothing. This is the re-run-over-backfilled-data guarantee."""
    Organisation.objects.create(ods_code="RAA01", name="Org A", trust=trust_a)
    TrustSuccession.objects.create(
        predecessor=trust_a,
        successor=trust_b,
        succession_date=datetime.date(2024, 1, 1),
        succession_type="acquisition",
    )
    details = {
        "RAA01": _detail("RAA01", "Org A", rels=[_rel("RAA", "2001-04-01")]),
        "RAA": _detail("RAA", "Trust A", succs=[_succ("RBB", "Successor", "2024-01-01")]),
        "RBB": _detail("RBB", "Trust B"),
    }
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "Trust B")]}
    with _patch_engine(roster, details):
        engine = ReconcileEngine(["organisation", "trust"], since=None, write_queue=True)
        result = engine.detect()
        counts = engine.persist(result)
    assert [c for c in result.changes if not c.auto_safe] == []
    assert PendingOdsChange.objects.count() == 0
    assert counts["queued"] == 0


@pytest.mark.django_db
def test_succession_date_parity_detect_and_apply(trust_a, trust_b):
    """The succession_date the engine detects and the one the apply path writes
    both come from the same ODS date via _parse_ods_date, so a monthly re-run
    keys on the identical dedup value and never inserts a duplicate row."""
    details = {
        "RAA": _detail("RAA", "Trust A", succs=[_succ("RBB", "Successor", "2024-01-01")]),
        "RBB": _detail("RBB", "Trust B"),
    }
    roster = {"RO197": [_roster("RAA", "Trust A"), _roster("RBB", "Trust B")]}
    with _patch_engine(roster, details):
        engine = ReconcileEngine(["trust"], since=None, write_queue=True)
        engine.persist(engine.detect())
    change = PendingOdsChange.objects.get(change_class="succession")
    assert change.effective_date == datetime.date(2024, 1, 1)

    apply_pending_change(change)
    succ = TrustSuccession.objects.get(predecessor=trust_a, successor=trust_b)
    assert succ.succession_date == change.effective_date == datetime.date(2024, 1, 1)

    with _patch_engine(roster, details):
        engine2 = ReconcileEngine(["trust"], since=None, write_queue=True)
        result2 = engine2.detect()
        counts2 = engine2.persist(result2)
    assert [c for c in result2.changes if c.change_class == "succession"] == []
    assert counts2["queued"] == 0


@pytest.mark.django_db
def test_apply_superseded_code_follows_held_org_to_successor(trust_a, trust_b):
    """The closed-set forward follow: a held org Inactive in ODS with a Successor
    event is detected as superseded-code, and applying it creates the successor
    organisation under its new parent, records an OrganisationSuccession, and
    closes the predecessor (the North Middlesex RAP01 to RAL27 pattern)."""
    Organisation.objects.create(ods_code="RAP01", name="North Mid", trust=trust_a, active=True)
    held_detail = _detail(
        "RAP01",
        "North Mid",
        status="Inactive",
        succs=[_succ("RAL27", "Successor", "2024-07-01")],
    )
    successor_detail = _detail("RAL27", "North Mid", rels=[_rel("RBB", "2024-07-01")])

    with _patch_engine({}, {"RAP01": held_detail}):
        engine = ReconcileEngine(["organisation"], since=None, write_queue=True)
        engine.persist(engine.detect())
    change = PendingOdsChange.objects.get(change_class="superseded-code")
    assert change.payload["successor_ods_code"] == "RAL27"

    with patch(f"{APPLY}.deep_fetch", side_effect=lambda code, **kw: successor_detail):
        apply_pending_change(change)

    successor = Organisation.objects.get(ods_code="RAL27")
    assert successor.trust_id == trust_b.pk
    assert OrganisationSuccession.objects.filter(
        predecessor__ods_code="RAP01",
        successor=successor,
        succession_type="code_change",
    ).exists()
    predecessor = Organisation.objects.get(ods_code="RAP01")
    assert predecessor.active is False

    with patch(f"{APPLY}.deep_fetch", side_effect=lambda code, **kw: successor_detail):
        apply_pending_change(change)
    assert Organisation.objects.filter(ods_code="RAL27").count() == 1
    assert OrganisationSuccession.objects.filter(successor=successor).count() == 1


@pytest.mark.django_db
def test_apply_parallel_code_with_replacement_creates_successor(trust_a, trust_b):
    """Approving a parallel-code change with a replacement code performs the
    full reconciliation: deep-fetch the successor from ODS, create the org, link
    via OrganisationSuccession, re-point to the parent trust, close the
    predecessor, and flag the old code as diverged (the North Middlesex RAPNM
    → RAL27 pattern)."""
    pred = Organisation.objects.create(
        ods_code="RAPNM", name="North Middlesex Hospital", trust=trust_a, active=True
    )
    successor_detail = _detail(
        "RAL27", "North Middlesex Hospital", rels=[_rel("RBB", "2024-07-01")]
    )
    change = PendingOdsChange.objects.create(
        level="organisation",
        ods_code="RAPNM",
        change_class="parallel-code",
        effective_date=datetime.date(2024, 12, 31),
        payload={
            "reason": "parent-trust-succession-bridge",
            "predecessor_trust": "RAA",
            "successor_trust": "RBB",
            "candidate_successors": ["RAL27"],
            "replacement_ods_code": "RAL27",
        },
    )

    with patch(f"{APPLY}.deep_fetch", side_effect=lambda code, **kw: successor_detail):
        apply_pending_change(change)

    successor = Organisation.objects.get(ods_code="RAL27")
    assert successor.trust_id == trust_b.pk
    assert OrganisationSuccession.objects.filter(
        predecessor=pred, successor=successor, succession_type="code_change"
    ).exists()
    pred.refresh_from_db()
    assert pred.active is False
    assert pred.diverged_from_ods is True
    assert pred.ods_replacement_code == "RAL27"


@pytest.mark.django_db
def test_apply_parallel_code_without_replacement_flags_only(trust_a):
    """Approving a parallel-code change without a replacement code only flags
    the old code as diverged — no successor is created or linked."""
    pred = Organisation.objects.create(
        ods_code="RAPNM", name="North Middlesex Hospital", trust=trust_a, active=True
    )
    change = PendingOdsChange.objects.create(
        level="organisation",
        ods_code="RAPNM",
        change_class="parallel-code",
        effective_date=datetime.date(2024, 12, 31),
        payload={"candidate_successors": []},
    )

    apply_pending_change(change)

    pred.refresh_from_db()
    assert pred.diverged_from_ods is True
    assert pred.ods_replacement_code is None
    assert pred.active is True  # not closed — no successor to close it for
    assert not Organisation.objects.filter(ods_code="RAL27").exists()
    assert not OrganisationSuccession.objects.exists()


@pytest.mark.django_db
def test_apply_parallel_code_idempotent(trust_a, trust_b):
    """Re-applying a parallel-code change with a replacement is a no-op — the
    successor is not duplicated, the succession row is not duplicated."""
    pred = Organisation.objects.create(
        ods_code="RAPNM", name="North Middlesex Hospital", trust=trust_a, active=True
    )
    successor_detail = _detail(
        "RAL27", "North Middlesex Hospital", rels=[_rel("RBB", "2024-07-01")]
    )
    change = PendingOdsChange.objects.create(
        level="organisation",
        ods_code="RAPNM",
        change_class="parallel-code",
        effective_date=datetime.date(2024, 12, 31),
        payload={
            "candidate_successors": ["RAL27"],
            "replacement_ods_code": "RAL27",
        },
    )

    with patch(f"{APPLY}.deep_fetch", side_effect=lambda code, **kw: successor_detail):
        apply_pending_change(change)
        apply_pending_change(change)

    assert Organisation.objects.filter(ods_code="RAL27").count() == 1
    assert OrganisationSuccession.objects.filter(successor__ods_code="RAL27").count() == 1


# ---------------------------------------------------------------------------
# Baseline promotion — fills the [floor, installation_day) gap
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_promote_baseline_extends_version_row_to_floor(trust_a):
    """A stable organisation whose earliest version row starts at installation
    day gets its valid_from promoted to max(legal_start, floor) on --apply."""
    org = Organisation.objects.create(
        ods_code="RAA01", name="Org A", trust=trust_a, active=True
    )
    # Baseline version row at installation day (as the baseline migration does)
    OrganisationVersion.objects.create(
        organisation=org,
        valid_from=datetime.date(2026, 8, 5),
        valid_to=None,
        name="Org A",
        active=True,
    )
    # ODS record with legal_start before the floor
    details = {
        "RAA01": _detail("RAA01", "Org A", legal_start="2013-04-01",
                         rels=[_rel("RAA", "2013-04-01")]),
        "RAA": _detail("RAA", "Trust A"),
    }
    roster = {"RO197": [_roster("RAA", "Trust A")]}
    with _patch_engine(roster, details):
        engine = ReconcileEngine(["organisation", "trust"], since=None, apply=True)
        engine.persist(engine.detect())
    org.refresh_from_db()
    version = OrganisationVersion.objects.get(organisation=org)
    assert version.valid_from == FLOOR  # max(2013-04-01, 2020-12-01) = floor


@pytest.mark.django_db
def test_promote_baseline_idempotent(trust_a):
    """A second run does not re-promote or duplicate — the earliest row already
    starts at or before the target date, and all baseline rows exist."""
    from rcpch_nhs_organisations.hospitals.models import TrustVersion
    org = Organisation.objects.create(
        ods_code="RAA01", name="Org A", trust=trust_a, active=True
    )
    # Create all baseline rows at/before the floor so the second run is a no-op.
    TrustVersion.objects.create(
        trust=trust_a, valid_from=FLOOR, valid_to=None, name="Trust A",
    )
    OrganisationVersion.objects.create(
        organisation=org,
        valid_from=FLOOR,
        valid_to=None,
        name="Org A",
        active=True,
    )
    OrganisationTrustMembership.objects.create(
        organisation=org, trust=trust_a, valid_from=FLOOR, valid_to=None,
    )
    details = {
        "RAA01": _detail("RAA01", "Org A", legal_start="2013-04-01",
                         rels=[_rel("RAA", "2013-04-01")]),
        "RAA": _detail("RAA", "Trust A"),
    }
    roster = {"RO197": [_roster("RAA", "Trust A")]}
    with _patch_engine(roster, details):
        engine = ReconcileEngine(["organisation", "trust"], since=None, apply=True)
        result = engine.detect()
        engine.persist(result)
    assert result.baseline_promotions == 0
    assert OrganisationVersion.objects.filter(organisation=org).count() == 1
    assert TrustVersion.objects.filter(trust=trust_a).count() == 1


@pytest.mark.django_db
def test_promote_baseline_dry_run_does_not_write(trust_a):
    """Without --apply, the baseline promotion reports but does not write."""
    org = Organisation.objects.create(
        ods_code="RAA01", name="Org A", trust=trust_a, active=True
    )
    OrganisationVersion.objects.create(
        organisation=org,
        valid_from=datetime.date(2026, 8, 5),
        valid_to=None,
        name="Org A",
        active=True,
    )
    details = {
        "RAA01": _detail("RAA01", "Org A", legal_start="2013-04-01",
                         rels=[_rel("RAA", "2013-04-01")]),
        "RAA": _detail("RAA", "Trust A"),
    }
    roster = {"RO197": [_roster("RAA", "Trust A")]}
    with _patch_engine(roster, details):
        engine = ReconcileEngine(["organisation", "trust"], since=None, apply=False)
        result = engine.detect()
    version = OrganisationVersion.objects.get(organisation=org)
    assert version.valid_from == datetime.date(2026, 8, 5)  # unchanged


@pytest.mark.django_db
def test_promote_baseline_creates_missing_version_row(trust_a):
    """On a fresh DB (no version rows), _promote_baseline creates a baseline
    version row at max(legal_start, floor) snapshotting the current attributes."""
    org = Organisation.objects.create(
        ods_code="RAA01", name="Org A", trust=trust_a, active=True
    )
    # No OrganisationVersion row — simulates a fresh DB where the 0024
    # migration ran before seed.
    details = {
        "RAA01": _detail("RAA01", "Org A", legal_start="2013-04-01",
                         rels=[_rel("RAA", "2013-04-01")]),
        "RAA": _detail("RAA", "Trust A"),
    }
    roster = {"RO197": [_roster("RAA", "Trust A")]}
    with _patch_engine(roster, details):
        engine = ReconcileEngine(["organisation", "trust"], since=None, apply=True)
        engine.persist(engine.detect())
    version = OrganisationVersion.objects.get(organisation=org)
    assert version.valid_from == FLOOR  # max(2013-04-01, 2020-12-01) = floor
    assert version.valid_to is None
    assert version.name == "Org A"


@pytest.mark.django_db
def test_promote_baseline_creates_missing_membership_rows(trust_a):
    """On a fresh DB (no membership rows), _promote_baseline creates baseline
    membership rows at the floor for each non-null denormalised FK."""
    from rcpch_nhs_organisations.hospitals.models import (
        OrganisationIntegratedCareBoardMembership,
        OrganisationNHSEnglandRegionMembership,
    )
    icb = IntegratedCareBoard.objects.create(
        ods_code="QKK", name="Test ICB", boundary_identifier="E54000001"
    )
    from django.contrib.gis.geos import MultiPolygon, Polygon
    region = NHSEnglandRegion.objects.create(
        boundary_identifier="E40000001",
        name="London",
        bng_e=400000,
        bng_n=400000,
        long=-1.0,
        lat=53.0,
        globalid="guid",
        geom=MultiPolygon(
            Polygon(
                (
                    (399900, 400100),
                    (399900, 399900),
                    (400100, 399900),
                    (400100, 400100),
                    (399900, 400100),
                )
            )
        ),
        region_code="Y56",
    )
    org = Organisation.objects.create(
        ods_code="RAA01", name="Org A", trust=trust_a,
        integrated_care_board=icb, nhs_england_region=region, active=True,
    )
    # No membership rows — simulates a fresh DB.
    details = {
        "RAA01": _detail("RAA01", "Org A", legal_start="2013-04-01",
                         rels=[_rel("RAA", "2013-04-01")]),
        "RAA": _detail("RAA", "Trust A"),
    }
    roster = {"RO197": [_roster("RAA", "Trust A")]}
    with _patch_engine(roster, details):
        engine = ReconcileEngine(["organisation", "trust"], since=None, apply=True)
        engine.persist(engine.detect())
    icb_row = OrganisationIntegratedCareBoardMembership.objects.get(organisation=org)
    assert icb_row.valid_from == FLOOR
    assert icb_row.valid_to is None
    assert icb_row.integrated_care_board == icb
    region_row = OrganisationNHSEnglandRegionMembership.objects.get(organisation=org)
    assert region_row.valid_from == FLOOR
    assert region_row.valid_to is None
    assert region_row.nhs_england_region == region
