"""
Run all ODS change-detection dry-run checks and print a single combined
markdown report between sentinel markers.

Used by the ods-change-detection GitHub workflow via the Azure Container Apps
Job (``<app>-ods-check``): the job runs this command, and the workflow
extracts the text between the markers from the job's console logs and opens a
GitHub issue if the report is non-empty.

The checks must run against the production database, which is only reachable
from inside the Container Apps environment — hence a job rather than a
GitHub-hosted runner. See documentation/docs/developer/ods-change-detection.md.

The three checks are the same ones the original GitHub Action ran directly:

1. ODS sync (trusts + organisations) — the /sync endpoint for recent changes.
2. Trust succession backfill — the /organisations/{ods_code} Succs block for
   every trust, reporting missing TrustSuccession rows.
3. ICB succession backfill — the Succs block for every ICB, reporting missing
   IntegratedCareBoardSuccession rows and missing successor ICBs.

Each check runs with --report-file so its clean markdown report is written to
a temp file without the status noise (banners, summaries, ASCII art, ANSI
colour codes), then the non-empty reports are combined under section headings.

If any check raises, the error is recorded, the remaining checks still run,
a "Check failures" section is appended to the printed report, and the command
exits non-zero so the job execution is marked Failed (the workflow then opens
a "check failed" issue rather than a "changes detected" issue).
"""
import io
import os
import tempfile

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


REPORT_START_MARKER = "<<<ODS_REPORT_START>>>"
REPORT_END_MARKER = "<<<ODS_REPORT_END>>>"


# (section title, command name, command arguments) for each dry-run check.
CHECKS = [
    (
        "ODS sync changes (trusts + organisations)",
        "cron",
        ["--service", "organisations", "--dry-run"],
    ),
    (
        "Trust succession backfill",
        "backfill_successions",
        ["--entity", "trust", "--dry-run"],
    ),
    (
        "ICB succession backfill",
        "backfill_successions",
        ["--entity", "icb", "--dry-run"],
    ),
]


class Command(BaseCommand):
    help = (
        "Run the ODS change-detection dry-run checks and print a combined "
        "markdown report between sentinel markers, for the GitHub workflow "
        "to extract from the Container Apps job console logs."
    )

    def handle(self, *args, **options):
        sections = []
        errors = []

        tmpdir = tempfile.mkdtemp(prefix="ods-change-report-")
        for index, (title, command_name, command_args) in enumerate(CHECKS):
            report_path = os.path.join(tmpdir, f"check_{index}.md")
            try:
                call_command(
                    command_name,
                    *command_args,
                    "--report-file",
                    report_path,
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            except Exception as e:
                errors.append(f"- **{title}**: `{e}`")
                continue
            with open(report_path, encoding="utf-8") as f:
                content = f.read()
            if content.strip():
                sections.append((title, content.strip()))

        combined = ""
        for title, content in sections:
            combined += f"## {title}\n\n{content}\n\n"
        if errors:
            combined += "## Check failures\n\n" + "\n".join(errors) + "\n\n"

        # Print between sentinel markers so the GitHub workflow can extract
        # the report from the job's console logs regardless of any log-line
        # prefixes the logging pipeline adds.
        self.stdout.write(REPORT_START_MARKER)
        self.stdout.write(combined)
        self.stdout.write(REPORT_END_MARKER)

        if errors:
            raise CommandError(
                f"{len(errors)} of {len(CHECKS)} ODS change-detection checks "
                "failed — see the Check failures section of the report."
            )