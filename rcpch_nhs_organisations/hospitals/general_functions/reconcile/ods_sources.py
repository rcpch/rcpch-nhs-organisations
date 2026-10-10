"""
ODS data sources for the reconciliation engine.

Three ODS sources are used together (see
documentation/docs/developer/ods-sync.md, "Detection mechanism"):

1. ``/sync?LastChangeDate=`` — the cheap trigger feed (already wrapped by
   ``fetch_updated_organisations`` in ``ods_update.py``).
2. ``/organisations?PrimaryRoleId={role}`` (or ``Roles={role}`` for ICBs),
   paginated with ``Offset``, carrying ``Status`` and ``LastChangeDate``. Used
   for trust / LHB / ICB presence and status reconciliation (the organisation
   level is a closed set and is not roster-reconciled). Implemented here as
   ``fetch_roster``.
3. ``/organisations/{ods_code}`` — per-entity detail (already wrapped by
   ``get_organisation``). Here we add ``deep_fetch`` which applies the rate
   limiter and returns the parsed record.

All functions take an optional ``rate_limiter`` so the engine can throttle to
stay safely under the ODS 5000-requests / 5-minutes ceiling.
"""
import datetime
import logging
import os

import requests
from requests.exceptions import HTTPError

from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    _parse_ods_date,
)

logger = logging.getLogger("hospitals")

# ODS role codes for the in-scope levels. The organisation level (RO198 trust
# site / RO144 LHB site) is deliberately not roster-reconciled — it is a closed
# set followed only along succession chains.
#
# Trusts and LHBs are selected by their *primary* role. ICBs are a special
# case: their primary role RO261 ("STRATEGIC PARTNERSHIP") is far broader than
# ICBs — it also covers mental-health provider collaboratives (SMHPCs), shared
# care records, commissioning alliances, etc. (125 orgs vs the ~48 real ICBs).
# The reliable, name-free discriminator is the *non-primary* role RO318, which
# ODS assigns only to actual Integrated Care Boards. So the ICB roster is
# selected by RO318, not RO261.
ROLE_TRUST = "RO197"
ROLE_LHB = "RO142"
ROLE_ICB_PRIMARY = "RO261"  # too broad for roster selection; kept for reference
ROLE_ICB = "RO318"  # the ICB-specific (non-primary) role used for the roster

# Map a reconcile level to the ODS directory query that selects its roster:
# (query_param, role_id). ``PrimaryRoleId`` is a strict primary-role match;
# ``Roles`` matches an org carrying the role in any (primary or non-primary)
# position, which is how the non-primary ICB role RO318 is selected.
LEVEL_ROSTER_FILTERS = {
    "trust": ("PrimaryRoleId", ROLE_TRUST),
    "lhb": ("PrimaryRoleId", ROLE_LHB),
    "icb": ("Roles", ROLE_ICB),
}

# The historical floor. Entities inactive before this date are out of scope
# entirely; held entities are reconstructed backward only to this date.
TEMPORAL_FLOOR = datetime.date(2020, 12, 1)


def _base_url():
    url = os.getenv("NHS_ODS_API_URL")
    if not url:
        raise RuntimeError(
            "NHS_ODS_API_URL is not set — cannot reach the ODS directory API."
        )
    return url.rstrip("/")


def organisation_url(ods_code):
    """Return the ODS detail URL for a single ODS code."""
    return f"{_base_url()}/organisations/{ods_code}"


def fetch_roster(filter_param, role_id, limit=500, rate_limiter=None):
    """Fetch the full, paginated ODS roster for a role.

    ``filter_param`` is the directory query parameter (``PrimaryRoleId`` or
    ``Roles``) and ``role_id`` the role code — see ``LEVEL_ROSTER_FILTERS``.

    Returns a list of dicts, one per organisation, each carrying at least
    ``OrgId`` (the ODS code), ``Name``, ``Status`` ("Active"/"Inactive"), and
    ``LastChangeDate``. This is the directory roster used for trust / LHB / ICB
    presence and status reconciliation.

    The ODS directory caps a single page at 500 rows, so this paginates with
    ``Offset`` until a short/empty page is returned. Two quirks are handled:
    the API rejects ``Offset=0`` with HTTP 406, so the first page omits
    ``Offset`` entirely; and ``Limit`` above 500 is incompatible with
    ``Offset``, so the page size is held at 500. Without pagination the roster
    silently truncated at 500 rows, which made every entity past the first page
    look "absent from ODS" (a false retirement).

    ``all_nhs_hospitals_list`` uses a different NHS API and cannot be reused for
    this — the ODS directory roster carries the ``Status`` flag the engine needs.
    """
    limit = min(limit, 500)
    results = []
    offset = 0
    while True:
        if rate_limiter is not None:
            rate_limiter.acquire()
        query = f"{filter_param}={role_id}&Limit={limit}"
        if offset:
            # Offset=0 is rejected (HTTP 406); omit it for the first page.
            query += f"&Offset={offset}"
        request_url = f"{_base_url()}/organisations?{query}"
        try:
            response = requests.get(url=request_url, timeout=30)
            response.raise_for_status()
        except HTTPError as e:
            logger.error(
                "ODS roster fetch failed for %s=%s (offset %s): %s",
                filter_param,
                role_id,
                offset,
                e,
            )
            raise
        page = response.json().get("Organisations", [])
        results.extend(page)
        if len(page) < limit:
            break
        offset += limit
    return results


def deep_fetch(ods_code, rate_limiter=None):
    """Fetch the full ODS record for a single ODS code, with rate limiting.

    One deep fetch returns the entity's entire history (``Status``, ``Rels``,
    ``Succs``), so each entity needs only one such call per run.

    Returns the ``Organisation`` block, or ``None`` if the record is missing.
    """
    if rate_limiter is not None:
        rate_limiter.acquire()
    request_url = organisation_url(ods_code)
    try:
        response = requests.get(url=request_url, timeout=10)
        response.raise_for_status()
    except HTTPError as e:
        logger.warning("ODS deep fetch failed for %s: %s", ods_code, e)
        return None
    return response.json().get("Organisation")


def extract_status(ord_record):
    """Return the ODS ``Status`` of a record as a bool: True if Active.

    ODS uses "Active" / "Inactive". Any value other than "Active" (including a
    missing status) is treated as inactive.
    """
    return ord_record.get("Status") == "Active"


def extract_ods_code(ord_record):
    """Return the ODS code (OrgId.extension) from a full ODS record."""
    return ord_record.get("OrgId", {}).get("extension")


def roster_ods_code(roster_item):
    """Return the ODS code from a roster list item (``OrgId`` is a bare string)."""
    org_id = roster_item.get("OrgId")
    if isinstance(org_id, dict):
        return org_id.get("extension")
    return org_id


def legal_start(ord_record):
    """Return the entity's own Legal.Start date, or None.

    Falls back to Operational.Start if no Legal date is present. Used to decide
    whether an entity was already inactive before the temporal floor.
    """
    legal = None
    operational = None
    for d in ord_record.get("Date", []):
        if d.get("Type") == "Legal":
            legal = _parse_ods_date(d.get("Start"))
        elif d.get("Type") == "Operational":
            operational = _parse_ods_date(d.get("Start"))
    return legal or operational


def operational_end(ord_record):
    """Return the entity's own Operational/Legal End date, or None if still open."""
    operational = None
    legal = None
    for d in ord_record.get("Date", []):
        if d.get("Type") == "Operational":
            operational = _parse_ods_date(d.get("End"))
        elif d.get("Type") == "Legal":
            legal = _parse_ods_date(d.get("End"))
    return operational or legal


def active_on_or_after_floor(ord_record, floor=TEMPORAL_FLOOR):
    """True if the entity was active on or after the temporal floor.

    An entity whose ODS record closed before the floor is out of scope. An
    entity with no end date (still open) or an end date on/after the floor is in
    scope.
    """
    end = operational_end(ord_record)
    if end is None:
        return True
    return end >= floor


def is_effectively_active(ord_record, as_of=None):
    """True if an entity is genuinely still open, not merely ODS-Status-Active.

    The ODS ``Status`` header is unreliable: ODS leaves long-dissolved trusts
    (and re-coded sites) stamped ``Active`` for years after they closed. The
    authoritative signal is the Operational/Legal End date — an entity is
    effectively inactive once that end date has passed. An entity is effectively
    active only when BOTH:

      * its ``Status`` is "Active", AND
      * it has no end date, or its end date is on/after ``as_of``
        (defaulting to today).

    This is the discriminator that lets the engine (a) skip zombie roster-adds
    — long-dead trusts ODS still flags Active — and (b) spot held sites that
    have effectively closed even though their ODS record is still stamped
    Active (e.g. a site re-coded under a successor trust). The roster list items
    do not carry the end-date block, so a deep fetch is required before this
    check can be applied.
    """
    if not extract_status(ord_record):
        return False
    end = operational_end(ord_record)
    if end is None:
        return True
    as_of = as_of or datetime.date.today()
    return end >= as_of
