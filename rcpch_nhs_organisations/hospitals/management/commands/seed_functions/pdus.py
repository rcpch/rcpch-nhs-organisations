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
    Seed function which populates the Organisation table from JSON.
    This instead uses a list provided by RCPCH E12 team of all organisations in England
    and Wales that care for children with Epilepsy - community paediatrics and hospital paediatrics
    in the same trust are counted as one organisation.
    """

    # Get models
    Organisation = apps.get_model("hospitals", "Organisation")
    Trust = apps.get_model("hospitals", "Trust")
    LocalHealthBoard = apps.get_model("hospitals", "LocalHealthBoard")
    PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")

    logger.info("Paediatric Diabetes Units being seeded...")
    for pdu in PZ_CODES:
        if Organisation.objects.filter(ods_code=pdu["ods_code"]).exists():
            # the ods_code provided is for an existing organisation, update to include PDU
            paediatric_diabetes_unit = PaediatricDiabetesUnit.objects.create(
                pz_code=pdu["npda_code"]
            )
            Organisation.objects.filter(ods_code=pdu["ods_code"]).update(
                paediatric_diabetes_unit=paediatric_diabetes_unit
            )
        else:
            if Trust.objects.filter(ods_code=pdu["ods_code"]).exists():
                # the ods_code provided is for a Trust, update all the related organisations

                # create the PDU
                paediatric_diabetes_unit = PaediatricDiabetesUnit.objects.create(
                    pz_code=pdu["npda_code"]
                )
                # get the trust
                trust = Trust.objects.filter(ods_code=pdu["ods_code"]).get()
                # Update trust's child organisations and update their affiliation with the new PDU
                Organisation.objects.filter(trust=trust).update(
                    paediatric_diabetes_unit=paediatric_diabetes_unit
                )
            elif LocalHealthBoard.objects.filter(ods_code=pdu["ods_code"]).exists():
                # the ods_code provided is for a Local Health Board, update all the related organisations
                # create the PDU
                paediatric_diabetes_unit = PaediatricDiabetesUnit.objects.create(
                    pz_code=pdu["npda_code"]
                )
                lhb = LocalHealthBoard.objects.get(
                    ods_code=ORD_organisation["Rels"]["Rel"][0]["Target"]["OrgId"][
                        "extension"
                    ]
                )
                Organisation.objects.filter(local_health_board=lhb).update(
                    paediatric_diabetes_unit=paediatric_diabetes_unit
                )
            else:
                # this organisation is associated with a pz code but does not exist in the organisation list we have
                # Fetch therefore from the Spine
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
                    else:
                        print(
                            "There is no parent trust for this new organisation matching our database"
                        )
                        parent_trust = None

                    if parent_trust is not None:
                        paediatric_diabetes_unit = (
                            PaediatricDiabetesUnit.objects.create(
                                pz_code=pdu["npda_code"]
                            )
                        )

                        organisations = parent_trust.trust_organisations.all()
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
                            Organisation.objects.create(
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
                                trust=parent_trust,
                                local_health_board=None,
                                integrated_care_board=organisations[
                                    0
                                ].integrated_care_board,
                                nhs_england_region=organisations[0].nhs_england_region,
                                openuk_network=organisations[0].openuk_network,
                                paediatric_diabetes_unit=paediatric_diabetes_unit,
                                london_borough=organisations[0].london_borough,
                                country=organisations[0].country,
                            )
                        except Exception as error:
                            logger.exception(
                                f"{ORD_organisation['Name']} {pdu['ods_code']} not saved due to {error} {parent_trust.name} has count: {organisations.count()} organisations"
                            )
                    else:
                        logger.exception(
                            "It was not possible to add this PDU as there was no parent organisation in the database"
                        )
