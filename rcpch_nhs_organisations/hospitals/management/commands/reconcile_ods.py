"""
reconcile_ods — the unified ODS reconciliation orchestrator.

Treats ODS as the source of truth and reconciles the local database against it
across four geography levels (organisation, trust, lhb, icb), detecting
attribute, relationship, succession, roster, and status changes.

Replaces the overlapping cron / backfill_successions / backfill_*_memberships /
ods_change_report detection surface with one engine. See
documentation/docs/developer/ods-sync.md.

    python manage.py reconcile_ods \
        [--levels organisation,trust,lhb,icb] \
        [--mode incremental|backfill] \
        [--since YYYY-MM-DD] \
        [--dry-run]            # default; detection only, writes nothing
        [--apply]              # apply only the auto-safe class
        [--report-file PATH]   # clean markdown
        [--check-overlaps]     # fail if the temporal layer has overlaps
        [--rate N]             # requests/sec throttle (default 10)
"""
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from rcpch_nhs_organisations.hospitals.models import OdsSyncRun
from rcpch_nhs_organisations.hospitals.general_functions.reconcile import (
    ReconcileEngine,
    TokenBucketRateLimiter,
    build_report,
    TEMPORAL_FLOOR,
)
from rcpch_nhs_organisations.hospitals.general_functions.ods_report_blob import (
    emit_report,
    upload_report,
)

from .image import rcpch_ascii_art

W = "\033[0m"
R = "\033[31m"
G = "\033[32m"
O = "\033[33m"
B = "\033[34m"

ALL_LEVELS = ["organisation", "trust", "lhb", "icb"]

# Incremental window defaults. The stored last-run date makes the window
# self-adjusting; these only apply to the first run (no prior run) or as a
# safety floor.
DEFAULT_INCREMENTAL_WINDOW_DAYS = 35
# Re-scan a few days before the last run's synced_through to catch anything
# that landed in ODS right around the previous run boundary.
MARGIN_DAYS = 5


class Command(BaseCommand):
    help = (
        "Reconcile the local database against ODS across the organisation, "
        "trust, LHB and ICB levels. Detection fills the PendingOdsChange "
        "review queue (structural changes) and, with --apply, auto-applies "
        "attribute-only changes. See "
        "documentation/docs/developer/ods-sync.md."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--levels",
            type=str,
            default=",".join(ALL_LEVELS),
            help=(
                "Comma-separated levels to reconcile: organisation, trust, "
                "lhb, icb. Defaults to all four."
            ),
        )
        parser.add_argument(
            "--mode",
            type=str,
            choices=["incremental", "backfill"],
            default="incremental",
            help=(
                "incremental = reconcile changes since the last successful run "
                "(the monthly default); backfill = deep-fetch every held entity "
                "and reconstruct full history back to the temporal floor."
            ),
        )
        parser.add_argument(
            "--since",
            type=str,
            default=None,
            help=(
                "Override the window start (YYYY-MM-DD). In incremental mode "
                "this is the /sync window start; in backfill mode it is the "
                "temporal floor (defaults to 2020-12-01)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Detection only; write nothing. This is the safe default behaviour.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help=(
                "Apply only the auto-safe class (attribute changes with no "
                "succession in the window) to the temporal layer, and write "
                "structural changes to the PendingOdsChange queue. Structural "
                "changes are always queued for review, never auto-applied."
            ),
        )
        parser.add_argument(
            "--queue",
            action="store_true",
            default=False,
            help=(
                "With --dry-run, still write structural deltas to the "
                "PendingOdsChange queue (without touching the temporal layer). "
                "Used by the monthly Azure job, which both fills the queue and "
                "raises the GitHub issue. A plain --dry-run writes nothing."
            ),
        )
        parser.add_argument(
            "--report-file",
            type=str,
            default=None,
            help="Write the clean markdown report to this path instead of stdout.",
        )
        parser.add_argument(
            "--check-overlaps",
            action="store_true",
            default=False,
            help=(
                "After reconciling, assert the temporal layer has no two open "
                "version rows and no overlapping intervals. Exits non-zero if "
                "any violation is found."
            ),
        )
        parser.add_argument(
            "--rate",
            type=float,
            default=10.0,
            help="ODS request throttle in requests/second (default 10).",
        )
        parser.add_argument(
            "--upload-blob",
            action="store_true",
            default=False,
            help=(
                "Print the report between the ODS report sentinel markers and "
                "upload it to Azure Blob Storage (ODS_REPORT_STORAGE_ACCOUNT_NAME "
                "et al). This is what the monthly Container Apps job uses so the "
                "GitHub workflow can download the report and open an issue. "
                "Requires the storage env vars; see ods-change-detection.md."
            ),
        )

    def handle(self, *args, **options):
        levels = [lvl.strip() for lvl in options["levels"].split(",") if lvl.strip()]
        for lvl in levels:
            if lvl not in ALL_LEVELS:
                raise CommandError(
                    f"Unknown level '{lvl}'. Choose from: {', '.join(ALL_LEVELS)}."
                )

        mode = options["mode"]
        dry_run = options["dry_run"]
        apply = options["apply"]
        write_queue = options["queue"]
        report_file = options["report_file"]
        check_overlaps = options["check_overlaps"]
        rate = options["rate"]
        upload_blob = options["upload_blob"]

        if apply and dry_run:
            raise CommandError("--apply and --dry-run are mutually exclusive.")
        # Default to dry-run when neither --apply nor --dry-run is given.
        if not apply:
            dry_run = True

        since_override = None
        if options["since"]:
            try:
                since_override = datetime.date.fromisoformat(options["since"])
            except ValueError:
                raise CommandError(
                    f"--since must be YYYY-MM-DD. Got '{options['since']}'."
                )

        scan_since, floor = self._resolve_window(mode, since_override)

        self.stdout.write(
            B + f"reconcile_ods: mode={mode} levels={','.join(levels)} "
            f"{'(dry-run)' if dry_run else '(apply)'}" + W
        )
        if scan_since is None:
            self.stdout.write(f"  Window: full backfill scan (floor {floor})")
        else:
            self.stdout.write(f"  Window: /sync since {scan_since} (floor {floor})")

        run = OdsSyncRun.objects.create(
            mode=mode,
            levels=",".join(levels),
            since=scan_since,
            synced_through=timezone.now().date(),
            dry_run=dry_run,
            status=OdsSyncRun.STATUS_RUNNING,
        )

        rate_limiter = TokenBucketRateLimiter(rate=rate)
        engine = ReconcileEngine(
            levels,
            since=scan_since,
            floor=floor,
            rate_limiter=rate_limiter,
            apply=apply,
            write_queue=write_queue,
            stdout=self.stdout,
        )

        try:
            result = engine.detect()
        except Exception as e:
            run.status = OdsSyncRun.STATUS_FAILED
            run.notes = str(e)
            run.completed_at = timezone.now()
            run.save()
            raise CommandError(f"Detection failed: {e}")

        report = build_report(result)

        # Persist: auto-apply attribute changes (only under --apply) and write
        # structural changes to the queue (under --apply or --dry-run --queue).
        # A plain --dry-run writes nothing.
        counts = engine.persist(result, run=run)

        run.changes_detected = len(result.changes)
        run.report = report
        run.status = OdsSyncRun.STATUS_SUCCESS
        run.completed_at = timezone.now()
        run.save()

        # Emit the report.
        if report_file:
            with open(report_file, "w", encoding="utf-8") as fh:
                fh.write(report)
            self.stdout.write(f"  Report written to {report_file}")
        else:
            self.stdout.write("")
            self.stdout.write(report if report.strip() else O + "No changes detected." + W)

        # Monthly-job transport: emit between sentinel markers and upload to
        # blob storage, keeping the existing blob -> GitHub-issue path.
        if upload_blob:
            emit_report(report, self.stdout)
            upload_report(report, self.stdout, required=True)

        self.stdout.write("")
        self.stdout.write(B + "Summary:" + W)
        self.stdout.write(f"  Changes detected: {len(result.changes)}")
        self.stdout.write(f"  Legacy pre-floor skips (collapsed): {result.legacy_skips}")
        self.stdout.write(f"  Fetch errors: {len(result.fetch_errors)}")
        self.stdout.write(G + f"  Queued: {counts['queued']}" + W)
        self.stdout.write(f"  Re-queued (refreshed): {counts['requeued']}")
        self.stdout.write(G + f"  Auto-applied: {counts['applied']}" + W)
        self.stdout.write(f"  Skipped (terminal): {counts['skipped']}")

        if check_overlaps:
            problems = engine.check_overlaps()
            self.stdout.write("")
            if problems:
                self.stdout.write(R + f"Overlap check FAILED ({len(problems)}):" + W)
                for p in problems:
                    self.stdout.write(R + f"  - {p}" + W)
                raise CommandError(
                    f"Temporal overlap check failed with {len(problems)} violation(s)."
                )
            self.stdout.write(G + "Overlap check passed — no open-row or interval overlaps." + W)

        self.stdout.write("done.")
        if not report_file:
            rcpch_ascii_art()

    def _resolve_window(self, mode, since_override):
        """Return (scan_since, floor).

        scan_since is the /sync window start (None = deep-fetch everything, the
        backfill scan). floor is the temporal floor for succession scope.
        """
        if mode == "backfill":
            floor = since_override or TEMPORAL_FLOOR
            return None, floor

        # incremental
        floor = TEMPORAL_FLOOR
        if since_override is not None:
            return since_override, floor

        last = OdsSyncRun.last_successful(mode=OdsSyncRun.MODE_INCREMENTAL)
        if last is not None and last.synced_through is not None:
            scan_since = last.synced_through - datetime.timedelta(days=MARGIN_DAYS)
        else:
            scan_since = timezone.now().date() - datetime.timedelta(
                days=DEFAULT_INCREMENTAL_WINDOW_DAYS
            )
        return scan_since, floor
