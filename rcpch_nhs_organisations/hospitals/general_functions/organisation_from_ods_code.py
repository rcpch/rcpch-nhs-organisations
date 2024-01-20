import requests
from requests.exceptions import HTTPError
import os


def fetch_organisation_by_ods_code(ods_code: str):
    """
    Returns GP Practice/hospital for ODS Code
    """

    url = os.getenv("NHS_ODS_API_URL")

    request_url = f"{url}/organisations/{ods_code}"

    try:
        response = requests.get(
            url=request_url,
            timeout=10,  # times out after 10 seconds
        )
        response.raise_for_status()
    except HTTPError as e:
        print(e.response.text)
        print(f"{ods_code} not found")
        return None

    return response.json()["Organisation"]
