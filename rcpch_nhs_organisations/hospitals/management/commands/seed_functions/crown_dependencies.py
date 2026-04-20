# python imports
from datetime import date
import logging

# Django imports
from django.apps import apps
from django.contrib.gis.geos import Point

# Local imports
from rcpch_nhs_organisations.hospitals.constants import (
    JERSEY_ORGANISATION,
    JERSEY_NHS_TRUST,
    NOBLES_HOSPITAL_ISLE_OF_MAN_ORGANISATION,
    NOBLES_HOSPITAL_ISLE_OF_MAN_NHS_TRUST
)

logger = logging.getLogger(__name__)


def create_crown_dependency_hospital(country, organisation, trust, openuk_network):
    Organisation = apps.get_model("hospitals", "Organisation")
    Trust = apps.get_model("hospitals", "Trust")

    if Organisation.objects.filter(
        ods_code=organisation["OrganisationCode"]
    ).exists():
        logger.info(f"{organisation['OrganisationName']} already exists. Skipping creation.")
        return

    trust = Trust.objects.create(
        ods_code=trust["ods_code"],
        name=trust["trust_name"],
        address_line_1=trust["address_line_1"],
        address_line_2=trust["address_line_2"],
        town=trust["town"],
        postcode=trust["postcode"],
        country=country.name,
        telephone=None,
        website=None,
        active=True,
        published_at=date(2015, 4, 1),
    )

    Organisation.objects.create(
        ods_code=organisation["OrganisationCode"],
        name=organisation["OrganisationName"],
        website=organisation["Website"],
        address1=organisation["Address1"],
        address2=organisation["Address2"],
        address3=organisation["Address3"],
        city=organisation["City"],
        county=organisation["County"],
        latitude=float(organisation["Latitude"]),
        longitude=float(organisation["Longitude"]),
        postcode=organisation["Postcode"],
        geocode_coordinates=Point(
            x=float(organisation["Longitude"]),
            y=float(organisation["Latitude"]),
        ),
        telephone=organisation["Phone"],
        active=True,
        published_at=date(2015, 4, 1),
        country=country,
        trust=trust,
        local_health_board=None,
        openuk_network=openuk_network,
        nhs_england_region=None,
        integrated_care_board=None,
        london_borough=None,
    )

    logger.info(f"{organisation['OrganisationName']} created and all relationships added....")


def seed_crown_dependencies():
    Country = apps.get_model("hospitals", "Country")

    OPENUKNetwork = apps.get_model("hospitals", "OPENUKNetwork")

    swipe = OPENUKNetwork.objects.get(boundary_identifier="SWIPE")

    create_crown_dependency_hospital(
        country=Country.objects.get(boundary_identifier="E92000003"),
        organisation=JERSEY_ORGANISATION,
        trust=JERSEY_NHS_TRUST,
        openuk_network=swipe
    )

    create_crown_dependency_hospital(
        country=Country.objects.get(boundary_identifier="M83000003"),
        organisation=NOBLES_HOSPITAL_ISLE_OF_MAN_ORGANISATION,
        trust=NOBLES_HOSPITAL_ISLE_OF_MAN_NHS_TRUST,
        openuk_network=None
    )
