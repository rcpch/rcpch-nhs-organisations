# python imports
import datetime

# django
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.db import transaction

# RCPCH
from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    get_organisation,
    _extract_succession_info,
)
from rcpch_nhs_organisations.hospitals.models import (
    Trust,
    TrustSuccession,
    Organisation,
    OrganisationSuccession,
    PaediatricDiabetesUnit,
    PaediatricDiabetesUnitSuccession,
)

from .image import rcpch_ascii_art

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
BOLD = "\033[1m"


# Maps entity type -> (model, succession_model, ods_code_field, parent_fk_field)
ENTITY_CONFIG = {
    "trust": {
        "model": Trust,
        "succession_model": TrustSuccession,
        "ods_code_field": "ods_code",
        "parent_fk_field": "predecessor",
    },
    "organisation": {
        "model": Organisation,
        "succession_model": OrganisationSuccession,
        "ods_code_field": "ods_code",
        "parent_fk_field": "predecessor",
    },
    "pdu": {
        "model": PaediatricDiabetesUnit,
        "succession_model": PaediatricDiabetesUnitSuccession,
        "ods_code_field": "pz_code",
        "parent_fk_field": "predecessor",
    },
}


class Command(BaseCommand):
    help = (
        "Backfill succession rows (mergers, acquisitions, splits, closures) "
        "from the ODS Succs block for every entity in the database. The ODS "
        "/organisations/{ods_code} endpoint returns the complete Succs block "
        "regardless of when the succession happened, so this recovers the "
        "full historical merger chain — not just the last 185 days. "
        "See documentation/docs/developer/backfill-plan.md."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--entity",
            type=str,
            required=True,
            choices=list(ENTITY_CONFIG.keys()),
            help="Entity type to backfill: trust, organisation, or pdu.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report missing succession rows without creating them.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of entities to process (for testing).",
        )

    def handle(self, *args, **options):
        entity_type = options["entity"]
        dry_run = options["dry_run"]
        limit = options["limit"]

        config = ENTITY_CONFIG[entity_type]
        model = config["model"]
        succession_model = config["succession_model"]
        ods_code_field = config["ods_code_field"]

        qs = model.objects.all()
        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(
            B + f"Backfilling successions for {total} {entity_type}(s)..." + W
        )

        found_count = 0
        created_count = 0
        skipped_count = 0

        for entity in qs:
            ods_code = getattr(entity, ods_code_field)
            # Fetch the full ODS record. The /organisations/{ods_code} endpoint
            # returns the complete Succs block regardless of when the succession
            # happened — this is not subject to the 185-day /sync limit.
            try:
                ord_record = get_organisation(
                    f"https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations/{ods_code}"
                )
            except Exception as e:
                self.stdout.write(
                    O + f"  {ods_code}: could not fetch ODS record ({e})" + W
                )
                continue

            succession_events = _extract_succession_info(ord_record)
            if not succession_events:
                continue

            for ev in succession_events:
                target_ods_code = ev["target_ods_code"]
                ev_type = ev["type"]
                ev_date = ev["date"]

                # Look up the target entity in our database.
                target = model.objects.filter(
                    **{ods_code_field: target_ods_code}
                ).first()
                if target is None:
                    self.stdout.write(
                        O + f"  {ods_code}: {ev_type} → {target_ods_code} "
                        f"({ev_date}) — target not in database, skipping" + W
                    )
                    skipped_count += 1
                    continue

                # Check if a succession row already exists.
                # For "Successor" (this entity was absorbed into the target),
                # the row is predecessor=this entity, successor=target.
                # For "Predecessor" (this entity absorbed the target), the row
                # is predecessor=target, successor=this entity.
                if ev_type == "Successor":
                    predecessor, successor = entity, target
                else:  # Predecessor
                    predecessor, successor = target, entity

                existing = succession_model.objects.filter(
                    predecessor=predecessor,
                    successor=successor,
                    succession_date=ev_date,
                ).exists()

                if existing:
                    continue  # already recorded

                found_count += 1

                # ODS does not distinguish merger/acquisition/split/closure.
                # We can't infer the type from the Succs block alone, so we
                # leave it as 'merger' as a placeholder — the operator should
                # review and correct via the admin if needed.
                suggested_type = "merger"

                self.stdout.write("")
                self.stdout.write(
                    B + f"  {ods_code} ({entity})" + W
                )
                self.stdout.write(
                    f"  {ev_type} → {target_ods_code} ({target})"
                )
                self.stdout.write(f"  Legal date: {ev_date}")
                self.stdout.write(
                    f"  Suggested succession_type: {suggested_type} "
                    "(review and correct via the admin if needed)"
                )

                if dry_run:
                    self.stdout.write(
                        O + "  [dry-run] would create succession row" + W
                    )
                    continue

                # Interactive prompt: yes / no / skip
                try:
                    answer = input(
                        f"  Create succession row {predecessor} → {successor} "
                        f"on {ev_date}? [y/n/s=skip] "
                    )
                except EOFError:
                    self.stdout.write(O + "  No input — skipping." + W)
                    skipped_count += 1
                    continue

                answer = answer.strip().lower()
                if answer == "y":
                    with transaction.atomic():
                        succession_model.objects.create(
                            predecessor=predecessor,
                            successor=successor,
                            succession_date=ev_date,
                            succession_type=suggested_type,
                            notes=f"Backfilled from ODS Succs block ({ev_type}).",
                        )
                    created_count += 1
                    self.stdout.write(G + "  Created." + W)
                elif answer == "n":
                    self.stdout.write(O + "  Not created." + W)
                    skipped_count += 1
                else:  # 's' or anything else
                    self.stdout.write(O + "  Skipped." + W)
                    skipped_count += 1

        self.stdout.write("")
        self.stdout.write(B + "Summary:" + W)
        self.stdout.write(f"  Found (missing): {found_count}")
        if not dry_run:
            self.stdout.write(G + f"  Created: {created_count}" + W)
            self.stdout.write(O + f"  Skipped/refused: {skipped_count}" + W)
        self.stdout.write("done.")
        rcpch_ascii_art()
