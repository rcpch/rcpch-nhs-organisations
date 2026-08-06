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
from rcpch_nhs_organisations.hospitals.general_functions.membership import (
    backfill_trust_attributes,
    backfill_organisation_attributes,
)
from rcpch_nhs_organisations.hospitals.models import (
    Trust,
    TrustSuccession,
    Organisation,
    OrganisationSuccession
)

from .image import rcpch_ascii_art

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
BOLD = "\033[1m"


# Maps entity type -> config. `backfill_helper` is the
# backfill_<entity>_attributes callable used to write the closure version row
# for the predecessor (see `handle`). `name_field` is the attribute on the
# entity that holds its name (used for the successor-side name-change prompt
# on Predecessor events).
ENTITY_CONFIG = {
    "trust": {
        "model": Trust,
        "succession_model": TrustSuccession,
        "ods_code_field": "ods_code",
        "parent_fk_field": "predecessor",
        "backfill_helper": backfill_trust_attributes,
        "name_field": "name",
    },
    "organisation": {
        "model": Organisation,
        "succession_model": OrganisationSuccession,
        "ods_code_field": "ods_code",
        "parent_fk_field": "predecessor",
        "backfill_helper": backfill_organisation_attributes,
        "name_field": "name",
    }
}


class Command(BaseCommand):
    help = (
        "Backfill succession rows (mergers, acquisitions, splits, closures) "
        "from the ODS Succs block for every entity in the database. The ODS "
        "/organisations/{ods_code} endpoint returns the complete Succs block "
        "regardless of when the succession happened, so this recovers the "
        "full historical merger chain — not just the last 185 days. "
        "See documentation/docs/developer/backfill.md."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--entity",
            type=str,
            required=True,
            choices=list(ENTITY_CONFIG.keys()),
            help="Entity type to backfill: trust or organisation. (PDUs are "
            "not in ODS, so they are not supported by this command.)",
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
        backfill_helper = config["backfill_helper"]
        name_field = config["name_field"]

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
                # The predecessor ceased to exist on ev_date in every ODS
                # succession type (merger / acquisition / split / closure), so
                # confirming this row also closes the predecessor: a closure
                # version row is written (active=False from ev_date) and the
                # entity row's `active` flag is flipped. This is the same write
                # the backfill-merger admin wizard performs.
                predecessor_already_closed = not getattr(predecessor, "active", True)
                if predecessor_already_closed:
                    self.stdout.write(
                        f"  Predecessor {predecessor} is already inactive — "
                        "only the succession row will be created."
                    )
                else:
                    self.stdout.write(
                        O + f"  This will also close {predecessor} "
                        f"(set active=False from {ev_date})." + W
                    )

                # For a "Predecessor" event (this entity absorbed the target),
                # this entity is the continuing successor. If it was renamed as
                # part of the merger, ODS has overwritten its Name in place, so
                # the old name is gone from the API. The operator is the source
                # of truth for the pre-merger name: we prompt for it and, if
                # supplied, backfill a name-change version row for the successor
                # covering [establishment, merger_date). If the operator skips
                # (blank input), the successor's name history is left as-is.
                # This only applies to Predecessor events — for a Successor
                # event, this entity is the predecessor (being closed), not the
                # continuing entity.
                successor_name_change = (ev_type == "Predecessor")
                if successor_name_change:
                    self.stdout.write(
                        O + f"  {successor} may have had a different name "
                        f"before {ev_date}. You will be prompted for the "
                        "pre-merger name (look it up in ODS Trac or another "
                        "source); leave blank to skip the name backfill." + W
                    )

                if dry_run:
                    self.stdout.write(
                        O + "  [dry-run] would create succession row" + W
                    )
                    if not predecessor_already_closed:
                        self.stdout.write(
                            O + f"  [dry-run] would close {predecessor} "
                            f"(active=False from {ev_date})." + W
                        )
                    if successor_name_change:
                        self.stdout.write(
                            O + f"  [dry-run] would prompt for {successor}'s "
                            "pre-merger name and backfill a name-change "
                            "version row if supplied." + W
                        )
                    continue

                # Interactive prompt: yes / no / skip
                try:
                    answer = input(
                        f"  Create succession row {predecessor} → {successor} "
                        f"on {ev_date}"
                        + ("" if predecessor_already_closed else
                            f" and close {predecessor}")
                        + "? [y/n/s=skip] "
                    )
                except EOFError:
                    self.stdout.write(O + "  No input — skipping." + W)
                    skipped_count += 1
                    continue

                answer = answer.strip().lower()
                if answer == "y":
                    # For a Predecessor event, prompt for the successor's
                    # pre-merger name. The operator is the source of truth —
                    # ODS has overwritten the successor's Name in place, so
                    # the old name is not recoverable from the API. Blank input
                    # (or EOF) skips the name backfill; the succession row and
                    # predecessor closure still proceed.
                    old_name = None
                    if successor_name_change:
                        current_name = getattr(successor, name_field, "") or ""
                        try:
                            old_name = input(
                                f"  Pre-merger name for {successor} "
                                f"(current: {current_name!r}). "
                                "Leave blank to skip: "
                            )
                        except EOFError:
                            self.stdout.write(
                                O + "  No input — skipping name backfill." + W
                            )
                            old_name = ""
                        old_name = old_name.strip()
                        if not old_name or old_name == current_name:
                            old_name = None
                    with transaction.atomic():
                        succession_model.objects.create(
                            predecessor=predecessor,
                            successor=successor,
                            succession_date=ev_date,
                            succession_type=suggested_type,
                            notes=f"Backfilled from ODS Succs block ({ev_type}).",
                        )
                        if not predecessor_already_closed:
                            # Write the closure version row (active=False from
                            # ev_date forward) and flip the entity row. Uses
                            # the same backfill_<entity>_attributes helper as
                            # the admin wizard so the write path is identical.
                            backfill_helper(
                                predecessor,
                                valid_from=ev_date,
                                valid_to=None,
                                active=False,
                            )
                            predecessor.active = False
                            predecessor.save(update_fields=["active"])
                        if old_name:
                            # Backfill the successor's pre-merger name for
                            # [establishment, merger_date). We use the ODS
                            # Legal.Start as the establishment date if
                            # available; otherwise fall back to the merger date
                            # (which produces a zero-length interval that the
                            # helper will treat as a no-op, so the name
                            # backfill is effectively skipped if we can't date
                            # it).
                            legal_start = None
                            for d in ord_record.get("Date", []):
                                if d.get("Type") == "Legal":
                                    legal_start = d.get("Start")
                                    break
                            if legal_start:
                                backfill_helper(
                                    successor,
                                    valid_from=datetime.date.fromisoformat(
                                        legal_start
                                    ),
                                    valid_to=ev_date,
                                    **{name_field: old_name},
                                    active=True,
                                )
                    created_count += 1
                    self.stdout.write(G + "  Created." + W)
                    if not predecessor_already_closed:
                        self.stdout.write(
                            G + f"  Closed {predecessor} (active=False "
                            f"from {ev_date})." + W
                        )
                    if old_name:
                        self.stdout.write(
                            G + f"  Backfilled {successor} name "
                            f"'{old_name}' ({legal_start} → {ev_date})." + W
                        )
                    elif successor_name_change:
                        self.stdout.write(
                            O + f"  Skipped name backfill for {successor}." + W
                        )
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
