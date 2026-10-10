"""
Shared transport for the monthly ODS report → GitHub-issue path.

``reconcile_ods`` (the unified engine) emits a combined markdown report that
the ``ods-change-detection`` GitHub workflow turns into a monthly issue. The
workflow cannot read the Azure database, so detection runs in an Azure
Container Apps Job which:

1. prints the report between the sentinel markers (so it is also visible in
   the job's console logs), and
2. uploads the report to Azure Blob Storage, from where the workflow
   downloads it and opens an issue if it is non-empty.

This module is the single implementation of that transport. See
documentation/docs/developer/ods-change-detection.md.
"""
import os

from django.core.management.base import CommandError

REPORT_START_MARKER = "<<<ODS_REPORT_START>>>"
REPORT_END_MARKER = "<<<ODS_REPORT_END>>>"


def emit_report(report, stdout):
    """Print the report between the sentinel markers on stdout."""
    stdout.write(REPORT_START_MARKER)
    stdout.write(report)
    stdout.write(REPORT_END_MARKER)


def upload_report(report, stdout, *, required=True):
    """Upload the combined report to Azure Blob Storage.

    The GitHub workflow downloads it from here — the job's console logs are not
    a reliable transport. Uses the job's managed identity via
    ``DefaultAzureCredential`` (the identity needs the Storage Blob Data
    Contributor role on the account).

    When ``required`` is True (the Container Apps job), a missing
    ``ODS_REPORT_STORAGE_ACCOUNT_NAME`` raises ``CommandError`` — a successful
    job that silently skips the upload leaves the workflow with no report to
    download, which is indistinguishable from "no changes" and has caused
    silent failures in production. When ``required`` is False (local use), the
    upload is simply skipped. Local development and tests should mock the
    upload (see test_reconcile_ods.py).
    """
    account_name = os.getenv("ODS_REPORT_STORAGE_ACCOUNT_NAME")
    if not account_name:
        if required:
            raise CommandError(
                "ODS_REPORT_STORAGE_ACCOUNT_NAME is not set — cannot upload "
                "the ODS report to blob storage. The Container Apps job must "
                "have this env var set (see "
                "documentation/docs/developer/ods-change-detection.md)."
            )
        return

    # Imported here so environments without the azure packages can still
    # import the module and run detection.
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
        blob_client.upload_blob(report.encode("utf-8"), overwrite=True)
    except Exception as e:
        raise CommandError(
            f"Could not upload the ODS report to blob storage: {e}"
        )
    stdout.write(
        f"Report uploaded to blob '{container_name}/{blob_name}' in "
        f"storage account '{account_name}'."
    )
