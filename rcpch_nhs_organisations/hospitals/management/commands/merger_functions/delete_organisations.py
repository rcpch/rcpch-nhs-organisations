# python imports
import logging

# django imports
from django.apps import apps

# third party imports

# rcpch imports

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
P = "\033[35m"  # purple
BOLD = "\033[1m"
END = "\033[0m"


logger = logging.getLogger("hospitals")


def delete_organisations(self, organisations):
    """
    Delete organisations from the database.
    """
    Organisation = apps.get_model("hospitals", "Organisation")
    PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")

    for organisation in organisations:
        try:
            organisation = Organisation.objects.get(ods_code=organisation)
            self.stdout.write(
                R
                + f"You are about to delete {organisation}! It has the following relationships."
                + W,
            )
            self.stdout.write(
                f"{BOLD}Paediatric Diabetes Unit: {organisation.paediatric_diabetes_unit}.{END} This code is associated with {PaediatricDiabetesUnit.objects.filter(pk=organisation.paediatric_diabetes_unit.pk).count()} Paediatric Diabetes Unit(s)."
            )
            self.stdout.write(
                f"{BOLD}OPENUK Network: {organisation.openuk_network}{END}. There are {Organisation.objects.filter(openuk_network=organisation.openuk_network).count()} other organisations in this OPENUK Network."
            )
            self.stdout.write(f"{BOLD}Trust: {organisation.trust}{END}")
            self.stdout.write(
                f"{BOLD}Local Health Board: {organisation.local_health_board}{END}"
            )
            self.stdout.write(
                f"{BOLD}Integrated Care Board: {organisation.integrated_care_board}.{END} There are {Organisation.objects.filter(integrated_care_board=organisation.integrated_care_board).count()} other organisations in this Integrated Care Board."
            )
            self.stdout.write(
                f"{BOLD}NHS England Region: {organisation.nhs_england_region}.{END} There are {Organisation.objects.filter(nhs_england_region=organisation.nhs_england_region).count()} other organisations in this NHS England Region."
            )
            self.stdout.write(
                f"{BOLD}Country: {organisation.country}.{END} There are {Organisation.objects.filter(country=organisation.country).count()} other organisations in this country."
            )

            confirm = input(f"Are you sure you want to delete {organisation}? (y/n): ")
            if confirm.lower() == "y":
                organisation.delete()
                self.stdout.write(f"Deleted {organisation}.")
            else:
                self.stdout.write(f"Skipped deleting {organisation}.")

        except Organisation.DoesNotExist:
            self.stderr.write(
                f"Organisation {organisation} does not exist in the database."
            )
            continue
