# python imports

# django
from django.core.management.base import BaseCommand
from django.db import transaction

# RCPCH
from rcpch_nhs_organisations.hospitals.models import (
    Organisation,
    PaediatricDiabetesUnit,
    PaediatricDiabetesUnitVersion,
)

from .image import rcpch_ascii_art

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
BOLD = "\033[1m"


# The hardcoded lead-organisation mappings that were in
# PaediatricDiabetesUnit.primary_organisation before the lead_organisation FK
# was introduced. This command transfers these into the FK on the PDU row (and
# snapshots them on the current PaediatricDiabetesUnitVersion row). Once this
# command has run, the hardcoded block can be (and has been) removed.
#
# PZ code -> lead organisation ODS code.
# For single-org PDUs not listed here, the lead is unambiguous (the one
# child) and is handled by the general case below.
HARDCODED_LEAD_ORGANISATIONS = {
    "PZ024": "RVV01",  # William Harvey Hospital, Ashford
    "PZ050": "RVR07",  # Queen Mary's Hospital for Children, Carshalton
    "PZ136": "R0A03",  # Manchester Children's Hospital
    "PZ206": "RM321",  # Trafford General Hospital
    "PZ230": "RXC01",  # Conquest Hospital, Hastings
    "PZ249": "RTRAT",  # South Tees Hospital NHS Foundation Trust
    "PZ250": "R0B01",  # Sunderland Royal Hospital
    "PZ242": "RTE03",  # Gloucestershire Royal Hospital (lead)
    # The following were previously handled by the old
    # primary_organisation property's `else: return organisations.first()`
    # fallback. They are multi-site PDUs where the lead site is not the
    # first child in database ordering. Added here so the lead_organisation
    # FK is set correctly by the backfill command.
    "PZ167": "RTX02",  # Royal Lancaster Infirmary (Morecambe Bay)
    "PZ244": "7A2AA",  # Glangwili Hospital (Hywel Dda, Welsh)
    "PZ246": "RM315",  # Fairfield General Hospital (Northern Care Alliance)
    "PZ253": "RWFTW",  # Tunbridge Wells Hospital (Maidstone and Tunbridge Wells)
}

# The hardcoded name-source mappings that were in PaediatricDiabetesUnit.name
# before the name_source field was introduced. This command transfers these
# into name_source values on the PDU rows (and snapshots them on the current
# PaediatricDiabetesUnitVersion rows).
NAME_SOURCE_TRUST = "trust"
NAME_SOURCE_LOCAL_HEALTH_BOARD = "local_health_board"
HARDCODED_NAME_SOURCE_TRUST = {
    "PZ024",  # East Kent Hospitals University NHS Foundation Trust
    "PZ120",  # Northumbria Healthcare NHS Foundation Trust
    "PZ167",  # UNIVERSITY HOSPITALS OF MORECAMBE BAY NHS FOUNDATION TRUST
    "PZ172",  # WEST HERTFORDSHIRE TEACHING HOSPITALS NHS TRUST
    "PZ186",  # CALDERDALE AND HUDDERSFIELD NHS FOUNDATION TRUST
    "PZ232",  # BARKING, HAVERING AND REDBRIDGE UNIVERSITY HOSPITALS NHS TRUST
    "PZ246",  # NORTHERN CARE ALLIANCE NHS FOUNDATION TRUST
    "PZ249",  # SOUTH TEES HOSPITALS NHS FOUNDATION TRUST
    "PZ250",  # SOUTH TYNESIDE AND SUNDERLAND NHS FOUNDATION TRUST
    "PZ253",  # MAIDSTONE AND TUNBRIDGE WELLS NHS TRUST
    "PZ254",  # NORTH WEST ANGLIA NHS FOUNDATION TRUST
}
HARDCODED_NAME_SOURCE_LOCAL_HEALTH_BOARD = {
    "PZ244",  # Welsh PDU — names itself by its local health board
}


class Command(BaseCommand):
    help = (
        "One-off backfill of lead_organisation FKs on PaediatricDiabetesUnit "
        "and name_source values on PaediatricDiabetesUnit and "
        "PaediatricDiabetesUnitVersion, replacing the hardcoded PZ-code lists "
        "that were in PaediatricDiabetesUnit.primary_organisation and .name "
        "before the temporal layer modelled these attributes. See "
        "documentation/docs/developer/merger-handling.md."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report what would change without writing to the database.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            default=False,
            help=(
                "Auto-answer 'y' to every [y/n] prompt, applying all changes "
                "without interactive review. Has no effect with --dry-run."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        auto_yes = options["yes"]

        pdus = PaediatricDiabetesUnit.objects.all().order_by("pz_code")
        total = pdus.count()
        self.stdout.write(
            B
            + f"Backfilling lead_organisation and name_source for {total} PDU(s)..."
            + W
        )
        if auto_yes and not dry_run:
            self.stdout.write(
                R + "  --yes: auto-answering 'y' to every prompt without review."
                + W
            )

        lead_set = 0
        lead_skipped = 0
        name_source_set = 0
        name_source_skipped = 0
        ambiguous = 0

        for pdu in pdus:
            pz = pdu.pz_code
            # --- lead_organisation ---
            # Determine the lead organisation ODS code for this PDU.
            lead_ods_code = HARDCODED_LEAD_ORGANISATIONS.get(pz)
            if lead_ods_code is None:
                # Not in the hardcoded map. If the PDU has exactly one child
                # org, that org is the unambiguous lead.
                child_count = pdu.organisations.count()
                if child_count == 1:
                    lead_ods_code = pdu.organisations.first().ods_code
                elif child_count == 0:
                    if pdu.active:
                        # Active PDU with no child organisations — the
                        # organisations may not be seeded yet, or the PDU
                        # is new and has no children assigned.
                        network = pdu.paediatric_diabetes_network
                        net_name = network.name if network else "no network"
                        self.stdout.write(
                            R
                            + f"  {pz}: active PDU with no child "
                            f"organisations (network: {net_name}, name: "
                            f"{pdu.name or '(none)'}). No lead "
                            "organisation was ever set. Create the child "
                            "organisations via `mergers --create` or add "
                            "them to PZ_CODES, then re-run this command."
                            + W
                        )
                    else:
                        # Inactive predecessor or never-participated code —
                        # no lead is expected. Its lead organisation was
                        # reassigned to the successor PDU (if it had one).
                        self.stdout.write(
                            O
                            + f"  {pz}: inactive PDU, no child "
                            "organisations — no lead organisation set "
                            "(expected for inactive predecessors)."
                            + W
                        )
                    lead_skipped += 1
                else:
                    # Multiple children and no hardcoded lead — ambiguous.
                    # The operator must set lead_organisation manually via the
                    # admin.
                    network = pdu.paediatric_diabetes_network
                    net_name = network.name if network else "no network"
                    self.stdout.write(
                        R
                        + f"  {pz}: {child_count} child organisations and "
                        "no hardcoded lead (network: "
                        f"{net_name}, name: {pdu.name or '(none)'}). "
                        "No lead organisation was ever set. Set "
                        "lead_organisation manually via the admin "
                        "(Acquire another… or Merge into a new… wizard, "
                        "or edit the PDU row directly)."
                        + W
                    )
                    ambiguous += 1
                    lead_skipped += 1

            if lead_ods_code is not None:
                # Find the Organisation row.
                try:
                    lead_org = Organisation.objects.get(ods_code=lead_ods_code)
                except Organisation.DoesNotExist:
                    self.stdout.write(
                        R
                        + f"  {pz}: lead organisation {lead_ods_code} not in "
                        "database, skipping lead."
                        + W
                    )
                    lead_skipped += 1
                else:
                    if pdu.lead_organisation_id == lead_org.pk:
                        # Already set — idempotent.
                        pass
                    else:
                        self.stdout.write(
                            B
                            + f"  {pz}: set lead_organisation={lead_ods_code} "
                            f"({lead_org.name})"
                            + W
                        )
                        if dry_run:
                            self.stdout.write(
                                O + "  [dry-run] would set lead_organisation" + W
                            )
                        elif auto_yes or self._confirm("  Set lead_organisation? [y/n] "):
                            with transaction.atomic():
                                pdu.lead_organisation = lead_org
                                pdu.save(update_fields=["lead_organisation"])
                                # Snapshot onto the current version row too.
                                current_version = (
                                    PaediatricDiabetesUnitVersion.objects.filter(
                                        paediatric_diabetes_unit=pdu,
                                        valid_to__isnull=True,
                                    ).first()
                                )
                                if current_version is not None:
                                    current_version.lead_organisation = lead_org
                                    current_version.save(
                                        update_fields=["lead_organisation"]
                                    )
                            lead_set += 1
                            self.stdout.write(G + "  Set." + W)
                        else:
                            self.stdout.write(O + "  Not set." + W)
                            lead_skipped += 1

            # --- name_source ---
            if pz in HARDCODED_NAME_SOURCE_TRUST:
                new_source = NAME_SOURCE_TRUST
            elif pz in HARDCODED_NAME_SOURCE_LOCAL_HEALTH_BOARD:
                new_source = NAME_SOURCE_LOCAL_HEALTH_BOARD
            else:
                new_source = PaediatricDiabetesUnit.NAME_SOURCE_LEAD_ORGANISATION

            if pdu.name_source == new_source:
                # Already correct — idempotent.
                pass
            else:
                self.stdout.write(
                    B
                    + f"  {pz}: set name_source={new_source} (was "
                    f"{pdu.name_source or '<default>'})"
                    + W
                )
                if dry_run:
                    self.stdout.write(
                        O + "  [dry-run] would set name_source" + W
                    )
                elif auto_yes or self._confirm("  Set name_source? [y/n] "):
                    with transaction.atomic():
                        pdu.name_source = new_source
                        pdu.save(update_fields=["name_source"])
                        # Snapshot onto the current version row too.
                        current_version = (
                            PaediatricDiabetesUnitVersion.objects.filter(
                                paediatric_diabetes_unit=pdu,
                                valid_to__isnull=True,
                            ).first()
                        )
                        if current_version is not None:
                            current_version.name_source = new_source
                            current_version.save(update_fields=["name_source"])
                    name_source_set += 1
                    self.stdout.write(G + "  Set." + W)
                else:
                    self.stdout.write(O + "  Not set." + W)
                    name_source_skipped += 1

        self.stdout.write("")
        self.stdout.write(B + "Summary:" + W)
        self.stdout.write(f"  PDUs processed: {total}")
        self.stdout.write(G + f"  lead_organisation set: {lead_set}" + W)
        self.stdout.write(O + f"  lead_organisation skipped: {lead_skipped}" + W)
        if ambiguous:
            self.stdout.write(
                R
                + f"  Ambiguous (multiple children, no hardcoded lead): "
                f"{ambiguous} — set lead_organisation manually via the admin."
                + W
            )
        self.stdout.write(G + f"  name_source set: {name_source_set}" + W)
        self.stdout.write(O + f"  name_source skipped: {name_source_skipped}" + W)
        self.stdout.write("done.")
        rcpch_ascii_art()

    def _confirm(self, prompt):
        try:
            answer = input(prompt)
        except EOFError:
            self.stdout.write(O + "  No input — skipping." + W)
            return False
        return answer.strip().lower() == "y"
