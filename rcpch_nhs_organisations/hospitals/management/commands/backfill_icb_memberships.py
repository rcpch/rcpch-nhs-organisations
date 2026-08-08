# python imports
import datetime

# django
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# RCPCH
from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    get_organisation,
    _extract_icb_membership_info,
    _parse_ods_date,
)
from rcpch_nhs_organisations.hospitals.general_functions.membership import (
    backfill_trust_icb_membership,
)
from rcpch_nhs_organisations.hospitals.models import (
    IntegratedCareBoard,
    Trust,
    TrustIntegratedCareBoardMembership,
)

from .image import rcpch_ascii_art

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
BOLD = "\033[1m"

# Default lookback window. ICBs were established on 1 July 2022, so the
# default run recovers memberships from 2020-04-01 (when ODS started
# recording RO261 ICB rels) forward. Use --since for a different window,
# or --all for the full history.
DEFAULT_SINCE = datetime.date(2020, 4, 1)


class Command(BaseCommand):
    help = (
        "Backfill historical TrustIntegratedCareBoardMembership rows from "
        "the ODS Rels block for every trust in the database. The ODS "
        "/organisations/{ods_code} endpoint returns the complete Rels "
        "history regardless of when a relationship ended, so this recovers "
        "ICB memberships that were overwritten before the temporal layer "
        "was installed. Only RO261 (ICB) targets are recovered — CCG "
        "(RO210) and STP (RO132) targets are ignored. See "
        "documentation/docs/developer/icb-history.md."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report missing membership rows without creating them.",
        )
        parser.add_argument(
            "--since",
            type=str,
            default=None,
            help=(
                "Only recover memberships whose operational interval "
                "overlaps this date forward (YYYY-MM-DD). Defaults to "
                f"{DEFAULT_SINCE.isoformat()} (when ICB rels first appear "
                "in ODS). Use --all for the full history held by ODS."
            ),
        )
        parser.add_argument(
            "--all",
            action="store_true",
            default=False,
            help=(
                "Recover the full membership history held by ODS, ignoring "
                "the --since window."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of trusts to process (for testing).",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            default=False,
            help=(
                "Auto-answer 'y' to every [y/n/s=skip] prompt, creating all "
                "missing membership rows without interactive review. Has no "
                "effect with --dry-run."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        use_all = options["all"]
        since_str = options["since"]
        limit = options["limit"]
        auto_yes = options["yes"]

        if use_all and since_str:
            raise CommandError("--all and --since are mutually exclusive.")

        if since_str:
            try:
                since_date = datetime.date.fromisoformat(since_str)
            except ValueError:
                raise CommandError(
                    f"--since must be a valid YYYY-MM-DD date. Got '{since_str}'."
                )
        elif use_all:
            since_date = None
        else:
            since_date = DEFAULT_SINCE

        qs = Trust.objects.all()
        if limit:
            qs = qs[:limit]

        total = qs.count()
        window_desc = (
            "the full ODS history" if since_date is None else f"since {since_date}"
        )
        self.stdout.write(
            B
            + f"Backfilling ICB memberships for {total} trust(s) "
            f"({window_desc})..."
            + W
        )
        if auto_yes and not dry_run:
            self.stdout.write(
                R + "  --yes: auto-answering 'y' to every prompt without review."
                + W
            )

        found_count = 0
        created_count = 0
        skipped_count = 0
        trusts_with_rels = 0

        for trust in qs:
            ods_code = trust.ods_code
            try:
                ord_record = get_organisation(
                    f"https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations/{ods_code}"
                )
            except Exception as e:
                self.stdout.write(
                    O + f"  {ods_code}: could not fetch ODS record ({e})" + W
                )
                continue

            memberships = _extract_icb_membership_info(ord_record)
            if not memberships:
                continue

            trusts_with_rels += 1

            for m in memberships:
                icb_ods_code = m["icb_ods_code"]
                valid_from_str = m["valid_from"]
                valid_to_str = m["valid_to"]

                valid_from = _parse_ods_date(valid_from_str)
                valid_to = _parse_ods_date(valid_to_str)

                if valid_from is None:
                    continue

                # Apply the --since window.
                if since_date is not None and valid_to is not None:
                    if valid_to < since_date:
                        continue

                # Look up the target ICB in our database. If it is not
                # present, the operator should run backfill_successions
                # --entity icb first (which creates missing ICB rows).
                icb = IntegratedCareBoard.objects.filter(
                    ods_code=icb_ods_code
                ).first()
                if icb is None:
                    self.stdout.write(
                        O + f"  {ods_code}: RE5/RE8 → {icb_ods_code} "
                        f"({valid_from_str} → {valid_to_str or 'now'}) — "
                        "ICB not in database, skipping. Run "
                        "backfill_successions --entity icb first." + W
                    )
                    skipped_count += 1
                    continue

                # Idempotency: skip if a membership row already exists.
                existing = TrustIntegratedCareBoardMembership.objects.filter(
                    trust=trust,
                    integrated_care_board=icb,
                    valid_from=valid_from,
                    valid_to=valid_to,
                ).exists()
                if existing:
                    continue

                found_count += 1

                self.stdout.write("")
                self.stdout.write(B + f"  {ods_code} ({trust.name})" + W)
                self.stdout.write(
                    f"  was managed by {icb_ods_code} ({icb.name})"
                )
                self.stdout.write(
                    f"  Operational interval: {valid_from_str} → "
                    f"{valid_to_str or 'now'}"
                )

                if dry_run:
                    self.stdout.write(
                        O + "  [dry-run] would backfill membership row" + W
                    )
                    continue

                if auto_yes:
                    answer = "y"
                else:
                    try:
                        answer = input(
                            f"  Backfill membership {ods_code} → {icb_ods_code} "
                            f"({valid_from_str} → {valid_to_str or 'now'})? "
                            "[y/n/s=skip] "
                        )
                    except EOFError:
                        self.stdout.write(O + "  No input — skipping." + W)
                        skipped_count += 1
                        continue

                answer = answer.strip().lower()
                if answer == "y":
                    with transaction.atomic():
                        backfill_trust_icb_membership(
                            trust,
                            integrated_care_board=icb,
                            valid_from=valid_from,
                            valid_to=valid_to,
                        )
                    created_count += 1
                    self.stdout.write(G + "  Backfilled." + W)
                elif answer == "n":
                    self.stdout.write(O + "  Not backfilled." + W)
                    skipped_count += 1
                else:
                    self.stdout.write(O + "  Skipped." + W)
                    skipped_count += 1

        self.stdout.write("")
        self.stdout.write(B + "Summary:" + W)
        self.stdout.write(f"  Trusts processed: {total}")
        self.stdout.write(f"  Trusts with ICB rels: {trusts_with_rels}")
        self.stdout.write(f"  Found (missing): {found_count}")
        if not dry_run:
            self.stdout.write(G + f"  Backfilled: {created_count}" + W)
            self.stdout.write(O + f"  Skipped/refused: {skipped_count}" + W)
        self.stdout.write("done.")
        rcpch_ascii_art()
