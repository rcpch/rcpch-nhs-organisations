"""
Functions to interact with the RCPCH instance of the Postcodes API
"""

# Python imports
import requests
from requests.exceptions import HTTPError
import os

# Django imports
from django.apps import apps


def fetch_by_postcode(postcode: str):
    """
    Returns data object from the Postcode API for a given postcode
    Includes:
    - longitude, latitude
    - northings, eastings
    - country, nhs_ha, european_electoral_region, primary_care_trust
    - region, lsoa, msoa, incode, outcode
    - parliamentary_constituency, admin_district, parish, admin_county, admin_ward
    codes for all of the above
    """

    url = os.getenv("POSTCODES_IO_API_URL")
    api_key = os.getenv("POSTCODES_IO_API_KEY")

    request_url = f"{url}/postcodes/{postcode}"

    try:
        response = requests.get(
            url=request_url,
            timeout=10,  # times out after 10 seconds
            headers={"Ocp-Apim-Subscription-Key": api_key},
        )
        response.raise_for_status()
    except HTTPError as e:
        print(e.response.text)
        print(f"{postcode} not found")
        return None

    return response.json()["result"]


def generate_lsoa_lad_for_all_organisations():
    """
    Generates a dictionary of LSOA and LAD codes for all organisations
    """
    Organisation = apps.get_model("hospitals", "Organisation")
    LocalAuthorityDistrict = apps.get_model("hospitals", "LocalAuthorityDistrict")
    all_codes = []
    for organisation in Organisation.objects.all()[:10]:
        if organisation.postcode:
            new_code = {
                "lsoa_code": None,
                "lad_code": None,
                "ods_code": organisation.ods_code,
            }
            postcode_data = fetch_by_postcode(organisation.postcode)
            if postcode_data:
                new_code["lsoa_code"] = postcode_data["codes"]["lsoa"]
                new_code["lad_code"] = postcode_data["codes"]["admin_district"]
                new_code["ods_code"] = organisation.ods_code
                all_codes.append(new_code)
                if LocalAuthorityDistrict.objects.filter(
                    lad24cd=new_code["lad_code"]
                ).exists():
                    organisation.local_authority_district = (
                        LocalAuthorityDistrict.objects.get(lad24cd=new_code["lad_code"])
                    )
                    organisation.save()

                print(
                    f"{organisation.name} updated with LSOA {new_code['lsoa_code']} and LAD {new_code['lad_code']} codes"
                )
            else:
                print(f"{organisation.name} not updated")
        else:
            print(f"{organisation.name} has no postcode")

    # save the codes to a file
    with open("lsoa_lad_codes.txt", "w") as f:
        f.write(str(all_codes))
    print("Codes saved to file")
