# standard library imports
import logging

# Django imports
from django.apps import apps
from django.contrib.gis.db.models import Q

from rcpch_nhs_organisations.hospitals.constants import (
    PZ_CODES,
)

from rcpch_nhs_organisations.hospitals.general_functions import (
    fetch_organisation_by_ods_code,
)


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

    if Organisation.objects.filter(paediatric_diabetes_unit__isnull=True).count() > 0:
        logging.info(
            "\033[31m Paediatric Diabetes Units already seeded. Skipping... \033[31m"
        )

    for pdu in PZ_CODES:
        if Organisation.objects.filter(ods_code=pdu["ods_code"]).exists():
            organisation = Organisation.objects.get(ods_code=pdu["ods_code"])
            paediatric_diabetes_unit = PaediatricDiabetesUnit.objects.create(
                pz_code=pdu["npda_code"]
            )
            organisation.paediatric_diabetes_unit = paediatric_diabetes_unit
            organisation.save(update_fields=["paediatric_diabetes_unit"])
            logging_info = (
                f"\033[31m Adding {organisation} to {paediatric_diabetes_unit}... \033[31m",
            )
            logging.info(logging_info)
        else:
            if Trust.objects.filter(ods_code=pdu["ods_code"]).exists():
                # the ods_code provided is for a Trust, update all the related organisations
                trust = Trust.objects.filter(ods_code=pdu["ods_code"]).get()
                organisations = Organisation.objects.filter(trust=trust).all()
                for organisation in organisations:
                    organisation.paediatric_diabetes_unit == pdu["ods_code"]
                    organisation.save(update_fields=["paediatric_diabetes_unit"])
                logging_info = f"\033[31m Adding {organisation} in {trust} to {paediatric_diabetes_unit}... \033[31m"
                logging.info(logging_info)
            else:
                # this organisation is associate with a pz code but does not exist in the organisation list we have
                ORD_organisation = fetch_organisation_by_ods_code(pdu["ods_code"])
                if ORD_organisation is not None:
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
                        organisations = parent_trust.trust_organisations.all()
                        county = getattr(
                            ORD_organisation["GeoLoc"]["Location"], "county", None
                        )
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
                                active=ORD_organisation["Status"] == "Active",
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
                            print(
                                f"{ORD_organisation['Name']} {pdu['ods_code']} not saved due to {error} {parent_trust.name} has count: {organisations.count()} organisations"
                            )
                    elif LocalHealthBoard.objects.filter(
                        ods_code=ORD_organisation["Rels"]["Rel"][0]["Target"]["OrgId"][
                            "extension"
                        ]
                    ).exists():
                        parent_local_health_board = LocalHealthBoard.objects.get(
                            ods_code=ORD_organisation["Rels"]["Rel"][0]["Target"][
                                "OrgId"
                            ]["extension"]
                        )
                        organisations = (
                            parent_local_health_board.local_health_board_organisations.all()
                        )
                        county = getattr(
                            ORD_organisation["GeoLoc"]["Location"], "county", None
                        )
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
                                active=ORD_organisation["Status"] == "Active",
                                published_at=ORD_organisation["Date"][0]["Start"],
                                trust=None,
                                local_health_board=parent_local_health_board,
                                integrated_care_board=None,
                                nhs_england_region=None,
                                openuk_network=organisations[0].openuk_network,
                                paediatric_diabetes_unit=paediatric_diabetes_unit,
                                london_borough=organisations[0].london_borough,
                                country=organisations[0].country,
                            )
                        except Exception as error:
                            error_message = (
                                f"{ORD_organisation['Name']} not saved due to {error}"
                            )
                            logging.error(error_message)

                    paediatric_diabetes_unit = PaediatricDiabetesUnit.objects.create(
                        pz_code=pdu["npda_code"]
                    )

                else:
                    error = f"{pdu['ods_code']} not saved as it does not exist or the ORD server is down."
                    logging.error(error)
