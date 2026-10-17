# python imports
import datetime

# django
from django.apps import apps
from django.core.management.base import BaseCommand

from .image import rcpch_ascii_art

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
BOLD = "\033[1m"

# Membership models to audit for active organisations in England.
# Each entry is (model_name, parent_field, relationship_label).
# Trust is always expected; ICB / region / OPEN UK are expected for English
# hospital sites. PDU is not audited here because not every site has a PDU —
# use the snapshot endpoint or the PDU constants for that check.
_AUDITED_MEMBERSHIPS = [
    ("OrganisationTrustMembership", "trust", "trust"),
    ("OrganisationIntegratedCareBoardMembership", "integrated_care_board", "ICB"),
    ("OrganisationNHSEnglandRegionMembership", "nhs_england_region", "NHS England region"),
    ("OrganisationOPENUKNetworkMembership", "openuk_network", "OPEN UK network"),
]


class Command(BaseCommand):
    help = (
        "Audit every active Organisation for missing current membership rows "
        "(trust, ICB, NHS England region, OPEN UK network) and missing baseline "
        "OrganisationVersion.\n\n"
        "The snapshot endpoint reads parent relationships from the membership "
        "tables, not the denormalised FK on the Organisation row. An organisation "
        "with a denormalised trust FK but no OrganisationTrustMembership row "
        "appears under its trust in the trusts endpoint but returns null trust "
        "(and null ICB / region / OPEN UK) on the snapshot — the half-applied "
        "succession gap.\n\n"
        "This command lists active organisations where any expected current "
        "membership is missing, or where no baseline OrganisationVersion exists. "
        "Use it to find sites that need the same fix as RW155, RW1YH, RBN52, etc.\n\n"
        "Flags: --include-inactive to also audit inactive organisations (e.g. "
        "predecessors whose memberships were never closed). --country to filter "
        "by country name (e.g. 'England')."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Also audit inactive organisations (predecessors etc.).",
        )
        parser.add_argument(
            "--country",
            type=str,
            default=None,
            help="Filter by country name (e.g. 'England'). Default: all.",
        )
        parser.add_argument(
            "--missing",
            type=str,
            default=None,
            help=(
                "Only report organisations missing this relationship. "
                "One of: version, trust, icb, region, openuk, all (default)."
            ),
        )

    def handle(self, *args, **options):
        include_inactive = options["include_inactive"]
        country_filter = options["country"]
        missing_filter = (options["missing"] or "all").lower()

        Organisation = apps.get_model("hospitals", "Organisation")
        OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")

        rcpch_ascii_art()
        self.stdout.write("")

        qs = Organisation.objects.all()
        if not include_inactive:
            qs = qs.filter(active=True)
        if country_filter:
            qs = qs.filter(country__name__iexact=country_filter)
        qs = qs.order_by("ods_code")

        # Build the report.
        report = []
        for org in qs.iterator():
            issues = []

            # Check baseline OrganisationVersion.
            has_version = OrganisationVersion.objects.filter(
                organisation=org, valid_to__isnull=True
            ).exists()
            if not has_version:
                issues.append("no baseline OrganisationVersion")

            # Check each expected current membership.
            for model_name, _parent_field, label in _AUDITED_MEMBERSHIPS:
                Model = apps.get_model("hospitals", model_name)
                has_current = Model.objects.filter(
                    organisation=org, valid_to__isnull=True
                ).exists()
                if not has_current:
                    issues.append(f"no current {label} membership")

            if not issues:
                continue

            # Filter by --missing if specified.
            if missing_filter != "all":
                filter_map = {
                    "version": "no baseline OrganisationVersion",
                    "trust": "no current trust membership",
                    "icb": "no current ICB membership",
                    "region": "no current NHS England region membership",
                    "openuk": "no current OPEN UK network membership",
                }
                if filter_map.get(missing_filter) not in issues:
                    continue

            report.append(
                {
                    "ods_code": org.ods_code,
                    "name": org.name,
                    "active": org.active,
                    "trust": org.trust.ods_code if org.trust else None,
                    "issues": issues,
                }
            )

        # Print the report.
        if not report:
            self.stdout.write(f"{G}No organisations with missing memberships found.{W}")
            return

        self.stdout.write(
            f"{B}Organisation relationship audit{W} — "
            f"{len(report)} organisation(s) with missing memberships"
        )
        if not include_inactive:
            self.stdout.write(f"  (active only — use --include-inactive for all)")
        if country_filter:
            self.stdout.write(f"  (filtered to country '{country_filter}')")
        self.stdout.write("")

        for entry in report:
            status = f"{G}active{W}" if entry["active"] else f"{O}inactive{W}"
            issues_str = "; ".join(entry["issues"])
            trust_str = entry["trust"] or "—"
            self.stdout.write(
                f"  {entry['ods_code']:>10}  trust={trust_str:<8}  "
                f"[{status}]  {issues_str}"
            )

        self.stdout.write("")
        self.stdout.write(
            f"{B}Total:{W} {len(report)} organisation(s) need attention."
        )