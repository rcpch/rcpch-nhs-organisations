# Python imports
import logging

# Django imports
from django.apps import apps

# RCPCH imports
from rcpch_nhs_organisations.hospitals.constants.organisation_ods_code_to_lsoa_lad_code_mapping import (
    ORGANISATION_TO_LSOA_LAD_MAPPING,
)

# logger setup
logger = logging.getLogger("hospitals")


# seeds the local authorities table with data from the local authorities csv file
def seed_local_authorities_and_lsoas():
    """
    Seed the Organisation table with the local authorities and LSOA data
    """
    Organisation = apps.get_model("hospitals", "Organisation")
    LocalAuthorityDistrict = apps.get_model("hospitals", "LocalAuthorityDistrict")
    LowerLayerSuperOutputArea = apps.get_model("hospitals", "LowerLayerSuperOutputArea")

    for organisation_mapping in ORGANISATION_TO_LSOA_LAD_MAPPING:
        if Organisation.objects.filter(
            ods_code=organisation_mapping["ods_code"]
        ).exists():
            organisation = Organisation.objects.get(
                ods_code=organisation_mapping["ods_code"]
            )
            if LowerLayerSuperOutputArea.objects.filter(
                lsoa11cd=organisation_mapping["lsoa_code"]
            ).exists():
                lsoa = LowerLayerSuperOutputArea.objects.get(
                    lsoa11cd=organisation_mapping["lsoa_code"]
                )
                organisation.lower_layer_super_output_area = lsoa
                logger.info(f"Updated {organisation.name} with LSOA {lsoa}")
            else:
                logger.warning(
                    f"LSOA with code {organisation_mapping['lsoa_code']} not found for {organisation.name}"
                )
            if LocalAuthorityDistrict.objects.filter(
                lad24cd=organisation_mapping["lad_code"]
            ).exists():
                lad = LocalAuthorityDistrict.objects.get(
                    lad24cd=organisation_mapping["lad_code"]
                )
                organisation.local_authority_district = lad
                logger.info(f"Updated {organisation.name} with Local Authority {lad}")
            else:
                logger.warning(
                    f"Local authority with code {organisation_mapping['lad_code']} not found for {organisation.name}"
                )
            organisation.save()
        else:
            print(
                f"Organisation with ODS code {organisation_mapping['ods_code']} not found"
            )
    logger.info(
        f"{Organisation.objects.filter(local_authority_district__isnull=False).count()} Local authorities and {Organisation.objects.filter(lower_layer_super_output_area__isnull=False).count()} LSOAs seeded of total {Organisation.objects.count()} organisations."
    )
