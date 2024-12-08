import requests
from requests.exceptions import HTTPError
import os


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

    request_url = f"{url}/postcodes/{postcode}"

    try:
        response = requests.get(
            url=request_url,
            timeout=10,  # times out after 10 seconds
        )
        response.raise_for_status()
    except HTTPError as e:
        print(e.response.text)
        print(f"{postcode} not found")
        return None

    return response.json()["result"]
