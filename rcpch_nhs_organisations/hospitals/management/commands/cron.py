# python libraries

# django
from django.core.management.base import BaseCommand


# RCPCH
from ...general_functions.ods_update import update_organisation_model_with_ORD_changes


from .image import rcpch_ascii_art

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
P = "\033[35m"  # purple
BOLD = "\033[1m"
END = "\033[0m"


class Command(BaseCommand):
    help = "Update the organisation list from the NHS ODS API."

    def add_arguments(self, parser):
        parser.add_argument("--service", type=str, help="Service")

    def handle(self, *args, **options):
        if options["service"] == "organisations":
            self.stdout.write(B + "Checking for organisation updates..." + W)
            update_organisation_model_with_ORD_changes()
            rcpch_ascii_art()

        else:
            self.stdout.write("No options supplied...")
        self.stdout.write(rcpch_ascii_art())
        self.stdout.write("done.")
