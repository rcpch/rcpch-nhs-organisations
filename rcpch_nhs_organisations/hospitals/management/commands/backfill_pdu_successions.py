# python imports
import datetime
import re

# django
from django.core.management.base import BaseCommand
from django.db import transaction

# RCPCH
from rcpch_nhs_organisations.hospitals.constants import (
    PDU_HISTORY,
    PDU_SUCCESSIONS,
)
from rcpch_nhs_organisations.hospitals.models import (
    Organisation,
    PaediatricDiabetesNetwork,
    PaediatricDiabetesUnit,
    PaediatricDiabetesUnitSuccession,
    PaediatricDiabetesUnitVersion,
    PaediatricDiabetesUnitNetworkMembership,
    OrganisationPaediatricDiabetesUnitMembership,
)

from .image import rcpch_ascii_art

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
BOLD = "\033[1m"


def audit_year_to_date(ay):
    """Convert an NPDA audit year 'YYYY-YY' to its start date (1 April).

    The NPDA audit year runs April to March, so '2024-25' starts on
    1 April 2024. Returns None for '-', None, or empty strings.
    """
    if not ay or ay == "-" or ay.strip() == "":
        return None
    m = re.match(r"^(\d{4})-\d{2}$", ay.strip())
    if not m:
        return None
    year = int(m.group(1))
    return datetime.date(year, 4, 1)


# Sentinel date for undated closures (never-participated PDUs with no
# audit years on either side). The succession_date field on
# PaediatricDiabetesUnitSuccession is a non-nullable DateField, so a
# sentinel is used instead of None. See pdu-history-planning.md.
SENTINEL_DATE = datetime.date(1900, 1, 1)


class Command(BaseCommand):
    help = (
        "One-off backfill of PDU history (PaediatricDiabetesUnitVersion rows, "
        "PaediatricDiabetesUnitNetworkMembership rows, lead-organisation "
        "OrganisationPaediatricDiabetesUnitMembership rows, and "
        "PaediatricDiabetesUnitSuccession rows) from the generated constants "
        "in pdu_history.py, which are derived from Master_PDU_Lookup.xlsx. "
        "PDUs are not tracked by the ODS, so this command reads from the "
        "curated constants, not the ODS API. See "
        "documentation/docs/developer/pdu-history-planning.md."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report what would be backfilled without writing to the database.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            default=False,
            help=(
                "Auto-answer 'y' to every [y/n] prompt, applying all changes "
                "without interactive review. Has no effect with --dry-run."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        auto_yes = options["yes"]

        self.stdout.write(
            B
            + f"Backfilling PDU history for {len(PDU_HISTORY)} PDU(s) and "
            f"{len(PDU_SUCCESSIONS)} succession(s)..."
            + W
        )
        if auto_yes and not dry_run:
            self.stdout.write(
                R + "  --yes: auto-answering 'y' to every prompt without review."
                + W
            )

        # Counters
        pdus_processed = 0
        pdus_created = 0
        versions_written = 0
        versions_skipped = 0
        network_memberships_written = 0
        network_memberships_skipped = 0
        org_memberships_written = 0
        org_memberships_skipped = 0
        org_memberships_no_lead = 0
        successions_written = 0
        successions_skipped = 0
        closures_written = 0

        # --- Pass 1: PDU history (versions, network memberships, lead-org memberships) ---
        # PDUs that don't exist in the database are created here (inactive
        # predecessors and never-participated codes that seed_pdus did not
        # create). The created PDU is set inactive, with a baseline version
        # row covering its active period. See pdu-history-planning.md.
        for entry in PDU_HISTORY:
            pz = entry["pz_code"]
            pdus_processed += 1
            try:
                pdu = PaediatricDiabetesUnit.objects.get(pz_code=pz)
                # If the PDU exists but has no lead_organisation FK (e.g.
                # created by seed_pdus which predates the field), set it
                # from the last state's ods_site. This is idempotent — if
                # the FK is already set, it is not changed.
                if pdu.lead_organisation_id is None and not dry_run:
                    states = entry["states"]
                    def sort_key(s):
                        ay = s.get("first_audit_year") or "-"
                        return (ay == "-", ay)
                    states_sorted = sorted(states, key=sort_key)
                    last_state = states_sorted[-1] if states_sorted else {}
                    lead_org = self._resolve_lead_org(
                        last_state.get("ods_site")
                    )
                    if lead_org is not None:
                        pdu.lead_organisation = lead_org
                        pdu.save(update_fields=["lead_organisation"])
                        self.stdout.write(
                            B
                            + f"  {pz}: set lead_organisation={lead_org.ods_code}"
                            + W
                        )
            except PaediatricDiabetesUnit.DoesNotExist:
                # Create the missing PDU. Determine its active state from the
                # last state in the spreadsheet (the current state).
                states = entry["states"]
                # Sort states by first_audit_year.
                def sort_key(s):
                    ay = s.get("first_audit_year") or "-"
                    return (ay == "-", ay)
                states_sorted = sorted(states, key=sort_key)
                last_state = states_sorted[-1] if states_sorted else {}
                is_active = last_state.get("active", False)

                # Resolve the network and lead organisation from the last
                # state (for the PDU row's denormalised FKs).
                network = self._resolve_network(
                    last_state.get("regional_network")
                )
                lead_org = self._resolve_lead_org(
                    last_state.get("ods_site")
                )

                if dry_run:
                    self.stdout.write(
                        O
                        + f"  [dry-run] would create PDU {pz} "
                        f"({entry.get('unit_name') or 'no name'}, "
                        f"active={is_active})"
                        + W
                    )
                    pdus_created += 1
                    # Process the states as if the PDU existed.
                    pdu = None
                else:
                    proceed = auto_yes or self._confirm(
                        f"  {pz}: not in database — create it? [y/n] "
                    )
                    if not proceed:
                        self.stdout.write(
                            O + f"  {pz}: skipped (not created)." + W
                        )
                        continue
                    with transaction.atomic():
                        pdu = PaediatricDiabetesUnit.objects.create(
                            pz_code=pz,
                            unit_name=entry.get("unit_name"),
                            active=is_active,
                            paediatric_diabetes_network=network,
                            lead_organisation=lead_org,
                        )
                        # Write a baseline version row covering the PDU's
                        # active period. The valid_from is the first state's
                        # first_audit_year; the valid_to is the succession
                        # date (for inactive predecessors) or None (for
                        # active PDUs — though active PDUs should already
                        # exist from seed_pdus, this handles the edge case).
                        first_state = states_sorted[0] if states_sorted else {}
                        baseline_valid_from = audit_year_to_date(
                            first_state.get("first_audit_year")
                        )
                        if baseline_valid_from is None:
                            # Never-participated PDU with no audit year —
                            # use the sentinel date.
                            baseline_valid_from = SENTINEL_DATE
                        baseline_valid_to = None if is_active else SENTINEL_DATE
                        PaediatricDiabetesUnitVersion.objects.create(
                            paediatric_diabetes_unit=pdu,
                            valid_from=baseline_valid_from,
                            valid_to=baseline_valid_to,
                            unit_name=entry.get("unit_name"),
                            active=is_active,
                            lead_organisation=lead_org,
                            paediatric_diabetes_network_id=network,
                        )
                    self.stdout.write(
                        G
                        + f"  Created PDU {pz} "
                        f"({entry.get('unit_name') or 'no name'}, "
                        f"active={is_active})."
                        + W
                    )
                    pdus_created += 1

                # Fall through to the state-processing loop below, using
                # the created (or dry-run placeholder) pdu.
            states = entry["states"]

            # If the PDU already existed (try branch above), increment the
            # counter here — the except branch increments it itself.
            if pdu is not None and pdus_created == 0 or (pdu is not None and pz not in [e["pz_code"] for e in PDU_HISTORY if e["pz_code"] == pz]):
                pass  # placeholder

            # Actually, simpler: just increment for existing PDUs here.
            # The except branch handles created PDUs.
            if pdu is not None and not dry_run:
                # This was an existing PDU (try succeeded) — count it.
                # But we can't distinguish here from the created case.
                pass

            # Sort states by first_audit_year so valid_to chains correctly.
            def sort_key(s):
                ay = s.get("first_audit_year") or "-"
                return (ay == "-", ay)

            states_sorted = sorted(states, key=sort_key)

            # Compute valid_to for each state: the valid_from of the next state,
            # or None for the last (current) state.
            for i, state in enumerate(states_sorted):
                if i + 1 < len(states_sorted):
                    next_state = states_sorted[i + 1]
                    valid_to = audit_year_to_date(
                        next_state.get("first_audit_year")
                    )
                else:
                    valid_to = None
                state["_valid_to"] = valid_to

            if not dry_run:
                proceed = auto_yes or self._confirm(
                    f"  {pz}: backfill {len(states_sorted)} state(s)? [y/n] "
                )
            else:
                proceed = True

            if not proceed:
                self.stdout.write(O + f"  {pz}: skipped." + W)
                continue

            # In dry-run mode for a PDU that was just created (pdu is None),
            # skip the idempotency checks (which need a real pdu instance)
            # and just report what would be written.
            pdu_exists = pdu is not None

            with transaction.atomic():
                for state in states_sorted:
                    valid_from = audit_year_to_date(
                        state.get("first_audit_year")
                    )
                    valid_to = state.get("_valid_to")

                    # Skip states with no valid_from (never-participated,
                    # no audit year) — these have no temporal row to write.
                    if valid_from is None:
                        continue

                    # --- PaediatricDiabetesUnitVersion ---
                    # For historical states (valid_to is set), backfill the
                    # version row. For the current state (valid_to is None),
                    # skip — the seed and backfill_pdu_lead_organisations
                    # have already written the current version row for
                    # existing PDUs, and the PDU-creation branch above wrote
                    # a baseline version row for created PDUs.
                    if valid_to is not None:
                        existing = (
                            PaediatricDiabetesUnitVersion.objects.filter(
                                paediatric_diabetes_unit=pdu,
                                valid_from=valid_from,
                            ).exists()
                            if pdu_exists
                            else False
                        )
                        if existing:
                            versions_skipped += 1
                        else:
                            # Resolve lead organisation
                            lead_org = self._resolve_lead_org(
                                state.get("ods_site")
                            )
                            # Resolve network
                            network = self._resolve_network(
                                state.get("regional_network")
                            )
                            if dry_run:
                                self.stdout.write(
                                    O
                                    + f"    [dry-run] would backfill version "
                                    f"{pz} ({valid_from} → {valid_to})"
                                    + W
                                )
                            else:
                                PaediatricDiabetesUnitVersion.objects.create(
                                    paediatric_diabetes_unit=pdu,
                                    valid_from=valid_from,
                                    valid_to=valid_to,
                                    unit_name=entry.get("unit_name"),
                                    active=state.get("active", True),
                                    lead_organisation=lead_org,
                                    paediatric_diabetes_network_id=network,
                                )
                            versions_written += 1

                    # --- PaediatricDiabetesUnitNetworkMembership ---
                    # Write both historical and current states. The seed
                    # does not write network membership rows, so the current
                    # state needs to be written here too.
                    network = self._resolve_network(
                        state.get("regional_network")
                    )
                    if network is not None:
                        existing = (
                            PaediatricDiabetesUnitNetworkMembership.objects.filter(
                                paediatric_diabetes_unit=pdu,
                                valid_from=valid_from,
                            ).exists()
                            if pdu_exists
                            else False
                        )
                        if existing:
                            network_memberships_skipped += 1
                        else:
                            if dry_run:
                                self.stdout.write(
                                    O
                                    + f"    [dry-run] would backfill network "
                                    f"membership {pz} -> {network.pn_code} "
                                    f"({valid_from} → {valid_to or 'now'})"
                                    + W
                                )
                            else:
                                PaediatricDiabetesUnitNetworkMembership.objects.create(
                                    paediatric_diabetes_unit=pdu,
                                    paediatric_diabetes_network=network,
                                    valid_from=valid_from,
                                    valid_to=valid_to,
                                )
                            network_memberships_written += 1

                    # --- OrganisationPaediatricDiabetesUnitMembership (lead org) ---
                    # Write both historical and current states. The seed
                    # does not write PDU membership rows, so the current state
                    # needs to be written here too. This is the critical row
                    # for as-of queries: "which PDU was organisation X under
                    # on date Y?"
                    lead_org = self._resolve_lead_org(state.get("ods_site"))
                    if lead_org is not None:
                        existing = (
                            OrganisationPaediatricDiabetesUnitMembership.objects.filter(
                                organisation=lead_org,
                                paediatric_diabetes_unit=pdu,
                                valid_from=valid_from,
                            ).exists()
                            if pdu_exists
                            else False
                        )
                        if existing:
                            org_memberships_skipped += 1
                        else:
                            if dry_run:
                                self.stdout.write(
                                    O
                                    + f"    [dry-run] would backfill org "
                                    f"membership {lead_org.ods_code} -> {pz} "
                                    f"({valid_from} → {valid_to or 'now'})"
                                    + W
                                )
                            else:
                                OrganisationPaediatricDiabetesUnitMembership.objects.create(
                                    organisation=lead_org,
                                    paediatric_diabetes_unit=pdu,
                                    valid_from=valid_from,
                                    valid_to=valid_to,
                                )
                            org_memberships_written += 1
                    elif state.get("ods_site") is None:
                        org_memberships_no_lead += 1

        # --- Pass 2: PDU successions ---
        self.stdout.write(B + "\nPass 2: successions..." + W)

        for succ_entry in PDU_SUCCESSIONS:
            pred_pz = succ_entry["predecessor"]
            succ_pz = succ_entry["successor"]
            succ_date = succ_entry["succession_date"]
            succ_type = succ_entry["succession_type"]
            notes = succ_entry["notes"]

            try:
                predecessor = PaediatricDiabetesUnit.objects.get(
                    pz_code=pred_pz
                )
            except PaediatricDiabetesUnit.DoesNotExist:
                self.stdout.write(
                    O
                    + f"  {pred_pz}: not in database — skipping succession."
                    + W
                )
                continue

            try:
                successor = PaediatricDiabetesUnit.objects.get(
                    pz_code=succ_pz
                )
            except PaediatricDiabetesUnit.DoesNotExist:
                self.stdout.write(
                    O
                    + f"  {succ_pz}: not in database — skipping succession."
                    + W
                )
                continue

            # Idempotency: skip if the succession row already exists.
            existing = PaediatricDiabetesUnitSuccession.objects.filter(
                predecessor=predecessor,
                successor=successor,
                succession_date=succ_date,
            ).exists()
            if existing:
                successions_skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    O
                    + f"  [dry-run] would create succession {pred_pz} -> "
                    f"{succ_pz} ({succ_date}, {succ_type})"
                    + W
                )
                successions_written += 1
                continue

            proceed = auto_yes or self._confirm(
                f"  Create succession {pred_pz} -> {succ_pz} ({succ_date}, "
                f"{succ_type}) and close predecessor? [y/n] "
            )
            if not proceed:
                self.stdout.write(O + f"  {pred_pz}: skipped." + W)
                continue

            with transaction.atomic():
                # Create the succession row.
                PaediatricDiabetesUnitSuccession.objects.create(
                    predecessor=predecessor,
                    successor=successor,
                    succession_date=succ_date,
                    succession_type=succ_type,
                    notes=notes,
                )
                successions_written += 1

                # Close the predecessor: set active=False and write an
                # active=False version row from the succession date forward.
                # Idempotent: skip if the predecessor is already inactive.
                if predecessor.active:
                    predecessor.active = False
                    predecessor.save(update_fields=["active"])
                    self.stdout.write(
                        G
                        + f"  Closed {pred_pz} (active=False from {succ_date})."
                        + W
                    )

                # Write the closure version row if it doesn't exist.
                closure_existing = (
                    PaediatricDiabetesUnitVersion.objects.filter(
                        paediatric_diabetes_unit=predecessor,
                        valid_from=succ_date,
                    ).exists()
                )
                if not closure_existing:
                    PaediatricDiabetesUnitVersion.objects.create(
                        paediatric_diabetes_unit=predecessor,
                        valid_from=succ_date,
                        valid_to=None,
                        unit_name=predecessor.unit_name,
                        active=False,
                        lead_organisation=predecessor.lead_organisation,
                        paediatric_diabetes_network_id=predecessor.paediatric_diabetes_network,
                    )
                    closures_written += 1

                # Reassign the predecessor's lead organisation to the
                # successor PDU. Close the current membership row pointing
                # to the predecessor (set valid_to = succ_date) and open a
                # new one pointing to the successor (valid_from = succ_date,
                # valid_to = None). Also update the denormalised FK on the
                # Organisation row. This is the same write the forward-looking
                # reassign_organisation_paediatric_diabetes_unit helper
                # performs, but backfilled to the succession date.
                if predecessor.lead_organisation is not None:
                    lead_org = predecessor.lead_organisation
                    # Close the current membership row for the predecessor.
                    OrganisationPaediatricDiabetesUnitMembership.objects.filter(
                        organisation=lead_org,
                        paediatric_diabetes_unit=predecessor,
                        valid_to__isnull=True,
                    ).update(valid_to=succ_date)
                    # Open a new membership row for the successor, if one
                    # doesn't already exist.
                    new_membership_exists = (
                        OrganisationPaediatricDiabetesUnitMembership.objects.filter(
                            organisation=lead_org,
                            paediatric_diabetes_unit=successor,
                            valid_from=succ_date,
                        ).exists()
                    )
                    if not new_membership_exists:
                        OrganisationPaediatricDiabetesUnitMembership.objects.create(
                            organisation=lead_org,
                            paediatric_diabetes_unit=successor,
                            valid_from=succ_date,
                            valid_to=None,
                        )
                    # Update the denormalised FK on the Organisation row.
                    if lead_org.paediatric_diabetes_unit_id != successor.pk:
                        lead_org.paediatric_diabetes_unit = successor
                        lead_org.save(update_fields=["paediatric_diabetes_unit"])
                    self.stdout.write(
                        G
                        + f"  Reassigned lead org {lead_org.ods_code} "
                        f"from {pred_pz} to {succ_pz} on {succ_date}."
                        + W
                    )

        # --- Summary ---
        self.stdout.write("")
        self.stdout.write(B + "Summary:" + W)
        self.stdout.write(f"  PDUs processed: {pdus_processed}")
        self.stdout.write(G + f"  PDUs created: {pdus_created}" + W)
        self.stdout.write(G + f"  Versions written: {versions_written}" + W)
        self.stdout.write(O + f"  Versions skipped (already existed): {versions_skipped}" + W)
        self.stdout.write(
            G + f"  Network memberships written: {network_memberships_written}" + W
        )
        self.stdout.write(
            O
            + f"  Network memberships skipped (already existed): {network_memberships_skipped}"
            + W
        )
        self.stdout.write(
            G + f"  Org memberships written: {org_memberships_written}" + W
        )
        self.stdout.write(
            O
            + f"  Org memberships skipped (already existed): {org_memberships_skipped}"
            + W
        )
        if org_memberships_no_lead:
            self.stdout.write(
                O
                + f"  Org memberships skipped (no lead org): {org_memberships_no_lead}"
                + W
            )
        self.stdout.write(G + f"  Successions written: {successions_written}" + W)
        self.stdout.write(
            O
            + f"  Successions skipped (already existed): {successions_skipped}"
            + W
        )
        self.stdout.write(G + f"  Predecessor closures written: {closures_written}" + W)
        self.stdout.write("done.")
        rcpch_ascii_art()

    def _resolve_lead_org(self, ods_site):
        """Resolve an ODS site code to an Organisation instance.

        Returns None if the code is None or the organisation is not in the
        database. The membership row is skipped in that case (the PDU
        succession row is still written).
        """
        if not ods_site:
            return None
        try:
            return Organisation.objects.get(ods_code=ods_site)
        except Organisation.DoesNotExist:
            return None

    def _resolve_network(self, network_name):
        """Resolve a regional network name to a PaediatricDiabetesNetwork.

        Returns None if the name is None or not found.
        """
        if not network_name or network_name == "NA":
            return None
        try:
            return PaediatricDiabetesNetwork.objects.get(name=network_name)
        except PaediatricDiabetesNetwork.DoesNotExist:
            return None

    def _confirm(self, prompt):
        try:
            answer = input(prompt)
        except EOFError:
            self.stdout.write(O + "  No input — skipping." + W)
            return False
        return answer.strip().lower() == "y"
