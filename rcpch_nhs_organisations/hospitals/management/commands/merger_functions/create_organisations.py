# python imports
import logging

# django imports
from django.apps import apps
from django.contrib.gis.geos import Point

# third party imports

# rcpch imports
from rcpch_nhs_organisations.hospitals.general_functions import (
    fetch_organisation_by_ods_code,
    fetch_by_postcode,
)
from rcpch_nhs_organisations.hospitals.constants import (
    PZ_CODES,
    OPEN_UK_NETWORKS_TRUSTS,
)


logger = logging.getLogger("hospitals")


def create_organisations(self, organisations):
    """
    Create organisations from a list of ODS codes by looking them up on the Spine.
    Also fetches the longitude and latitude of the organisation's postcode.
    Then looks up the parent Trust or Local Health Board to get relationships for parents.
    Also looks up the country, london borough, NHS England region, ICB and OPENUK network.
    If no records of these affiliated organisations or regions are found, they are set to None.
    It is not possible to create an organisation without a parent Trust or Local Health Board.
    This function assumes that the ODS code provided is for an organisation and not a Trust or Local Health Board or Integrated Care Board.
    """
    Organisation = apps.get_model("hospitals", "Organisation")
    Trust = apps.get_model("hospitals", "Trust")
    LocalHealthBoard = apps.get_model("hospitals", "LocalHealthBoard")
    PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")
    OPENUKNetwork = apps.get_model("hospitals", "OPENUKNetwork")

    for organisation in organisations:
        try:
            spine_result = fetch_organisation_by_ods_code(organisation)
        except Exception as e:
            self.stderr.write(
                f"Organisation {organisation} does not exist in the Spine."
            )
            continue

        if Organisation.objects.filter(
            ods_code=spine_result["OrgId"]["extension"]
        ).exists():
            self.stdout.write(
                f"Organisation {spine_result['Name']} already exists in the database. Skipping..."
            )
            continue
        else:
            self.stdout.write(
                f"Organisation {organisation} not found in the database. Fetching from Spine..."
            )
            try:
                postcode_object = fetch_by_postcode(
                    spine_result["GeoLoc"]["Location"]["PostCode"]
                )
            except Exception as e:
                logger.error("Postcode not found. Organisation not saved.")
                return

            # fetch the parent Trust or Local Health Board for this new organisation in order to get relationships from siblings
            if Trust.objects.filter(
                ods_code=spine_result["Rels"]["Rel"][0]["Target"]["OrgId"]["extension"]
            ).exists():
                trust = Trust.objects.get(
                    ods_code=spine_result["Rels"]["Rel"][0]["Target"]["OrgId"][
                        "extension"
                    ]
                )
                icb = (
                    Organisation.objects.filter(trust=trust)
                    .first()
                    .integrated_care_board
                )
                nhs_england_region = (
                    Organisation.objects.filter(trust=trust).first().nhs_england_region
                )
                london_borough = (
                    Organisation.objects.filter(trust=trust).first().london_borough
                )
                country = Organisation.objects.filter(trust=trust).first().country
                local_health_board = None

                openuk_network = None
                for network in OPEN_UK_NETWORKS_TRUSTS:
                    if network["ods trust code"] == trust.ods_code:
                        openuk_network = OPENUKNetwork.objects.get(
                            boundary_identifier=network["OPEN UK Network Code"]
                        )
                        break

            elif LocalHealthBoard.objects.filter(
                ods_code=spine_result["Rels"]["Rel"][0]["Target"]["OrgId"]["extension"]
            ).exists():
                local_health_board = LocalHealthBoard.objects.get(
                    ods_code=spine_result["Rels"]["Rel"][0]["Target"]["OrgId"][
                        "extension"
                    ]
                )
                openuk_network = None
                for network in OPEN_UK_NETWORKS_TRUSTS:
                    if network["ods trust code"] == local_health_board.ods_code:
                        openuk_network = OPENUKNetwork.objects.get(
                            boundary_identifier=network["OPEN UK Network Code"]
                        )
                        break

                country = (
                    Organisation.objects.filter(local_health_board=local_health_board)
                    .first()
                    .country
                )
                icb = None
                nhs_england_region = None
                london_borough = None
                trust = None
            else:
                self.stdout.write(
                    f"There is no parent trust/local health board for this new organisation {organisation} in the Spine. Skipping..."
                )
                return

            # PDUs
            pdu = None
            for pdu_code in PZ_CODES:
                if pdu_code["ods_code"] == spine_result["OrgId"]["extension"]:
                    pdu = PaediatricDiabetesUnit.objects.get(
                        pz_code=pdu_code["npda_code"]
                    )
                    break

            # Inputs for the user to confirm
            if not openuk_network:
                confirm = input(
                    f"There is no OPENUK Network associated with this {organisation}? Do you want to continue to create the organisation? (y/n) [It is possible to add it later.]"
                )
                if confirm.lower() == "y":
                    pass
                else:
                    self.stdout.write(
                        f"Skipped deleting {organisation} as there is no associated OPENUK Network."
                    )
                    return

            if not pdu:
                confirm = input(
                    f"There is no Paediatric Diabetes Unit associated with this {organisation}? Do you want to continue to create it? (y/n) [It is possible to add it later.]"
                )
                if confirm.lower() == "y":
                    pass
                else:
                    self.stdout.write(
                        f"Skipped deleting {organisation} as there is no associated Paediatric Diabetes Unit."
                    )
                    return

            # fetch the county, postcode and retrieve the longitude and latitude
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

            # save the new organisation
            try:
                self.stdout.write(
                    f"Saving new organisation {spine_result['Name']} from Spine..."
                )

                new_organisation = Organisation.objects.create(
                    ods_code=spine_result["OrgId"]["extension"],
                    name=spine_result["Name"],
                    address1=spine_result["GeoLoc"]["Location"]["AddrLn1"],
                    address2=(
                        spine_result["GeoLoc"]["Location"]["AddrLn2"]
                        if "AddrLn2" in spine_result["GeoLoc"]["Location"]
                        else None
                    ),
                    address3=(
                        spine_result["GeoLoc"]["Location"]["AddrLn3"]
                        if "AddrLn3" in spine_result["GeoLoc"]["Location"]
                        else None
                    ),
                    telephone=None,  # no telephone number in Spine
                    city=spine_result["GeoLoc"]["Location"]["Town"],
                    county=spine_result["GeoLoc"]["Location"]["County"],
                    postcode=spine_result["GeoLoc"]["Location"]["PostCode"],
                    longitude=longitude,
                    latitude=latitude,
                    geocode_coordinates=new_point,
                    published_at=spine_result["Date"][0]["Start"],
                    integrated_care_board=icb,
                    nhs_england_region=nhs_england_region,
                    openuk_network=openuk_network,
                    paediatric_diabetes_unit=pdu,
                    london_borough=london_borough,
                    trust=trust,
                    local_health_board=local_health_board,
                    country=country,
                    active=(True if spine_result["Status"] == "Active" else False),
                )

                self.stdout.write(
                    f"New organisation {new_organisation} created from Spine."
                )
            except Exception as e:
                self.stderr.write(
                    f"Error saving organisation {spine_result['Name']} from Spine. Error: {e}"
                )
                continue
