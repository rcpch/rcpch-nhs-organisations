# python libraries

# django
from django.core.management.base import BaseCommand, CommandError


# RCPCH
from ...general_functions.ods_update import update_organisation_model_with_ORD_changes


from .image import rcpch_ascii_art

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
P = "\033[35m"  # purple
BOLD = "\033[1m"
END = "\033[0m"


# The ODS /sync endpoint returns changes from the LastChangeDate query
# parameter forward, with a hard limit of 185 days into the past.
ODS_MAX_TIME_FRAME_DAYS = 185


class Command(BaseCommand):
    help = "Update the organisation list from the NHS ODS API."

    def add_arguments(self, parser):
        parser.add_argument("--service", type=str, help="Service")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report what would change without writing to the database.",
        )
        parser.add_argument(
            "--report-file",
            type=str,
            default=None,
            help=(
                "When used with --dry-run, write the markdown report to this "
                "file path instead of stdout. Used by the GitHub Action for ODS "
                "change detection."
            ),
        )
        parser.add_argument(
            "--time-frame",
            type=int,
            default=30,
            help=(
                "Number of days of ODS changes to fetch (1-185). Default 30. "
                "Use 185 for the full ODS recovery window — see "
                "documentation/docs/developer/backfill-plan.md."
            ),
        )

    def handle(self, *args, **options):
        if options["service"] == "organisations":
            time_frame = options["time_frame"]
            if time_frame < 1 or time_frame > ODS_MAX_TIME_FRAME_DAYS:
                raise CommandError(
                    f"--time-frame must be between 1 and {ODS_MAX_TIME_FRAME_DAYS} days "
                    f"(the ODS API hard limit). Got {time_frame}."
                )
            self.stdout.write(
                B + f"Checking for organisation updates (last {time_frame} days)..." + W
            )
            report_file = options.get("report_file")
            if options["dry_run"] and report_file:
                # Write the report to a file so the GitHub Action can detect
                # empty (no changes) vs non-empty (changes detected) without
                # stdout pollution from the ASCII art / status messages.
                import io
                file_stdout = io.StringIO()
                changes_found = update_organisation_model_with_ORD_changes(
                    dry_run=True,
                    stdout=file_stdout,
                    time_frame=time_frame,
                )
                report = file_stdout.getvalue()
                with open(report_file, "w") as f:
                    f.write(report)
            else:
                changes_found = update_organisation_model_with_ORD_changes(
                    dry_run=options["dry_run"],
                    stdout=self.stdout if options["dry_run"] else None,
                    time_frame=time_frame,
                )
            if options["dry_run"]:
                if changes_found:
                    self.stdout.write(
                        G + "Dry run complete: changes detected (see report above)." + W
                    )
                else:
                    self.stdout.write(
                        G + "Dry run complete: no changes detected." + W
                    )
            rcpch_ascii_art()

        else:
            self.stdout.write("No options supplied...")
        self.stdout.write(rcpch_ascii_art())
        self.stdout.write("done.")
