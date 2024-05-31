# python libraries

# django
from django.core.management.base import BaseCommand

# RCPCH
from rcpch_nhs_organisations.hospitals.management.commands.merger_functions import (
    create_organisations,
    delete_organisations,
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
    help = "Manually handle mergers, acquisitions, name changes and closing of hospitals and other NHS organisationational structures."

    def add_arguments(self, parser):
        parser.add_argument(
            "--organisations",
            "-o",
            nargs="+",
            help="List of organisation ODS codes to manipulate.",
            type=str,
        )

        parser.add_argument(
            "-c",
            "--create",
            action="store_const",
            const=True,
            help="Optional parameter. Set True if Organisations are to be created. This is the default option.",
            default=False,
        )
        parser.add_argument(
            "-d",
            "--delete",
            action="store_const",
            const=True,
            help="Optional parameter. Set True if Organisations are to be deleted. The default option is set to False.",
            default=False,
        )

    def handle(self, *args, **options):
        create = options["create"]
        delete = options["delete"]
        organisations = options["organisations"]

        if create and delete:
            self.stdout.write(
                "Error: Cannot use both --create and --delete at the same time."
            )
            return
        elif not create and not delete:
            self.stdout.write("Error: Must provide either --create or --delete.")
            return

        if len(organisations) < 1:
            self.stdout.write("Error: Argument requires one or more organisations.")
            return

        if create:
            self.stdout.write(
                B + "Finding organisation(s) on the Spine and creating..." + W
            )
            create_organisations(self, organisations)
        elif delete:
            self.stdout.write(B + "Deleting organisation(s)..." + W)
            delete_organisations(self, organisations)

        self.stdout.write(rcpch_ascii_art())
