# python libraries

# django
from django.core.management.base import BaseCommand

# RCPCH
from .seed_functions import *

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
        parser.add_argument("--model", type=str, help="Mode")

    def handle(self, *args, **options):
        if options["model"] == "abstraction_levels":
            self.stdout.write(B + "Adding abstraction levels..." + W)
            ods_codes_to_abstraction_levels()
            image()
        elif options["model"] == "trusts":
            self.stdout.write(B + "Adding trusts..." + W)
            seed_trusts()
            image()
        elif options["model"] == "organisations":
            self.stdout.write(B + "Adding organisations..." + W)
            seed_organisations()
            image()
        elif options["model"] == "pdus":
            self.stdout.write(B + "Adding paediatric diabetes units..." + W)
            seed_pdus()
            image()
        elif options["model"] == "all":
            self.stdout.write(
                B + "Adding all organisations and levels of abstraction..." + W
            )
            ods_codes_to_abstraction_levels()
            seed_trusts()
            seed_organisations()
            seed_pdus()
            image()

        else:
            self.stdout.write("No options supplied...")
        self.stdout.write(image())
        self.stdout.write("done.")


def image():
    return """

                                .^~^      ^777777!~:       ^!???7~:
                                ^JJJ:.:!^ 7#BGPPPGBGY:   !5BBGPPGBBY.
                                 :~!!?J~. !BBJ    YBB?  ?BB5~.  .~J^
                              .:~7?JJ?:   !BBY^~~!PBB~ .GBG:
                              .~!?JJJJ^   !BBGGGBBBY^  .PBG^
                                 ?J~~7?:  !BBJ.:?BB5^   ~GBG?^:^~JP7
                                :?:   .   !BBJ   ~PBG?.  :?PBBBBBG5!
                                ..::...     .::. ...:^::. .. .:^~~^:.
                                !GPGGGGPY7.   :!?JJJJ?7~..PGP:    !GGJ
                                7BBY~~!YBBY  !JJ?!^^^!??::GBG:    7BBJ
                                7BB?   .GBG.^JJ7.     .. .GBG!^^^^JBBJ
                                7BB577?5BBJ ~JJ!         .GBBGGGGGGBBJ
                                7BBGPPP5J~  :JJJ^.   .^^ .GBG^.::.?BBJ
                                7#B?         :7JJ?77?JJ?^:GBB:    7##Y
                                ~YY!           :~!77!!^. .JYJ.    ~YY7


                                       RCPCH Census Platform 2022

                """
