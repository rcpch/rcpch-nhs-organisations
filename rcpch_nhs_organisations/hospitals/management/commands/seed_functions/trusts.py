import logging

# Logging setup
logger = logging.getLogger("hospitals")

# Django imports
from django.apps import apps

# RCPCH imports
from rcpch_nhs_organisations.hospitals.constants import TRUSTS


def seed_trusts():
    """
    Seed function which populates the Trust table from JSON and links to BoundaryEntity table.
    Also links all items of the LocalHealthBoard table to the BoundaryEntity model
    By the end of this function, the 7 LocalHealthBoard records should have a corresponding record in BoundaryEntity
    By the end of this function, the 138 Trust records should have a corresponding record in BoundaryEntity
    All 235 records will be associated with a country
    """

    # Get models
    Trust = apps.get_model("hospitals", "Trust")

    if Trust.objects.all().count() == 242:
        logging_message = "242 Trusts already seeded. Skipping..."
        logger.info(logging_message)
    else:
        logger.info("Adding new Trusts...")

        for added, trust in enumerate(TRUSTS):
            try:
                Trust.objects.create(
                    ods_code=trust["ods_code"],
                    name=trust["trust_name"],
                    address_line_1=trust["address_line_1"],
                    address_line_2=trust.get("address_line_2"),
                    town=trust["town"],
                    postcode=trust["postcode"],
                    country=trust["country"],
                ).save()
                logger.info(f"{added+1}: {trust['trust_name']}")
            except Exception as error:
                error_message = f"Unable to save {trust['trust_name']}: {error}"
                logger.error(error_message)

        logging_message = f"{added+1} trusts added."
        logger.info(logging_message)
