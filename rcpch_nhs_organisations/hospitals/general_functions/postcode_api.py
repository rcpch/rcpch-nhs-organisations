import requests
from requests.exceptions import HTTPError
import os


def fetch_by_postcode(postcode: str):
    """
    Returns GP Practice/hospital for ODS Code
    """

    url = os.getenv("POSTCODE_API_BASE_URL")

    request_url = f"{url}/postcodes/{postcode}.json"

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

    return response.json()["data"]["attributes"]
