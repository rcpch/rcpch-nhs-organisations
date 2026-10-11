# python imports
import datetime

# django
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# RCPCH
from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    get_organisation,
    _extract_icb_membership_info,
    build_trust_icb_timeline,
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
        "Backfill and repair TrustIntegratedCareBoardMembership rows from the "
        "ODS Rels block for every trust in the database. The ODS "
        "/organisations/{ods_code} endpoint returns the complete Rels "
        "history regardless of when a relationship ended, so this recovers "
        "ICB memberships that were overwritten before the temporal layer "
        "was installed. Only RO261 (ICB) targets are recovered — CCG "
        "(RO210) and STP (RO132) targets are ignored.\n\n"
        "ODS carries several concurrent ICB rels per trust (a legacy RE5 rel "
        "it never closes, plus maintained RE8 rels). This command collapses "
        "them into a single-ICB timeline with exactly one current (open) row, "
        "and repairs any trust left with duplicate or overlapping open rows by "
        "an earlier run. Re-running is safe and idempotent. See "
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
        removed_count = 0
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

            # Collapse ODS's overlapping RE5/RE8 rels into a clean single-ICB
            # timeline (at most one open row). This is what repairs trusts that
            # an earlier verbatim run left with duplicate/overlapping open rows.
            timeline = build_trust_icb_timeline(memberships)

            # Apply the --since window: drop segments that ended before it.
            if since_date is not None:
                timeline = [
                    s
                    for s in timeline
                    if s["valid_to"] is None or s["valid_to"] >= since_date
                ]

            # Resolve the target ICBs. A missing ICB (typically a brand-new
            # 2026 reorganisation code) means backfill_successions --entity icb
            # has not been run yet; skip that segment and warn.
            resolved = []
            for segment in timeline:
                icb_ods_code = segment["icb_ods_code"]
                icb = IntegratedCareBoard.objects.filter(
                    ods_code=icb_ods_code
                ).first()
                if icb is None:
                    self.stdout.write(
                        O + f"  {ods_code}: RE5/RE8 → {icb_ods_code} "
                        f"({segment['valid_from']} → "
                        f"{segment['valid_to'] or 'now'}) — "
                        "ICB not in database, skipping. Run "
                        "backfill_successions --entity icb first." + W
                    )
                    skipped_count += 1
                    continue
                resolved.append(
                    (icb, segment["valid_from"], segment["valid_to"])
                )

            # Reconcile the existing rows against the resolved timeline:
            # create the segments we are missing, and delete stale/overlapping
            # rows no longer in the timeline. The membership table is entirely
            # ODS-derived (never hand-curated), so pruning machine-generated
            # rows here is the sanctioned repair path.
            existing = list(
                TrustIntegratedCareBoardMembership.objects.filter(trust=trust)
            )
            target_keys = {
                (icb.id, valid_from, valid_to)
                for icb, valid_from, valid_to in resolved
            }
            existing_keys = {
                (r.integrated_care_board_id, r.valid_from, r.valid_to)
                for r in existing
            }
            to_create = [
                (icb, valid_from, valid_to)
                for icb, valid_from, valid_to in resolved
                if (icb.id, valid_from, valid_to) not in existing_keys
            ]
            to_delete = [
                r
                for r in existing
                if (r.integrated_care_board_id, r.valid_from, r.valid_to)
                not in target_keys
            ]

            if not to_create and not to_delete:
                continue

            found_count += 1
            self.stdout.write("")
            self.stdout.write(B + f"  {ods_code} ({trust.name})" + W)
            for icb, valid_from, valid_to in to_create:
                self.stdout.write(
                    f"  + {icb.ods_code} ({icb.name}): "
                    f"{valid_from} → {valid_to or 'now'}"
                )
            for r in to_delete:
                self.stdout.write(
                    O + f"  - {r.integrated_care_board.ods_code}: "
                    f"{r.valid_from} → {r.valid_to or 'now'} "
                    "(stale/overlapping)" + W
                )

            if dry_run:
                self.stdout.write(
                    O + "  [dry-run] would apply the changes above" + W
                )
                continue

            if auto_yes:
                answer = "y"
            else:
                try:
                    answer = input(
                        f"  Apply {len(to_create)} add(s) and "
                        f"{len(to_delete)} removal(s) for {ods_code}? "
                        "[y/n/s=skip] "
                    )
                except EOFError:
                    self.stdout.write(O + "  No input — skipping." + W)
                    skipped_count += 1
                    continue

            answer = answer.strip().lower()
            if answer != "y":
                self.stdout.write(O + "  Skipped." + W)
                skipped_count += 1
                continue

            with transaction.atomic():
                for r in to_delete:
                    r.delete()
                    removed_count += 1
                for icb, valid_from, valid_to in to_create:
                    backfill_trust_icb_membership(
                        trust,
                        integrated_care_board=icb,
                        valid_from=valid_from,
                        valid_to=valid_to,
                    )
                    created_count += 1
            self.stdout.write(G + "  Applied." + W)

        self.stdout.write("")
        self.stdout.write(B + "Summary:" + W)
        self.stdout.write(f"  Trusts processed: {total}")
        self.stdout.write(f"  Trusts with ICB rels: {trusts_with_rels}")
        self.stdout.write(f"  Trusts changed: {found_count}")
        if not dry_run:
            self.stdout.write(G + f"  Rows created: {created_count}" + W)
            self.stdout.write(
                O + f"  Rows removed (stale/overlapping): {removed_count}" + W
            )
            self.stdout.write(O + f"  Trusts skipped/refused: {skipped_count}" + W)
        self.stdout.write("done.")
        rcpch_ascii_art()
