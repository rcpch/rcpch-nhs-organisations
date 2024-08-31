# standard library imports
import logging

# Django imports
from django.apps import apps
from django.contrib.gis.geos import Point

from rcpch_nhs_organisations.hospitals.constants import (
    PZ_CODES_NETWORKS,
    PAEDIATRIC_DIABETES_NETWORKS,
)


# logger setup
logger = logging.getLogger("hospitals")


def seed_paediatric_diabetes_networks():
    """
    Seeds the PaediatricDiabetesNetwork model with the data from the constants file.
    There are 12 Paediatric Diabetes Networks in the UK.
    """
    PaediatricDiabetesNetwork = apps.get_model("hospitals", "PaediatricDiabetesNetwork")
    if PaediatricDiabetesNetwork.objects.exists():
        logger.info(
            "PaediatricDiabetesNetworks already seeded. Updating existing records."
        )
    for network in PAEDIATRIC_DIABETES_NETWORKS:
        PaediatricDiabetesNetwork.objects.update_or_create(
            pn_code=network["id"],
            defaults={"name": network["name"]},
        )
        logger.info(f"Seeded PaediatricDiabetesNetwork: {network['name']}")


def update_pdu_networks():
    """
    Updates the PaediatricDiabetesUnit model with the network information held in the constants file.
    """
    PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")
    PaediatricDiabetesNetwork = apps.get_model("hospitals", "PaediatricDiabetesNetwork")

    if PaediatricDiabetesUnit.objects.exists():
        logger.info(
            "PaediatricDiabetesUnits already seeded. Updating existing records."
        )
    for pdu in PZ_CODES_NETWORKS:
        paediatric_network = PaediatricDiabetesNetwork.objects.filter(
            pn_code=pdu["network_code"]
        )
        if not paediatric_network.exists():
            logger.error(
                f"Network: {pdu['network_code']} does not exist in the database."
            )
            continue
        else:
            paediatric_network = paediatric_network.get()
        PaediatricDiabetesUnit.objects.update_or_create(
            pz_code=pdu["npda_code"],
            defaults={"paediatric_diabetes_network": paediatric_network},
        )
