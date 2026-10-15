# python imports
import datetime
import sys

# django
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

# RCPCH
from rcpch_nhs_organisations.hospitals.constants.known_parallel_organisations import (
    KNOWN_PARALLEL_ORGANISATIONS,
)
from rcpch_nhs_organisations.hospitals.general_functions.reconcile.ods_sources import (
    deep_fetch,
)
from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    _extract_ord_fields,
)
from rcpch_nhs_organisations.hospitals.general_functions import membership as m

from .image import rcpch_ascii_art

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
BOLD = "\033[1m"


class Command(BaseCommand):
    help = (
        "Complete half-applied parallel-code organisation successions from the "
        "curated KNOWN_PARALLEL_ORGANISATIONS list.\n\n"
        "Some organisation code changes (where ODS closed a site's code and "
        "issued a new one under a successor trust) were half-applied before the "
        "inherit_organisation_state fix: the successor Organisation row was "
        "created and its trust reparented, but the baseline OrganisationVersion "
        "and non-trust membership rows were never created, and the predecessor's "
        "memberships were never closed.\n\n"
        "This command sweeps the KNOWN_PARALLEL_ORGANISATIONS list and completes "
        "each succession by creating the successor if missing (deep-fetched from "
        "ODS), ensuring the trust membership, creating the OrganisationSuccession "
        "link, inheriting the predecessor's non-trust state, and flagging the "
        "predecessor as diverged.\n\n"
        "The effective date is derived from the matching TrustSuccession "
        "(predecessor_trust -> successor_trust), or from --effective-date if "
        "given, or defaults to today.\n\n"
        "Run with --dry-run to see what would be done without writing anything."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be done without writing anything.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the confirmation prompt when applying.",
        )
        parser.add_argument(
            "--effective-date",
            type=str,
            default=None,
            help="Override the derived effective date (YYYY-MM-DD) for all entries.",
        )
        parser.add_argument(
            "--predecessor",
            type=str,
            default=None,
            help="Only process the entry with this predecessor ODS code.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_confirm = options["yes"]
        override_date = (
            datetime.date.fromisoformat(options["effective_date"])
            if options["effective_date"]
            else None
        )
        predecessor_filter = options["predecessor"]

        Organisation = apps.get_model("hospitals", "Organisation")
        OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")
        Trust = apps.get_model("hospitals", "Trust")
        OrganisationSuccession = apps.get_model(
            "hospitals", "OrganisationSuccession"
        )
        TrustSuccession = apps.get_model("hospitals", "TrustSuccession")

        entries = list(KNOWN_PARALLEL_ORGANISATIONS)
        if predecessor_filter:
            entries = [
                e
                for e in entries
                if e["predecessor_ods_code"] == predecessor_filter
            ]

        # --- First pass: collect what needs doing ---
        actions = []
        for entry in entries:
            pred_code = entry["predecessor_ods_code"]
            succ_code = entry["successor_ods_code"]
            pred_trust = entry["predecessor_trust"]
            succ_trust = entry["successor_trust"]

            if not succ_code:
                actions.append(
                    {
                        "pred": pred_code,
                        "succ": succ_code,
                        "ev": None,
                        "action": "skip (no successor — subsumed)",
                        "error": True,
                    }
                )
                continue

            # Resolve the effective date.
            if override_date:
                ev = override_date
            else:
                ts = TrustSuccession.objects.filter(
                    predecessor__ods_code=pred_trust,
                    successor__ods_code=succ_trust,
                ).first()
                ev = ts.succession_date if ts else timezone.now().date()

            pred = Organisation.objects.filter(ods_code=pred_code).first()
            if pred is None:
                actions.append(
                    {
                        "pred": pred_code,
                        "succ": succ_code,
                        "ev": ev,
                        "action": "skip (predecessor not in DB)",
                        "error": True,
                    }
                )
                continue

            succ = Organisation.objects.filter(ods_code=succ_code).first()
            has_version = (
                OrganisationVersion.objects.filter(
                    organisation=succ, valid_to__isnull=True
                ).exists()
                if succ
                else False
            )

            if succ is None:
                action_label = f"create {succ_code} + inherit + flag"
            elif not has_version:
                action_label = f"inherit to {succ_code} + flag"
            else:
                # Successor has a baseline version — still call
                # inherit_organisation_state (idempotent) to add any missing
                # memberships and close the predecessor's open rows.
                action_label = f"complete {succ_code} memberships + close predecessor + flag"

            actions.append(
                {
                    "pred": pred_code,
                    "succ": succ_code,
                    "ev": ev,
                    "action": action_label,
                    "error": False,
                    "pred_obj": pred,
                    "succ_obj": succ,
                    "has_version": has_version,
                    "succ_trust": succ_trust,
                }
            )

        # --- Print the report ---
        rcpch_ascii_art()
        self.stdout.write("")
        self.stdout.write(
            f"{B}Parallel-code succession sweep{W} — "
            f"{len(entries)} entries in KNOWN_PARALLEL_ORGANISATIONS"
        )
        if predecessor_filter:
            self.stdout.write(f"  (filtered to predecessor {predecessor_filter})")
        self.stdout.write("")

        for a in actions:
            ev_str = str(a["ev"]) if a["ev"] else "—"
            if a["error"]:
                self.stdout.write(
                    f"  {O}{a['pred']:>10}  →  {a['succ'] or '(none)':<10}{W}  "
                    f"{a['action']}  {O}(skipped){W}"
                )
            else:
                self.stdout.write(
                    f"  {a['pred']:>10}  →  {a['succ']:<10}  "
                    f"{a['action']}  (effective {ev_str})"
                )
        self.stdout.write("")

        applyable = [a for a in actions if not a["error"]]
        if not applyable:
            self.stdout.write(f"{G}Nothing to apply.{W}")
            return

        if dry_run:
            self.stdout.write(f"{O}--dry-run: no changes written.{W}")
            return

        # --- Confirm ---
        if not skip_confirm:
            self.stdout.write(
                f"{O}This will apply {len(applyable)} succession(s). "
                f"Continue? [y/N] {W}"
            )
            response = input().strip().lower()
            if response != "y":
                self.stdout.write("Aborted.")
                return

        # --- Second pass: apply ---
        success_count = 0
        error_count = 0
        for a in actions:
            if a["error"]:
                continue

            pred = a["pred_obj"]
            ev = a["ev"]
            succ = a["succ_obj"]
            succ_code = a["succ"]
            succ_trust_code = a["succ_trust"]
            has_version = a["has_version"]

            try:
                # Create the successor if missing (deep-fetch from ODS).
                if succ is None:
                    record = deep_fetch(succ_code)
                    if record is None:
                        self.stderr.write(
                            f"{R}ERROR: could not fetch {succ_code} from ODS — "
                            f"create it with `mergers --organisations {succ_code} "
                            f"--create` first, then re-run.{W}"
                        )
                        error_count += 1
                        continue
                    fields = _extract_ord_fields(record)
                    with transaction.atomic():
                        succ, _created = Organisation.objects.get_or_create(
                            ods_code=succ_code,
                            defaults={
                                "name": fields.get("name"),
                                "address1": fields.get("address1"),
                                "address2": fields.get("address2"),
                                "address3": fields.get("address3"),
                                "city": fields.get("city"),
                                "county": fields.get("county"),
                                "postcode": fields.get("postcode"),
                                "telephone": fields.get("telephone"),
                                "website": fields.get("website"),
                                "active": True,
                            },
                        )

                # Ensure trust membership on the successor.
                new_trust = Trust.objects.filter(
                    ods_code=succ_trust_code
                ).first()
                if new_trust is not None and succ.trust_id != new_trust.pk:
                    m.reassign_organisation_trust(
                        succ, new_trust, effective_date=ev
                    )

                with transaction.atomic():
                    # Create the succession link if missing.
                    OrganisationSuccession.objects.get_or_create(
                        predecessor=pred,
                        successor=succ,
                        succession_date=ev,
                        defaults={
                            "succession_type": "code_change",
                            "notes": (
                                "Created by apply_parallel_successions command "
                                "from KNOWN_PARALLEL_ORGANISATIONS."
                            ),
                        },
                    )

                    if not has_version:
                        # Full inheritance: baseline version + memberships +
                        # close predecessor.
                        m.inherit_organisation_state(
                            pred, succ, effective_date=ev
                        )
                    else:
                        # Successor already has a baseline version. Still
                        # call inherit_organisation_state to add any missing
                        # non-trust memberships (it is idempotent via
                        # get_or_create) and close the predecessor's open
                        # memberships.
                        m.inherit_organisation_state(
                            pred, succ, effective_date=ev
                        )

                    # Flag the predecessor as diverged.
                    pred.diverged_from_ods = True
                    pred.ods_replacement_code = succ_code
                    pred.save(
                        update_fields=[
                            "diverged_from_ods",
                            "ods_replacement_code",
                            "updated_at",
                        ]
                    )

                success_count += 1
                self.stdout.write(
                    f"{G}  {a['pred']} → {succ_code}: completed{W}"
                )
            except Exception as exc:
                error_count += 1
                self.stderr.write(
                    f"{R}  {a['pred']} → {succ_code}: ERROR — {exc}{W}"
                )

        self.stdout.write("")
        self.stdout.write(
            f"{B}Done:{W} {success_count} succeeded, {error_count} failed."
        )