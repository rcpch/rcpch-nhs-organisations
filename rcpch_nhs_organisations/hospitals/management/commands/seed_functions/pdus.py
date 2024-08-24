# standard library imports
import logging

# Django imports
from django.apps import apps
from django.contrib.gis.geos import Point

from rcpch_nhs_organisations.hospitals.constants import (
    PZ_CODES,
)

from rcpch_nhs_organisations.hospitals.general_functions import (
    fetch_organisation_by_ods_code,
    fetch_by_postcode,
)

# logger setup
logger = logging.getLogger("hospitals")


def seed_pdus():
    """
    Seed function which populates the PaediatricDiabetesUnit table from constants.py
    PDU codes are associated with ODS codes, which are used to identify the organisations or trusts or local health boards that have a PDU
    Some trusts or health boards have multiple PDUs
    This function will update the existing organisations with the PDU code, where the ODS code matches the Organisation ODS code
    If the ODS code is not found in the Organisation table, the function will search the Trust and Local Health Boards table for the ODS code. The assumption is made here
    that where a PZ code is associated with a Trust or Local Health Board, all the organisations under that Trust will be updated with the PDU code.

    """

    # Get models
    Organisation = apps.get_model("hospitals", "Organisation")
    Trust = apps.get_model("hospitals", "Trust")
    LocalHealthBoard = apps.get_model("hospitals", "LocalHealthBoard")
    PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")

    if PaediatricDiabetesUnit.objects.exists():
        logger.info(
            "Paediatric Diabetes Units already exist in the database. Updating..."
        )

    logger.info("Paediatric Diabetes Units being seeded...")
    for pdu in PZ_CODES:
        if Organisation.objects.filter(ods_code=pdu["ods_code"]).exists():
            # the ods_code provided is for an existing organisation, update to include PDU
            paediatric_diabetes_unit, created = (
                PaediatricDiabetesUnit.objects.update_or_create(
                    pz_code=pdu["npda_code"]
                )
            )
            Organisation.objects.filter(ods_code=pdu["ods_code"]).update(
                paediatric_diabetes_unit=paediatric_diabetes_unit
            )
            logger.info(
                f"Updated Organisation {Organisation.objects.get(ods_code=pdu['ods_code'])} with PDU {pdu['npda_code']}"
            )
        else:
            if Trust.objects.filter(ods_code=pdu["ods_code"]).exists():
                # the ods_code provided is for a Trust, update all the related organisations

                # create the PDU
                paediatric_diabetes_unit, created = (
                    PaediatricDiabetesUnit.objects.update_or_create(
                        pz_code=pdu["npda_code"]
                    )
                )
                # get the trust
                trust = Trust.objects.filter(ods_code=pdu["ods_code"]).get()
                # Update trust's child organisations and update their affiliation with the new PDU - exclude any organisations that already have a PDU
                Organisation.objects.filter(trust=trust).exclude(
                    paediatric_diabetes_unit__isnull=False
                ).update(paediatric_diabetes_unit=paediatric_diabetes_unit)
                logger.info(
                    f"Updated Trust {trust} and all child organisations({Organisation.objects.filter(trust=trust)}) with PDU {pdu['npda_code']}"
                )

            elif LocalHealthBoard.objects.filter(ods_code=pdu["ods_code"]).exists():
                # the ods_code provided is for a Local Health Board, update all the related organisations
                # create the PDU
                paediatric_diabetes_unit, created = (
                    PaediatricDiabetesUnit.objects.update_or_create(
                        pz_code=pdu["npda_code"]
                    )
                )
                # get the local health board
                lhb = LocalHealthBoard.objects.get(ods_code=pdu["ods_code"])
                # update all child organisations in Local Health Board - exclude any organisations that already have a PDU
                Organisation.objects.filter(local_health_board=lhb).exclude(
                    paediatric_diabetes_unit__isnull=False
                ).update(paediatric_diabetes_unit=paediatric_diabetes_unit)
            else:
                # this organisation is associated with a pz code but does not exist in the organisation list we have
                # Fetch therefore from the Spine
                logger.info(
                    f"Organisation with ODS code {pdu['ods_code']} not found in the database. Fetching from Spine..."
                )
                ORD_organisation = fetch_organisation_by_ods_code(pdu["ods_code"])
                if ORD_organisation is not None:
                    # use the retrieved postcode to get the longitude and latitude
                    postcode_object = fetch_by_postcode(
                        ORD_organisation["GeoLoc"]["Location"]["PostCode"]
                    )
                    # fetch the parent Trust or Local Health Board for this new organisation in order to get relationships from siblings
                    if Trust.objects.filter(
                        ods_code=ORD_organisation["Rels"]["Rel"][0]["Target"]["OrgId"][
                            "extension"
                        ]
                    ).exists():
                        parent_trust = Trust.objects.get(
                            ods_code=ORD_organisation["Rels"]["Rel"][0]["Target"][
                                "OrgId"
                            ]["extension"]
                        )
                        child_organisations = Organisation.objects.filter(
                            trust=parent_trust, active=True
                        )
                    elif LocalHealthBoard.objects.filter(
                        ods_code=ORD_organisation["Rels"]["Rel"][0]["Target"]["OrgId"][
                            "extension"
                        ]
                    ).exists():
                        parent_trust = LocalHealthBoard.objects.get(
                            ods_code=ORD_organisation["Rels"]["Rel"][0]["Target"][
                                "OrgId"
                            ]["extension"]
                        )
                        child_organisations = Organisation.objects.filter(
                            local_health_board=parent_trust, active=True
                        )
                    else:
                        logger.warning(
                            f'There is no parent trust/local health board for this new organisation {pdu["ods_code"]} in the Spine. Skipping...'
                        )
                        parent_trust = None

                    if parent_trust is not None:
                        paediatric_diabetes_unit, created = (
                            PaediatricDiabetesUnit.objects.update_or_create(
                                pz_code=pdu["npda_code"]
                            )
                        )

                        county = getattr(
                            ORD_organisation["GeoLoc"]["Location"], "county", None
                        )
                        try:
                            longitude = float(postcode_object["location"]["lon"])
                        except:
                            longitude = None

                        try:
                            latitude = float(postcode_object["location"]["lat"])
                        except:
                            latitude = None

                        if longitude and latitude:
                            new_point = Point(x=longitude, y=latitude)
                        else:
                            new_point = None
                        try:
                            logger.info(
                                f"Saving new organisation {ORD_organisation['Name']} from Spine with PDU {pdu['npda_code']}"
                            )
                            new_organisation = Organisation.objects.create(
                                ods_code=pdu["ods_code"],
                                name=ORD_organisation["Name"],
                                address1=ORD_organisation["GeoLoc"]["Location"][
                                    "AddrLn1"
                                ],
                                city=ORD_organisation["GeoLoc"]["Location"]["Town"],
                                county=county,
                                postcode=ORD_organisation["GeoLoc"]["Location"][
                                    "PostCode"
                                ],
                                longitude=longitude,
                                latitude=latitude,
                                geocode_coordinates=new_point,
                                published_at=ORD_organisation["Date"][0]["Start"],
                                openuk_network=child_organisations.first().openuk_network,
                                paediatric_diabetes_unit=paediatric_diabetes_unit,
                                london_borough=child_organisations.first().london_borough,
                                country=child_organisations.first().country,
                            )
                            if child_organisations.first().country.name == "England":
                                new_organisation.trust = parent_trust
                                new_organisation.integrated_care_board = (
                                    child_organisations.first().integrated_care_board
                                )
                                new_organisation.nhs_england_region = (
                                    child_organisations.first().nhs_england_region
                                )
                                new_organisation.save(
                                    update_fields=[
                                        "trust",
                                        "integrated_care_board",
                                        "nhs_england_region",
                                    ]
                                )
                            elif child_organisations.first().country.name == "Wales":
                                new_organisation.local_health_board = parent_trust
                                new_organisation.save(
                                    update_fields=["local_health_board"]
                                )
                            else:
                                logger.warning(
                                    f"Country {child_organisations.first().country.name} not recognised for organisation {new_organisation.name}. Created with no relationship to Trust or Local Health Board or Integrated Care Board or NHS England Region"
                                )
                        except Exception as error:
                            logger.exception(
                                f"{ORD_organisation['Name']} {pdu['ods_code']} not saved due to {error} {parent_trust.name} has count: {child_organisations.count()} organisations"
                            )
                    else:
                        logger.exception(
                            "It was not possible to add this PDU as there was no parent organisation in the database"
                        )
