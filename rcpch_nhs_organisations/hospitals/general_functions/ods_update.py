# python imports
import requests
from requests.exceptions import HTTPError
import os

# django imports
from django.conf import settings
from django.utils import timezone, dateformat
from django.apps import apps


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
        print(e.response.text)

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


def update_organisation_model_with_ORD_changes():
    """
    Calls ORD API for updates in the last 30 days.
    Iterates response and searches database for organisation matches
    If matches, updates with new details
    """

    ord_updated_list = fetch_updated_organisations(time_frame=30)

    for index, org_link in enumerate(ord_updated_list):
        ods_code = extract_ods_code(org_link=org_link["OrgLink"])
        organisation = match_organisation(ods_code=ods_code)
        if organisation:
            print(
                f"{index}. {ods_code} has a match with {organisation} in the RCPCH Census Platform database"
            )
            ord_organisation_update = get_organisation(org_link["OrgLink"])
            organisation.name = ord_organisation_update["Name"]
            organisation.address1 = ord_organisation_update["GeoLoc"]["Location"][
                "AddrLn1"
            ]
            organisation.address2 = ord_organisation_update["GeoLoc"]["Location"][
                "AddrLn2"
            ]
            organisation.city = ord_organisation_update["GeoLoc"]["Location"]["Town"]
            organisation.postcode = ord_organisation_update["GeoLoc"]["Location"][
                "PostCode"
            ]
            organisation.telephone = ord_organisation_update["Contacts"]["Contact"][
                "value"
            ]
            organisation.save(
                update_fields=["name", "address1", "address2", "city", "postcode"]
            )
        else:
            print(f"No match with organisation {ods_code}")
            trust = match_trust(ods_code=ods_code)
            if trust:
                print(
                    f"{index}. {ods_code} has a match with {trust} in the RCPCH Census Platform database"
                )
                ord_trust_update = get_organisation(org_link["OrgLink"])
                trust.name = ord_trust_update["Name"]
                trust.address_line_1 = ord_trust_update["GeoLoc"]["Location"]["AddrLn1"]
                try:
                    line_two = ord_trust_update["GeoLoc"]["Location"]["AddrLn2"]
                    trust.address_line_1 = line_two
                except Exception:
                    pass

                trust.town = print(ord_trust_update["GeoLoc"]["Location"]["Town"])
                trust.postcode = print(
                    ord_trust_update["GeoLoc"]["Location"]["PostCode"]
                )

                for i in ord_trust_update["Contacts"]["Contact"]:
                    if i["type"] == "http":
                        trust.website = i["value"]
                    else:
                        trust.telephone = i["value"]
                trust.save()

            else:
                print("No match with Trust either")
