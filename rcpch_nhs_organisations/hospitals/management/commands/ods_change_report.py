"""
Run all ODS change-detection dry-run checks and print a single combined
markdown report between sentinel markers.

Used by the ods-change-detection GitHub workflow via the Azure Container Apps
Job (``<app>-ods-check``): the job runs this command, uploads the combined
report to Azure Blob Storage, and the workflow downloads it from there and
opens a GitHub issue if the report is non-empty.

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

The combined report is also uploaded to Azure Blob Storage (managed identity
auth — the job's identity needs the Storage Blob Data Contributor role on
the account), which is how the GitHub workflow retrieves it. The upload is
skipped when ODS_REPORT_STORAGE_ACCOUNT_NAME is not set (local development
and tests); the report is always printed between the sentinel markers so it
can also be read in the job's console logs.
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

        # Print between sentinel markers so the report can also be read
        # directly in the job's console logs. The GitHub workflow retrieves
        # the report from blob storage (see _upload_report).
        self.stdout.write(REPORT_START_MARKER)
        self.stdout.write(combined)
        self.stdout.write(REPORT_END_MARKER)

        self._upload_report(combined)

        if errors:
            raise CommandError(
                f"{len(errors)} of {len(CHECKS)} ODS change-detection checks "
                "failed — see the Check failures section of the report."
            )

    def _upload_report(self, combined):
        """Upload the combined report to Azure Blob Storage.

        The GitHub workflow downloads it from here — the job's console logs
        are not a reliable transport. Uses the job's managed identity via
        DefaultAzureCredential (the identity needs the Storage Blob Data
        Contributor role on the account).

        Fails loudly (CommandError) if ODS_REPORT_STORAGE_ACCOUNT_NAME is not
        set — a successful job that silently skips the upload leaves the
        workflow with no report to download, which is indistinguishable from
        "no changes" and has caused silent failures in production. Local
        development and tests should mock the upload (see test_ods_change_report.py).
        """
        account_name = os.getenv("ODS_REPORT_STORAGE_ACCOUNT_NAME")
        if not account_name:
            raise CommandError(
                "ODS_REPORT_STORAGE_ACCOUNT_NAME is not set — cannot upload "
                "the ODS change report to blob storage. The Container Apps job "
                "must have this env var set (see "
                "documentation/docs/developer/ods-change-detection.md)."
            )

        # Imported here so environments without the azure packages can still
        # import the module and run the checks.
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobClient

        container_name = os.getenv("ODS_REPORT_CONTAINER_NAME", "ods-change-reports")
        blob_name = os.getenv("ODS_REPORT_BLOB_NAME", "ods-change-report.md")
        try:
            blob_client = BlobClient(
                account_url=f"https://{account_name}.blob.core.windows.net",
                container_name=container_name,
                blob_name=blob_name,
                credential=DefaultAzureCredential(),
            )
            blob_client.upload_blob(combined.encode("utf-8"), overwrite=True)
        except Exception as e:
            raise CommandError(
                f"Could not upload the ODS change report to blob storage: {e}"
            )
        self.stdout.write(
            f"Report uploaded to blob '{container_name}/{blob_name}' in "
            f"storage account '{account_name}'."
        )