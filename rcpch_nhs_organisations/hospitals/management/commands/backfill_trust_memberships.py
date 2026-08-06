# python imports
import datetime

# django
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# RCPCH
from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    get_organisation,
    _extract_trust_membership_info,
    _parse_ods_date,
)
from rcpch_nhs_organisations.hospitals.general_functions.membership import (
    backfill_organisation_trust_membership,
)
from rcpch_nhs_organisations.hospitals.models import (
    Organisation,
    OrganisationTrustMembership,
    Trust,
)

from .image import rcpch_ascii_art

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
BOLD = "\033[1m"

# RE6 is the ODS relationship type for "is a site of" — the link from an
# NHS Trust Site (RO198) to its parent NHS Trust (RO197). This is the only
# Rel type that records parent-trust membership. See
# documentation/docs/developer/ods-api.md and backfill.md Part 3.
TRUST_SITE_REL_ID = "RE6"

# Default lookback window. The audit reports that consume this data cover
# the last ~5 years, so the default run recovers memberships whose
# operational interval overlaps that window. Use --since for a different
# window, or --all for the full history (bounded only by what ODS holds).
DEFAULT_SINCE_YEARS = 5


class Command(BaseCommand):
    help = (
        "Backfill historical OrganisationTrustMembership rows from the ODS "
        "Rels block for every organisation in the database. The ODS "
        "/organisations/{ods_code} endpoint returns the complete Rels "
        "history regardless of when a relationship ended, so this recovers "
        "trust memberships that were overwritten before the temporal layer "
        "was installed — the Layer 2 gap left by backfill_successions "
        "(which only recovers Layer 3 succession rows). "
        "See documentation/docs/developer/backfill.md."
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
                f"{DEFAULT_SINCE_YEARS} years ago. Use --all for the full "
                "history held by ODS."
            ),
        )
        parser.add_argument(
            "--all",
            action="store_true",
            default=False,
            help=(
                "Recover the full membership history held by ODS, ignoring "
                "the --since window. Use with care: this writes a row for "
                "every RE6 rel on every organisation, including very old "
                "ones."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of organisations to process (for testing).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        use_all = options["all"]
        since_str = options["since"]
        limit = options["limit"]

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
            since_date = datetime.date.today() - datetime.timedelta(
                days=DEFAULT_SINCE_YEARS * 365
            )

        qs = Organisation.objects.all()
        if limit:
            qs = qs[:limit]

        total = qs.count()
        window_desc = (
            "the full ODS history" if since_date is None else f"since {since_date}"
        )
        self.stdout.write(
            B
            + f"Backfilling trust memberships for {total} organisation(s) "
            f"({window_desc})..."
            + W
        )

        found_count = 0
        created_count = 0
        skipped_count = 0
        orgs_with_rels = 0

        for org in qs:
            ods_code = org.ods_code
            # Fetch the full ODS record. The /organisations/{ods_code}
            # endpoint returns the complete Rels block regardless of when
            # the relationship ended — this is not subject to the 185-day
            # /sync limit.
            try:
                ord_record = get_organisation(
                    f"https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations/{ods_code}"
                )
            except Exception as e:
                self.stdout.write(
                    O + f"  {ods_code}: could not fetch ODS record ({e})" + W
                )
                continue

            memberships = _extract_trust_membership_info(ord_record)
            if not memberships:
                continue

            orgs_with_rels += 1

            for m in memberships:
                trust_ods_code = m["trust_ods_code"]
                valid_from_str = m["valid_from"]
                valid_to_str = m["valid_to"]

                valid_from = _parse_ods_date(valid_from_str)
                valid_to = _parse_ods_date(valid_to_str)

                if valid_from is None:
                    # _extract_trust_membership_info already skips undated
                    # rels, but guard against bad parses.
                    continue

                # Apply the --since window. A rel overlaps the window if its
                # operational interval extends past the window start. A rel
                # that ended before the window is out of scope for the audit
                # reports this command serves.
                if since_date is not None and valid_to is not None:
                    if valid_to < since_date:
                        continue

                # Look up the target trust in our database. If it is not
                # present, the operator should run backfill_successions first
                # (which creates predecessor trust rows) or create the trust
                # via the admin / mergers command.
                trust = Trust.objects.filter(ods_code=trust_ods_code).first()
                if trust is None:
                    self.stdout.write(
                        O + f"  {ods_code}: RE6 → {trust_ods_code} "
                        f"({valid_from_str} → {valid_to_str or 'now'}) — "
                        "trust not in database, skipping. Run "
                        "backfill_successions --entity trust first." + W
                    )
                    skipped_count += 1
                    continue

                # Idempotency: skip if a membership row already exists for
                # the same (organisation, trust, valid_from, valid_to)
                # interval. This makes the command safe to re-run.
                existing = OrganisationTrustMembership.objects.filter(
                    organisation=org,
                    trust=trust,
                    valid_from=valid_from,
                    valid_to=valid_to,
                ).exists()
                if existing:
                    continue

                found_count += 1

                self.stdout.write("")
                self.stdout.write(B + f"  {ods_code} ({org.name})" + W)
                self.stdout.write(
                    f"  was a site of {trust_ods_code} ({trust.name})"
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

                # Interactive prompt: yes / no / skip. Mirrors
                # backfill_successions so operators have a consistent UX.
                try:
                    answer = input(
                        f"  Backfill membership {ods_code} → {trust_ods_code} "
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
                        backfill_organisation_trust_membership(
                            org,
                            trust=trust,
                            valid_from=valid_from,
                            valid_to=valid_to,
                        )
                    created_count += 1
                    self.stdout.write(G + "  Backfilled." + W)
                elif answer == "n":
                    self.stdout.write(O + "  Not backfilled." + W)
                    skipped_count += 1
                else:  # 's' or anything else
                    self.stdout.write(O + "  Skipped." + W)
                    skipped_count += 1

        self.stdout.write("")
        self.stdout.write(B + "Summary:" + W)
        self.stdout.write(f"  Organisations processed: {total}")
        self.stdout.write(f"  Organisations with RE6 rels: {orgs_with_rels}")
        self.stdout.write(f"  Found (missing): {found_count}")
        if not dry_run:
            self.stdout.write(G + f"  Backfilled: {created_count}" + W)
            self.stdout.write(O + f"  Skipped/refused: {skipped_count}" + W)
        self.stdout.write("done.")
        rcpch_ascii_art()
