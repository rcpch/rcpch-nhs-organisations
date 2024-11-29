# python libraries

# django
from django.core.management.base import BaseCommand

# RCPCH
from .seed_functions import (
    seed_organisations,
    seed_trusts,
    seed_paediatric_diabetes_networks,
    update_pdu_networks,
    seed_pdus,
    ods_codes_to_abstraction_levels,
    load_jersey_boundaries,
    create_jersey_country,
)

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
    help = "seed database with census and IMD data for England, Wales, Scotland and Northern Ireland."

    def add_arguments(self, parser):
        parser.add_argument(
            "--level",
            type=str,
            help="Level. e.g. Trust, Network, PDU. Enter 'all' to seed all. Enter --help for more information.",
        )

    def handle(self, *args, **options):
        if options["level"] == "abstraction_levels":
            self.stdout.write(B + "Adding abstraction levels..." + W)
            ods_codes_to_abstraction_levels()
            rcpch_ascii_art()
        elif options["level"] == "trusts":
            self.stdout.write(B + "Adding trusts..." + W)
            seed_trusts()
            rcpch_ascii_art()
        elif options["level"] == "organisations":
            self.stdout.write(B + "Adding organisations..." + W)
            seed_organisations()
            rcpch_ascii_art()
        elif options["level"] == "paediatric_diabetes_networks":
            self.stdout.write(B + "Adding paediatric diabetes networks..." + W)
            seed_paediatric_diabetes_networks()
            rcpch_ascii_art()
        elif options["level"] == "pdus":
            self.stdout.write(
                B + "Adding paediatric diabetes units and networks..." + W
            )
            seed_paediatric_diabetes_networks()
            seed_pdus()
            rcpch_ascii_art()
        elif options["level"] == "update_pdus_with_networks":
            self.stdout.write(
                B + "Adding paediatric diabetes units and networks..." + W
            )
            update_pdu_networks()
            rcpch_ascii_art()
        elif options["level"] == "jersey":
            self.stdout.write(B + "Adding Jersey boundaries..." + W)
            load_jersey_boundaries()
            rcpch_ascii_art()
        elif options["level"] == "all":
            self.stdout.write(
                B + "Adding all organisations and levels of abstraction..." + W
            )
            create_jersey_country()
            ods_codes_to_abstraction_levels()
            seed_trusts()
            seed_organisations()

            seed_pdus()
            load_jersey_boundaries()
            rcpch_ascii_art()

        else:
            self.stdout.write("No options supplied...")
        self.stdout.write(rcpch_ascii_art())
        self.stdout.write("done.")
