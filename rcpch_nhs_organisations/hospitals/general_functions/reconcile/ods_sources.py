"""
ODS data sources for the reconciliation engine.

Three ODS sources are used together (see
documentation/docs/developer/ods-sync.md, "Detection mechanism"):

1. ``/sync?LastChangeDate=`` — the cheap trigger feed (already wrapped by
   ``fetch_updated_organisations`` in ``ods_update.py``).
2. ``/organisations?PrimaryRoleId={role}&Limit=500`` — the roster per level,
   with ``Status`` and ``LastChangeDate``. Used for trust / LHB / ICB presence
   and status reconciliation (the organisation level is a closed set and is not
   roster-reconciled). Implemented here as ``fetch_roster``.
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

# ODS PrimaryRoleId codes for the four in-scope levels. The organisation level
# (RO198 trust site / RO144 LHB site) is deliberately not roster-reconciled —
# it is a closed set followed only along succession chains.
ROLE_TRUST = "RO197"
ROLE_LHB = "RO142"
ROLE_ICB = "RO261"

# Map a reconcile level to its roster PrimaryRoleId.
LEVEL_ROLE_IDS = {
    "trust": ROLE_TRUST,
    "lhb": ROLE_LHB,
    "icb": ROLE_ICB,
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


def fetch_roster(role_id, limit=500, rate_limiter=None):
    """Fetch the full ODS roster for a PrimaryRoleId.

    Returns a list of dicts, one per organisation, each carrying at least
    ``OrgId`` (the ODS code), ``Name``, ``Status`` ("Active"/"Inactive"), and
    ``LastChangeDate``. This is the directory roster used for trust / LHB / ICB
    presence and status reconciliation.

    ``all_nhs_hospitals_list`` uses a different NHS API and cannot be reused for
    this — the ODS directory roster carries the ``Status`` flag the engine needs.
    """
    if rate_limiter is not None:
        rate_limiter.acquire()
    request_url = (
        f"{_base_url()}/organisations?PrimaryRoleId={role_id}&Limit={limit}"
    )
    try:
        response = requests.get(url=request_url, timeout=30)
        response.raise_for_status()
    except HTTPError as e:
        logger.error("ODS roster fetch failed for %s: %s", role_id, e)
        raise
    return response.json().get("Organisations", [])


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
