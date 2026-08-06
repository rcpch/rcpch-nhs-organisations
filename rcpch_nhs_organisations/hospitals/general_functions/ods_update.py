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


def match_organisation(ods_code):
    """
    Accepts ODS code and checks if it exists in the Organisation model
    If there is a match, the object is returned.
    If no match, None is returned.
    """
    Organisation = apps.get_model("hospitals", "Organisation")
    try:
        organisation = Organisation.objects.get(ods_code=ods_code)
    except Organisation.DoesNotExist:
        return None

    return organisation


def match_trust(ods_code):
    """
    Accepts ODS code and checks if it exists in the Organisation model
    If there is a match, the object is returned.
    If no match, None is returned.
    """
    Trust = apps.get_model("hospitals", "Trust")
    try:
        trust = Trust.objects.get(ods_code=ods_code)
    except Trust.DoesNotExist:
        return None

    return trust


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
        {"type": "Successor", "date": "2021-10-01", "target_ods_code": "RM3"}
    Returns an empty list if the record has no ``Succs`` block.
    """
    succs = ord_record.get("Succs", {}).get("Succ", [])
    if isinstance(succs, dict):
        succs = [succs]

    events = []
    for succ in succs:
        succ_type = succ.get("Type")
        target_ods_code = succ.get("Target", {}).get("OrgId", {}).get("extension")
        # The date is in a list of {Type, Start} dicts; use the Legal date.
        legal_date = None
        for d in succ.get("Date", []):
            if d.get("Type") == "Legal":
                legal_date = d.get("Start")
                break
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


def _parse_ods_date(date_str):
    """Parse an ODS date string (YYYY-MM-DD) into a datetime.date.
    Returns None if the string is None or cannot be parsed."""
    if not date_str:
        return None
    try:
        return datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _recent_succession_events(succession_events, time_frame, reference_date=None):
    """Filter succession events to only those whose legal date falls within
    the ``time_frame`` window ending at ``reference_date`` (default: today).

    A succession event that happened 12 years ago is part of the entity's
    permanent ODS record — it will appear on every fetch of that entity, even
    for a routine website update in 2026. Gating every change on every
    succession event would force the operator to review routine updates that
    have nothing to do with a merger that happened over a decade ago.

    This filter restricts the review-gating to succession events whose legal
    date is within the ``time_frame`` window (e.g. the last 185 days), so only
    plausibly-related mergers trigger the review. The dry-run report still
    surfaces *all* succession events for context.
    """
    if reference_date is None:
        reference_date = timezone.now().date()
    window_start = reference_date - timezone.timedelta(days=time_frame)
    recent = []
    for ev in succession_events:
        if ev["date"] is None:
            continue
        try:
            ev_date = datetime.date.fromisoformat(ev["date"])
        except (ValueError, TypeError):
            continue
        if window_start <= ev_date <= reference_date:
            recent.append(ev)
    return recent


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


def _review_succession_change(
    review_callback,
    *,
    entity_type,
    ods_code,
    name,
    changes,
    succession_events,
    ods_change_date,
    effective_date,
):
    """Invoke the review callback for a merger-driven change.

    If ``review_callback`` is None (e.g. running from a script or the GitHub
    Action), return False so the change is skipped — merger-driven changes
    must not be applied without human review.

    If the callback returns True, the change is applied as a forward-looking
    change (effective today). If it returns False, the change is skipped
    with a warning, so the operator can handle it via the merger workflow or
    the ``backfill_*`` helpers.
    """
    if review_callback is None:
        return False
    return review_callback(
        {
            "entity_type": entity_type,
            "ods_code": ods_code,
            "name": name,
            "changes": changes,
            "succession_events": succession_events,
            "ods_change_date": ods_change_date,
            "effective_date": effective_date,
        }
    )


def update_organisation_model_with_ORD_changes(
    dry_run=False, stdout=None, time_frame=30, review_callback=None
):
    """
    Calls ORD API for updates in the last `time_frame` days.
    Iterates the response and searches the database for organisation and trust
    matches against ODS code. If matches, updates with new details.

    When dry_run is False, attribute changes are routed through the temporal
    helpers (update_organisation_attributes / update_trust_attributes) so that
    the previous state is recorded in the *Version tables before being
    overwritten. This is the sanctioned write path into the temporal layer.

    When dry_run is True, no writes occur. A markdown report of what *would*
    change is written to `stdout` (or the logger if stdout is None), listing
    per affected entity the field, old value, new value, the ODS last change
    date (when the change actually happened, surfaced from the /sync
    endpoint), and the effective date that would be applied (today). This is
    used by the GitHub Action for ODS change detection (see
    documentation/docs/developer/temporal-history.md) and by the `--time-frame`
    backfill workflow (see documentation/docs/developer/backfill.md).

    When a change has ODS succession events (merger / acquisition / split)
    and dry_run is False, the change is **not applied automatically**. Instead
    `review_callback` is invoked with a dict describing the entity, the
    changes, and the succession events. If the callback returns True the
    change is applied as a forward-looking change (effective today); if it
    returns False (or if review_callback is None) the change is skipped with
    a warning, so the operator can handle it via the merger workflow or the
    `backfill_*` helpers. Changes without succession events are applied
    automatically as before.

    Returns True if any changes were found (or would be applied), False
    otherwise. In dry-run mode this lets the caller decide whether to open a
    GitHub issue.
    """
    from .membership import (
        update_organisation_attributes,
        update_trust_attributes,
    )

    ord_updated_list = fetch_updated_organisations(time_frame=time_frame)

    report_lines = []
    changes_found = False
    effective_date = timezone.now().date()

    for org_link in ord_updated_list:
        ods_code = extract_ods_code(org_link=org_link["OrgLink"])
        organisation = match_organisation(ods_code=ods_code)
        if organisation:
            ord_record = get_organisation(org_link["OrgLink"])
            # LastChangeDate is on the full organisation record (fetched via
            # get_organisation), NOT on the /sync list item (which only has
            # OrgLink). Surface it in the dry-run report so operators can
            # decide whether to apply the change as forward-looking (effective
            # today) or as a backfill (effective on the LastChangeDate). See
            # backfill.md.
            ods_change_date = ord_record.get("LastChangeDate")
            # Succession (merger / acquisition / split) info from the Succs
            # block. Surfaced in the dry-run report so operators can see
            # whether a name/active change is the consequence of a merger.
            succession_events = _extract_succession_info(ord_record)
            new_fields = _extract_ord_fields(ord_record)
            changes = _diff_fields(
                organisation,
                new_fields,
                [
                    "name",
                    "address1",
                    "address2",
                    "address3",
                    "city",
                    "county",
                    "postcode",
                    "telephone",
                    "website",
                ],
            )
            if not changes:
                continue
            changes_found = True
            # Parse the ODS LastChangeDate for use as the backfill valid_from.
            ods_change_date_parsed = _parse_ods_date(ods_change_date)
            if dry_run:
                report_lines.append(
                    f"### Organisation {ods_code} ({organisation.name})"
                )
                report_lines.append("")
                report_lines.append(
                    f"ODS last change date: {ods_change_date or 'unknown'}"
                )
                # For non-merger changes, the change will be backfilled at the
                # ODS date. For merger-driven changes, it would be applied at
                # today (forward-looking) if the operator agrees.
                recent_succession_events = _recent_succession_events(
                    succession_events, time_frame, reference_date=effective_date
                )
                if recent_succession_events:
                    report_lines.append(
                        f"Effective date if applied: {effective_date.isoformat()} "
                        "(forward-looking — merger-driven change requires review)"
                    )
                else:
                    applied_date = ods_change_date_parsed or effective_date
                    report_lines.append(
                        f"Effective date applied: {applied_date.isoformat()} "
                        "(backfilled at ODS change date)"
                    )
                if succession_events:
                    report_lines.append("")
                    report_lines.append(
                        "**This organisation has succession events "
                        "(merger/acquisition/split) recorded in ODS:**"
                    )
                    for ev in succession_events:
                        report_lines.append(
                            f"- {ev['type']} → {ev['target_ods_code']} "
                            f"(legal date: {ev['date'] or 'unknown'})"
                        )
                    report_lines.append(
                        "If the change above is the consequence of this "
                        "succession, record it via the admin or the "
                        "`backfill_*` helpers, not the forward-looking sync."
                    )
                report_lines.append("")
                report_lines.append("| Field | Old | New |")
                report_lines.append("|---|---|---|")
                for field, (old, new) in changes.items():
                    report_lines.append(f"| {field} | {old} | {new} |")
                report_lines.append("")
            else:
                # Only gate on succession events whose legal date falls
                # within the time_frame window. A merger that happened 12
                # years ago is part of the entity's permanent ODS record and
                # will appear on every fetch; gating routine website updates
                # on it would force the operator to review every change.
                recent_succession_events = _recent_succession_events(
                    succession_events, time_frame, reference_date=effective_date
                )
                if recent_succession_events:
                    # Merger-driven change: do not apply automatically.
                    # Prompt the operator via the review callback; skip if
                    # they refuse or if no callback is provided (e.g. running
                    # from a script). If accepted, apply at today's date
                    # (forward-looking) — the operator should use the
                    # backfill_* helpers if the historical date matters.
                    apply = _review_succession_change(
                        review_callback,
                        entity_type="Organisation",
                        ods_code=ods_code,
                        name=organisation.name,
                        changes=changes,
                        succession_events=recent_succession_events,
                        ods_change_date=ods_change_date,
                        effective_date=effective_date,
                    )
                    if not apply:
                        logger.warning(
                            "Organisation %s has recent succession events; "
                            "change skipped. Handle via the admin or the "
                            "backfill_* helpers.",
                            ods_code,
                        )
                        continue
                    update_organisation_attributes(
                        organisation, effective_date=effective_date, **{
                            k: v[1] for k, v in changes.items()
                        }
                    )
                else:
                    # Non-merger change (address, website, telephone, etc.):
                    # apply at the ODS LastChangeDate so the version row records
                    # when the change actually happened, not today. We use the
                    # forward-looking update_*_attributes helper (which updates
                    # the entity row in place and closes/opens version rows) but
                    # with effective_date set to the ODS date.
                    applied_date = ods_change_date_parsed or effective_date
                    update_organisation_attributes(
                        organisation, effective_date=applied_date, **{
                            k: v[1] for k, v in changes.items()
                        }
                    )
                logger.info("Organisation %s details have been updated.", ods_code)
        else:
            trust = match_trust(ods_code=ods_code)
            if trust:
                ord_record = get_organisation(org_link["OrgLink"])
                ods_change_date = ord_record.get("LastChangeDate")
                succession_events = _extract_succession_info(ord_record)
                # Trust uses address_line_1 / address_line_2 / town rather than
                # address1 / address2 / city. Map the ORD fields across.
                new_fields = _extract_ord_fields(ord_record)
                trust_new = {
                    "name": new_fields.get("name"),
                    "address_line_1": new_fields.get("address1"),
                    "address_line_2": new_fields.get("address2"),
                    "town": new_fields.get("city"),
                    "postcode": new_fields.get("postcode"),
                    "telephone": new_fields.get("telephone"),
                    "website": new_fields.get("website"),
                }
                changes = _diff_fields(
                    trust,
                    trust_new,
                    [
                        "name",
                        "address_line_1",
                        "address_line_2",
                        "town",
                        "postcode",
                        "telephone",
                        "website",
                    ],
                )
                if not changes:
                    continue
                changes_found = True
                ods_change_date_parsed = _parse_ods_date(ods_change_date)
                if dry_run:
                    report_lines.append(
                        f"### Trust {ods_code} ({trust.name})"
                    )
                    report_lines.append("")
                    report_lines.append(
                        f"ODS last change date: {ods_change_date or 'unknown'}"
                    )
                    recent_succession_events = _recent_succession_events(
                        succession_events, time_frame, reference_date=effective_date
                    )
                    if recent_succession_events:
                        report_lines.append(
                            f"Effective date if applied: {effective_date.isoformat()} "
                            "(forward-looking — merger-driven change requires review)"
                        )
                    else:
                        applied_date = ods_change_date_parsed or effective_date
                        report_lines.append(
                            f"Effective date applied: {applied_date.isoformat()} "
                            "(backfilled at ODS change date)"
                        )
                    if succession_events:
                        report_lines.append("")
                        report_lines.append(
                            "**This trust has succession events "
                            "(merger/acquisition/split) recorded in ODS:**"
                        )
                        for ev in succession_events:
                            report_lines.append(
                                f"- {ev['type']} → {ev['target_ods_code']} "
                                f"(legal date: {ev['date'] or 'unknown'})"
                            )
                        report_lines.append(
                            "If the change above is the consequence of this "
                            "succession, record it via the admin or the "
                            "`backfill_*` helpers, not the forward-looking sync."
                        )
                    report_lines.append("")
                    report_lines.append("| Field | Old | New |")
                    report_lines.append("|---|---|---|")
                    for field, (old, new) in changes.items():
                        report_lines.append(f"| {field} | {old} | {new} |")
                    report_lines.append("")
                else:
                    recent_succession_events = _recent_succession_events(
                        succession_events, time_frame, reference_date=effective_date
                    )
                    if recent_succession_events:
                        apply = _review_succession_change(
                            review_callback,
                            entity_type="Trust",
                            ods_code=ods_code,
                            name=trust.name,
                            changes=changes,
                            succession_events=recent_succession_events,
                            ods_change_date=ods_change_date,
                            effective_date=effective_date,
                        )
                        if not apply:
                            logger.warning(
                                "Trust %s has recent succession events; "
                                "change skipped. Handle via the admin or "
                                "the backfill_* helpers.",
                                ods_code,
                            )
                            continue
                        update_trust_attributes(
                            trust, effective_date=effective_date, **{
                                k: v[1] for k, v in changes.items()
                            }
                        )
                    else:
                        # Non-merger change: apply at the ODS LastChangeDate.
                        applied_date = ods_change_date_parsed or effective_date
                        update_trust_attributes(
                            trust, effective_date=applied_date, **{
                                k: v[1] for k, v in changes.items()
                            }
                        )
                    logger.info("Trust %s details have been updated.", ods_code)

    if dry_run:
        report = "\n".join(report_lines)
        if stdout is not None:
            stdout.write(report)
        else:
            logger.info("Dry-run report:\n%s", report)
    else:
        if changes_found:
            logger.info(
                "Updates have been made to existing records in the RCPCH database."
            )
        else:
            logger.info(
                "No updates have been made to existing records in the RCPCH database."
            )

    return changes_found


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
