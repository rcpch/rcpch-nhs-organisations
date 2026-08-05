# python imports
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


def update_organisation_model_with_ORD_changes(
    dry_run=False, stdout=None, time_frame=30
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
    backfill workflow (see documentation/docs/developer/backfill-plan.md).

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
        # The /sync endpoint returns LastChangeDate per organisation — the date
        # the change actually happened on the ODS side. Surface it in the
        # dry-run report so operators can decide whether to apply the change
        # as forward-looking (effective today) or as a backfill (effective on
        # the LastChangeDate). See backfill-plan.md.
        ods_change_date = org_link.get("LastChangeDate")
        organisation = match_organisation(ods_code=ods_code)
        if organisation:
            ord_record = get_organisation(org_link["OrgLink"])
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
            if dry_run:
                report_lines.append(
                    f"### Organisation {ods_code} ({organisation.name})"
                )
                report_lines.append("")
                report_lines.append(
                    f"ODS last change date: {ods_change_date or 'unknown'}"
                )
                report_lines.append(
                    f"Effective date applied: {effective_date.isoformat()}"
                )
                report_lines.append("")
                report_lines.append("| Field | Old | New |")
                report_lines.append("|---|---|---|")
                for field, (old, new) in changes.items():
                    report_lines.append(f"| {field} | {old} | {new} |")
                report_lines.append("")
            else:
                update_organisation_attributes(
                    organisation, effective_date=effective_date, **{
                        k: v[1] for k, v in changes.items()
                    }
                )
                logger.info("Organisation %s details have been updated.", ods_code)
        else:
            trust = match_trust(ods_code=ods_code)
            if trust:
                ord_record = get_organisation(org_link["OrgLink"])
                new_fields = _extract_ord_fields(ord_record)
                # Trust uses address_line_1 / address_line_2 / town rather than
                # address1 / address2 / city. Map the ORD fields across.
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
                if dry_run:
                    report_lines.append(
                        f"### Trust {ods_code} ({trust.name})"
                    )
                    report_lines.append("")
                    report_lines.append(
                        f"ODS last change date: {ods_change_date or 'unknown'}"
                    )
                    report_lines.append(
                        f"Effective date applied: {effective_date.isoformat()}"
                    )
                    report_lines.append("")
                    report_lines.append("| Field | Old | New |")
                    report_lines.append("|---|---|---|")
                    for field, (old, new) in changes.items():
                        report_lines.append(f"| {field} | {old} | {new} |")
                    report_lines.append("")
                else:
                    update_trust_attributes(
                        trust, effective_date=effective_date, **{
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
