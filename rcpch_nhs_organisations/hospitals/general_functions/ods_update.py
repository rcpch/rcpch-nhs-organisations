# python imports
import datetime
import requests
from requests.exceptions import HTTPError
import os
import logging

# django imports
from django.conf import settings
from django.utils import timezone, dateformat
from django.apps import apps

logger = logging.getLogger("hospitals")


def fetch_updated_organisations(time_frame: int = 30):
    """
    Returns a list of organisations from the NHS ODS API who have updated their details or relationships
    Accepts time_frame as number of days as an integer upto 185 days
    """

    if time_frame is None:
        raise ValueError("ODS API error: a valid number of days must be supplied.")
    elif time_frame > 185:
        raise ValueError(
            "ODS API error: changes to organisations greater than 185 days ago cannot be retrieved from the NHS ODS API."
        )

    since_date = dateformat.format(
        timezone.now() - timezone.timedelta(days=time_frame), "Y-m-d"
    )

    url = os.getenv("NHS_ODS_API_URL")

    request_url = f"{url}/sync?LastChangeDate={since_date}"

    try:
        response = requests.get(
            url=request_url,
            timeout=10,  # times out after 10 seconds
        )
        response.raise_for_status()
    except HTTPError as e:
        logger.error(e.response.text)

    return response.json()["Organisations"]


def get_organisation(org_link):
    """
    Returns the organisation from ORD API using the link supplied by the ORD API
    """

    try:
        response = requests.get(url=org_link, timeout=10)
        response.raise_for_status()
    except HTTPError as e:
        print(e.response.text)

    return response.json()["Organisation"]


def extract_ods_code(org_link: str):
    """
    Extracts the ODS code from the link in the list returned from ORD API
    """
    ods_code = org_link.rsplit("/", 1)

    return ods_code[1]


def _extract_ord_fields(ord_record):
    """
    Extract the mutable fields we care about from an ORD organisation record.
    Returns a dict keyed by the field names used on the Organisation / Trust
    models. Missing keys default to None.
    """
    location = ord_record.get("GeoLoc", {}).get("Location", {})
    contacts = ord_record.get("Contacts", {}).get("Contact", [])
    # Contacts may be a single dict or a list of dicts; normalise to a list.
    if isinstance(contacts, dict):
        contacts = [contacts]

    telephone = None
    website = None
    for contact in contacts:
        if contact.get("type") == "http":
            website = contact.get("value")
        else:
            telephone = contact.get("value")

    return {
        "name": ord_record.get("Name"),
        "address1": location.get("AddrLn1"),
        "address2": location.get("AddrLn2"),
        "address3": location.get("AddrLn3"),
        "city": location.get("Town"),
        "county": location.get("County"),
        "postcode": location.get("PostCode"),
        "telephone": telephone,
        "website": website,
    }


def _extract_succession_info(ord_record):
    """
    Extract succession (merger / acquisition / split) information from an
    ORD organisation record's ``Succs`` block.

    The ODS ``Succs`` block records legal succession events. Each ``Succ`` has
    a ``Type`` (``"Successor"`` = this org was absorbed into the target;
    ``"Predecessor"`` = this org absorbed the target), a legal date, and a
    target ODS code. This is surfaced in the dry-run report so operators can
    see whether a name/active change is the consequence of a merger and, if so,
    record it manually via the admin or the ``backfill_*`` helpers.

    Returns a list of dicts, one per succession event:
        {"type": "Successor", "date": datetime.date(2021, 10, 1), "target_ods_code": "RM3"}
    ``date`` is a ``datetime.date`` (parsed from the ODS ISO-8601 string), or
    ``None`` if the ``Succ`` block has no Legal date. Returns an empty list if
    the record has no ``Succs`` block.
    """
    succs = ord_record.get("Succs", {}).get("Succ", [])
    if isinstance(succs, dict):
        succs = [succs]

    events = []
    for succ in succs:
        succ_type = succ.get("Type")
        target_ods_code = succ.get("Target", {}).get("OrgId", {}).get("extension")
        # The date is in a list of {Type, Start} dicts; use the Legal date.
        # ODS returns ISO-8601 strings (e.g. "2021-10-01"); parse to datetime.date
        # so consumers don't have to. None is preserved if no Legal date is present.
        legal_date = None
        for d in succ.get("Date", []):
            if d.get("Type") == "Legal":
                legal_date = d.get("Start")
                break
        if legal_date:
            legal_date = datetime.date.fromisoformat(legal_date)
        if succ_type and target_ods_code:
            events.append(
                {"type": succ_type, "date": legal_date, "target_ods_code": target_ods_code}
            )
    return events


def _extract_trust_membership_info(ord_record):
    """Extract historical trust-membership intervals from an ORD organisation
    record's ``Rels`` block.

    The ODS ``Rels`` block records operational and managed relationships.
    For NHS Trust Sites (``PrimaryRoleId == RO198``), the relationship with
    ``id == "RE6"`` is the "is a site of" link to the parent NHS Trust
    (``PrimaryRoleId == RO197``). Each ``Rel`` carries an operational
    ``[Start, End]`` interval — exactly the interval needed to backfill an
    ``OrganisationTrustMembership`` row.

    This is the recovery path for Layer 2 of the temporal history design
    (see ``backfill.md`` Part 3, "What the command does not recover").
    Unlike the ``/sync`` endpoint, ``/organisations/{ods_code}`` returns the
    full ``Rels`` history regardless of when the relationship ended, so this
    recovers memberships that were overwritten before the temporal layer
    was installed.

    Returns a list of dicts, one per RE6 rel, ordered by start date:
        {"trust_ods_code": "RA7", "valid_from": "1991-04-01", "valid_to": None}
    ``valid_to`` is ``None`` if the rel is still active (the open interval).
    Returns an empty list if the record has no ``Rels`` block or no RE6 rels.
    """
    rels = ord_record.get("Rels", {}).get("Rel", [])
    if isinstance(rels, dict):
        rels = [rels]

    memberships = []
    for rel in rels:
        if rel.get("id") != "RE6":
            continue
        target = rel.get("Target", {})
        # Only NHS Trusts (RO197) are parents under RE6. Other target roles
        # (e.g. RO261 ICBs under RE5/RE8) are commissioning relationships,
        # not parent-trust memberships, and are ignored here.
        target_role = target.get("PrimaryRoleId", {}).get("id")
        if target_role != "RO197":
            continue
        trust_ods_code = target.get("OrgId", {}).get("extension")
        if not trust_ods_code:
            continue

        # The Date list has {Type, Start, End} dicts. Use the Operational
        # interval — that is when the site actually reported to the trust.
        # Legal and Operational dates can differ; Operational is what audit
        # reports need (when the hospital actually sat under that parent).
        valid_from = None
        valid_to = None
        for d in rel.get("Date", []):
            if d.get("Type") == "Operational":
                valid_from = d.get("Start")
                valid_to = d.get("End")  # may be None (open interval)
                break

        # If no Operational date is present, fall back to Legal. Some older
        # ODS records only carry the Legal interval.
        if valid_from is None:
            for d in rel.get("Date", []):
                if d.get("Type") == "Legal":
                    valid_from = d.get("Start")
                    valid_to = d.get("End")
                    break

        if valid_from is None:
            # No date at all — cannot place this membership in time. Skip it
            # rather than write an undated row.
            continue

        memberships.append(
            {
                "trust_ods_code": trust_ods_code,
                "valid_from": valid_from,
                "valid_to": valid_to,
            }
        )

    memberships.sort(key=lambda m: m["valid_from"])
    return memberships


# RE5 and RE8 are the ODS relationship types for commissioning / managed-by
# relationships from a trust (RO197) to an ICB (RO261). RE5 ("managed by /
# reports to") is the primary commissioning link; RE8 ("operates / is
# operated by") appeared from 2023 onwards as a second link type. Both
# point at ICBs (RO261) in current data; historically they pointed at CCGs
# (RO210) and STPs (RO132), which are ignored — only ICB affiliations are
# recovered. See documentation/docs/developer/icb-history.md.
ICB_REL_IDS = ("RE5", "RE8")
ICB_TARGET_ROLE = "RO261"


def _extract_icb_membership_info(ord_record):
    """Extract historical ICB-membership intervals from an ORD organisation
    record's ``Rels`` block.

    For NHS Trusts (``PrimaryRoleId == RO197``), the ``RE5`` and ``RE8`` rels
    pointing at ICBs (``PrimaryRoleId == RO261``) record the commissioning
    relationship with operational ``[Start, End]`` intervals. This function
    extracts those intervals for backfilling ``TrustIntegratedCareBoardMembership``
    rows.

    Only ``RO261`` (ICB) targets are returned. ``RO210`` (CCG) and ``RO132``
    (STP) targets are ignored — audit reporting walks the chain
    organisation → trust/LHB → ICB → NHS England region → country, so only
    ICB-level affiliations are recovered.

    Returns a list of dicts, one per RE5/RE8 rel pointing at an ICB, ordered
    by start date:
        {"icb_ods_code": "QKS", "valid_from": "2020-04-01", "valid_to": None,
         "rel_id": "RE8", "status": "Active"}
    ``valid_to`` is ``None`` if the rel is still active (the open interval).
    ``rel_id`` is the ODS relationship id (``RE5`` legacy commissioning, which
    ODS never closes, vs ``RE8`` maintained geographic/partner). ``status`` is
    the ODS ``Status`` (``Active``/``Inactive``). Both are needed by
    :func:`build_trust_icb_timeline` to resolve the single current ICB when a
    trust carries several concurrent ICB rels. Returns an empty list if the
    record has no ``Rels`` block or no ICB rels.
    """
    rels = ord_record.get("Rels", {}).get("Rel", [])
    if isinstance(rels, dict):
        rels = [rels]

    memberships = []
    for rel in rels:
        if rel.get("id") not in ICB_REL_IDS:
            continue
        target = rel.get("Target", {})
        target_role = target.get("PrimaryRoleId", {}).get("id")
        if target_role != ICB_TARGET_ROLE:
            continue
        icb_ods_code = target.get("OrgId", {}).get("extension")
        if not icb_ods_code:
            continue

        # Use the Operational interval — that is when the trust actually
        # reported to the ICB. Fall back to Legal if Operational is absent.
        valid_from = None
        valid_to = None
        for d in rel.get("Date", []):
            if d.get("Type") == "Operational":
                valid_from = d.get("Start")
                valid_to = d.get("End")
                break
        if valid_from is None:
            for d in rel.get("Date", []):
                if d.get("Type") == "Legal":
                    valid_from = d.get("Start")
                    valid_to = d.get("End")
                    break
        if valid_from is None:
            continue

        memberships.append(
            {
                "icb_ods_code": icb_ods_code,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "rel_id": rel.get("id"),
                "status": rel.get("Status"),
            }
        )

    memberships.sort(key=lambda m: m["valid_from"])
    return memberships


def _parse_ods_date(date_str):
    """Parse an ODS date string (YYYY-MM-DD) into a datetime.date.
    Returns None if the string is None or cannot be parsed."""
    if not date_str:
        return None
    try:
        return datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


# ICB-rel precedence used when collapsing a trust's overlapping ODS ICB rels
# into a single current ICB. RE8 is the maintained geographic/partner rel and
# is kept up to date across reorganisations; RE5 is the legacy "is commissioned
# by" rel that ODS opens once (at 2020-04-01) and never closes, so it must only
# win when no RE8 rel is active.
_ICB_REL_RANK = {"RE8": 0, "RE5": 1}


def _icb_rel_rank(rel_id):
    return _ICB_REL_RANK.get(rel_id, 2)


def _choose_current_icb(active, previous_icb):
    """Pick the single current ICB from the rels active in one period.

    ``active`` is a list of parsed rels (dicts with ``icb``, ``start``,
    ``rel_id``). Precedence: maintained RE8 over legacy RE5, then the latest
    operational start (a later reorganisation supersedes an earlier one), then
    continuity with the previous period, then the alphabetically-first ICB code
    for determinism.
    """
    best_rank = min(_icb_rel_rank(p["rel_id"]) for p in active)
    candidates = [p for p in active if _icb_rel_rank(p["rel_id"]) == best_rank]
    latest_start = max(p["start"] for p in candidates)
    candidates = [p for p in candidates if p["start"] == latest_start]
    icb_codes = {p["icb"] for p in candidates}
    if previous_icb in icb_codes:
        return previous_icb
    return sorted(icb_codes)[0]


def build_trust_icb_timeline(memberships):
    """Collapse the raw ICB rels of an ODS trust record into a clean timeline.

    ``memberships`` is the output of :func:`_extract_icb_membership_info`. ODS
    carries several *concurrent* ICB rels for a single trust:

    - a legacy ``RE5`` "is commissioned by" rel that points at the trust's
      original (2020) ICB and is **never closed** (stays open forever), and
    - one or more maintained ``RE8`` geographic/partner rels that track the
      current ICB across the 2022/2023/2026 reorganisations — occasionally
      several open at once during an overlap window.

    Writing those verbatim leaves multiple ``valid_to IS NULL`` rows per trust,
    which violates the "one current ICB" invariant the audit chain
    (organisation → trust → ICB → region → country) depends on, and makes the
    reconcile detector pick an arbitrary open row.

    This resolves, for every distinct period, the single current ICB via
    :func:`_choose_current_icb`, then merges adjacent equal-ICB periods. The
    result is a list of ``{"icb_ods_code", "valid_from" (date),
    "valid_to" (date|None)}`` ordered by ``valid_from``, non-overlapping, with
    at most one open row.
    """
    parsed = []
    for m in memberships:
        start = _parse_ods_date(m["valid_from"])
        if start is None:
            continue
        end = _parse_ods_date(m["valid_to"])
        # A rel ODS marks Inactive but leaves open is treated as closed at its
        # start (defensive — real data always carries an explicit End date).
        if end is None and m.get("status") == "Inactive":
            continue
        parsed.append(
            {
                "icb": m["icb_ods_code"],
                "start": start,
                "end": end,
                "rel_id": m.get("rel_id"),
            }
        )
    if not parsed:
        return []

    # Period boundaries are every start and every (finite) end date. Each
    # boundary opens a window running to the next boundary (or to None).
    boundaries = sorted(
        {p["start"] for p in parsed}
        | {p["end"] for p in parsed if p["end"] is not None}
    )
    segments = []
    previous_icb = None
    for index, window_start in enumerate(boundaries):
        window_end = (
            boundaries[index + 1] if index + 1 < len(boundaries) else None
        )
        active = [
            p
            for p in parsed
            if p["start"] <= window_start
            and (p["end"] is None or p["end"] > window_start)
        ]
        if not active:
            continue
        chosen = _choose_current_icb(active, previous_icb)
        segments.append({"icb": chosen, "from": window_start, "to": window_end})
        previous_icb = chosen

    merged = []
    for segment in segments:
        if (
            merged
            and merged[-1]["icb"] == segment["icb"]
            and merged[-1]["to"] == segment["from"]
        ):
            merged[-1]["to"] = segment["to"]
        else:
            merged.append(dict(segment))

    return [
        {
            "icb_ods_code": s["icb"],
            "valid_from": s["from"],
            "valid_to": s["to"],
        }
        for s in merged
    ]


def current_trust_icb_code(memberships):
    """Return the ODS code of a trust's single current ICB, or None.

    Resolves the overlapping RE5/RE8 rels via :func:`build_trust_icb_timeline`
    and returns the ICB of the open (``valid_to is None``) segment.
    """
    for segment in build_trust_icb_timeline(memberships):
        if segment["valid_to"] is None:
            return segment["icb_ods_code"]
    return None


def _diff_fields(current, new, fields):
    """
    Compare the current entity's attributes against the new values from ORD.
    Returns a dict of {field: (old, new)} for fields that differ.
    """
    changes = {}
    for field in fields:
        old_value = getattr(current, field, None)
        new_value = new.get(field)
        if new_value is not None and (old_value or None) != (new_value or None):
            changes[field] = (old_value, new_value)
    return changes


def check_organisation_has_location_data():
    """
    Checks if the organisation has location data
    """
    index = 0
    Organisation = apps.get_model("hospitals", "Organisation")
    for organisation in Organisation.objects.all():
        if organisation.postcode is None:
            index += 1
            if organisation.longitude is None:
                print(f"{organisation.name} has not location data")
    print(
        f"{index} organisations have no postcode of a total {Organisation.objects.all().count()} organisations."
    )
