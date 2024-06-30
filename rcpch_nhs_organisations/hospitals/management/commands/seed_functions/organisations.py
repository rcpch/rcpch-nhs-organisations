# standard library imports
import logging

# Django imports
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models import Q
from django.apps import apps

# Logging setup
logger = logging.getLogger("hospitals")

from rcpch_nhs_organisations.hospitals.constants import (
    RCPCH_ORGANISATIONS,
    INTEGRATED_CARE_BOARDS_LOCAL_AUTHORITIES,
    OPEN_UK_NETWORKS_TRUSTS,
)


def seed_organisations():
    """
    Seed function which populates the Organisation table from JSON.
    This instead uses a list provided by RCPCH team of all organisations in England
    and Wales that care for children with Epilepsy - community paediatrics and hospital paediatrics
    in the same trust are counted as one organisation.
    """

    # Get models
    Organisation = apps.get_model("hospitals", "Organisation")
    Trust = apps.get_model("hospitals", "Trust")
    LocalHealthBoard = apps.get_model("hospitals", "LocalHealthBoard")
    IntegratedCareBoard = apps.get_model("hospitals", "IntegratedCareBoard")
    NHSEnglandRegion = apps.get_model("hospitals", "NHSEnglandRegion")
    LondonBorough = apps.get_model("hospitals", "LondonBorough")
    OPENUKNetwork = apps.get_model("hospitals", "OPENUKNetwork")
    Country = apps.get_model("hospitals", "Country")
    england = Country.objects.get(boundary_identifier="E92000001")
    wales = Country.objects.get(boundary_identifier="W92000004")

    if Organisation.objects.all().count() >= 330:
        logger.info(
            "329 RCPCH organisations already seeded. Skipping...",
        )
    else:
        logger.info("Adding new RCPCH organisations...")

        for added, rcpch_organisation in enumerate(RCPCH_ORGANISATIONS):
            # Apply longitude and latitude data, if exists
            new_point = None
            try:
                latitude = float(rcpch_organisation["Latitude"])
            except:
                latitude = None
            try:
                longitude = float(rcpch_organisation["Longitude"])
            except:
                latitude = None

            if longitude and latitude:
                new_point = Point(x=longitude, y=latitude)

            # Date-stamps the Organisation information (this data was supplied on 19.04.2023)
            # update_date = datetime(year=2023, month=4, day=19)
            # timezone_aware_update_date = timezone.make_aware(update_date, timezone.utc)

            # Create Organisation instances
            try:
                organisation = Organisation.objects.create(
                    ods_code=rcpch_organisation["OrganisationCode"],
                    name=rcpch_organisation["OrganisationName"],
                    website=rcpch_organisation["Website"],
                    address1=rcpch_organisation["Address1"],
                    address2=rcpch_organisation["Address2"],
                    address3=rcpch_organisation["Address3"],
                    city=rcpch_organisation["City"],
                    county=rcpch_organisation["County"],
                    latitude=latitude,
                    longitude=longitude,
                    postcode=rcpch_organisation["Postcode"],
                    geocode_coordinates=new_point,
                    telephone=rcpch_organisation["Phone"],
                )
                # add trust or local health board
                if (
                    LocalHealthBoard.objects.filter(
                        ods_code=rcpch_organisation["ParentODSCode"]
                    ).count()
                    > 0
                ):
                    local_health_board = LocalHealthBoard.objects.get(
                        ods_code=rcpch_organisation["ParentODSCode"]
                    )
                    organisation.local_health_board = local_health_board
                    organisation.country = wales
                elif (
                    Trust.objects.filter(
                        ods_code=rcpch_organisation["ParentODSCode"]
                    ).count()
                    > 0
                ):
                    trust = Trust.objects.get(
                        ods_code=rcpch_organisation["ParentODSCode"]
                    )
                    organisation.trust = trust
                    organisation.country = england

                else:
                    raise Exception(
                        f"No Match! {rcpch_organisation['OrganisationName']} has no parent organisation."
                    )

                # add london boroughs
                if rcpch_organisation["City"] == "LONDON":
                    try:
                        london_borough = LondonBorough.objects.get(
                            gss_code=rcpch_organisation["LocalAuthority"]
                        )
                        organisation.london_borough = london_borough
                    except Exception as e:
                        logger.info(
                            f"Unable to save London Borough {rcpch_organisation['LocalAuthority']}"
                        )
                        pass

                organisation.save()
                logger.info(f"{added+1}: {rcpch_organisation['OrganisationName']}")
            except Exception as error:
                logger.info(
                    f"Unable to save {rcpch_organisation['OrganisationName']}: {error}"
                )

        logger.info(f"{added+1} organisations added.")

    logger.info(
        "Updating RCPCH organisations with ICB, NHS England relationships...",
    )
    # add integrated care boards and NHS regions to organisations
    for added, icb_trust in enumerate(INTEGRATED_CARE_BOARDS_LOCAL_AUTHORITIES):
        try:
            icb = IntegratedCareBoard.objects.get(ods_code=icb_trust["ODS ICB Code"])
        except Exception as error:
            error_message = f"Could not match ICB ODS Code {icb_trust['ODS ICB Code']} with that in Trust table."
            logger.error(error_message)

        try:
            trust = Trust.objects.get(ods_code=icb_trust["ODS Trust Code"])
        except Exception as error:
            error_message = f"Could not match Trust ODS Code {icb_trust['ODS Trust Code']} with that in Trust table."
            logger.error(error_message)

        try:
            nhs_england_region = NHSEnglandRegion.objects.get(
                region_code=icb_trust["NHS England Region Code"]
            )
        except Exception as error:
            error_message = f"Could not match NHS Region GSS Code {icb_trust['NHS England Region Code']} with that in the NHS England Region table."
            logger.error(error_message)

        update_fields = {
            "integrated_care_board": icb,
            "nhs_england_region": nhs_england_region,
        }
        # if icb_trust[]
        # update all organisations associated with this trust with this ICB
        try:
            Organisation.objects.filter(trust=trust).update(**update_fields)
        except Exception as error:
            error_message = f"Unable to find {icb_trust['ODS Trust Code']} when updating {icb_trust['ODS ICB Code']} ICB and {icb_trust['NHS England Region Code']} NHS England Region!"
            logger.error(error_message)
    logger_info = (
        f"Updated {added+1} RCPCH organisations with ICB, NHS England relationships..."
    )
    logger.info(logger_info)

    logger.info(
        "Updating all RCPCH organisations with OPEN UK network relationships..."
    )

    # openuk_network
    for added, trust_openuk_network in enumerate(OPEN_UK_NETWORKS_TRUSTS):
        query_term = Q()
        if Trust.objects.filter(
            ods_code=trust_openuk_network["ods trust code"]
        ).exists():
            query_term = Q(
                trust=Trust.objects.get(ods_code=trust_openuk_network["ods trust code"])
            )
        elif LocalHealthBoard.objects.filter(
            ods_code=trust_openuk_network["ods trust code"]
        ).exists():
            query_term = Q(
                local_health_board=LocalHealthBoard.objects.get(
                    ods_code=trust_openuk_network["ods trust code"]
                )
            )
        else:
            raise Exception(f"{trust_openuk_network['ods trust code']} error")

        openuk_network = OPENUKNetwork.objects.get(
            boundary_identifier=trust_openuk_network["OPEN UK Network Code"]
        )
        # upoate the OPENUK netowork for all the Organisations in this trust
        Organisation.objects.filter(query_term).update(openuk_network=openuk_network)
        info_text = (
            f"Updated {added+1} RCPCH organisations with OPENUK relationships..."
        )
    logger_info = info_text
    logger.info(logger_info)
