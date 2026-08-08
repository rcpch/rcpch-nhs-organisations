#!/usr/bin/env python
"""
Generator for rcpch_nhs_organisations/hospitals/constants/pdu_history.py.

Reads Master_PDU_Lookup.xlsx (the NPDA team's authoritative contact
database, committed to the constants folder) and emits a Python module
containing two lists:

  - PDU_HISTORY: per-PZ-code state timeline (versions, network memberships,
    lead-organisation memberships).
  - PDU_SUCCESSIONS: flat list of predecessor -> successor succession events.

The xlsx is binary and opaque in diffs; the generated Python dict is the
reviewable source of truth consumed by the `backfill_pdu_successions`
management command. The xlsx remains in the constants folder as provenance.

This script is a DEVELOPMENT TOOL. It is not run at import time and is not
a runtime dependency. Run it manually when the NPDA team updates the xlsx:

    python scripts/generate_pdu_history_constants.py

The output is committed to the repo. The diff in the generated file is the
review surface for xlsx changes.

Welsh lead organisations
------------------------
The spreadsheet records `ODS_site` as `NA` for Welsh PDUs (they are keyed
by Local Health Board). The existing PZ_CODES in paediatric_diabetes_units.py
already carry the Welsh lead organisation ODS codes for ACTIVE PDUs
(e.g. 7A3C7 for PZ001 Morriston). This script cross-references PZ_CODES to
fill those in.

For INACTIVE Welsh predecessors not in PZ_CODES (PZ052, PZ056, PZ185,
PZ188, PZ190), the script resolves the lead organisation by matching the
spreadsheet's `pdu_name` against Organisation.name in the database. This
requires Django to be set up (the script imports the models). If the script
is run outside a Django environment, the name lookup is skipped and a TODO
comment is inserted for the operator to fill in manually.

See documentation/docs/developer/pdu-history-planning.md for the full
design, including the audit-year-to-date conversion and the succession-date
rules.
"""

from __future__ import annotations

import datetime
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# This script lives at <repo>/scripts/generate_pdu_history_constants.py.
# The repo root is the parent of the scripts directory.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

XLSX_PATH = (
    REPO_ROOT
    / "rcpch_nhs_organisations"
    / "hospitals"
    / "constants"
    / "Master_PDU_Lookup.xlsx"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "rcpch_nhs_organisations"
    / "hospitals"
    / "constants"
    / "pdu_history.py"
)
PZ_CODES_PATH = (
    REPO_ROOT
    / "rcpch_nhs_organisations"
    / "hospitals"
    / "constants"
    / "paediatric_diabetes_units.py"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def audit_year_to_date(ay: str | None) -> datetime.date | None:
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


def parse_date(s: str | None) -> datetime.date | None:
    """Parse a 'YYYY-MM-DD' string into a date. Returns None if blank."""
    if not s:
        return None
    return datetime.date.fromisoformat(s)


def strip_pz_prefix(name: str | None) -> str | None:
    """Strip the 'PZxxx ' prefix from a pdu_name if present.

    The spreadsheet's pdu_name column is prefixed with the PZ code
    (e.g. 'PZ002 Norfolk and Norwich University Hospital'). The unit_name
    on the model should not carry this prefix.
    """
    if not name:
        return None
    name = name.strip()
    m = re.match(r"^PZ\d{3}\s+(.+)$", name)
    if m:
        return m.group(1).strip()
    return name or None


def load_xlsx_rows() -> tuple[list[str], list[dict]]:
    """Load the xlsx and return (header, rows) where each row is a dict."""
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    ws = wb.worksheets[0]  # single sheet: "Master Lookup Clean"
    all_rows = list(ws.iter_rows(values_only=True))
    header = [str(h) if h is not None else "" for h in all_rows[0]]
    rows = []
    for raw in all_rows[1:]:
        # pad short rows to header length
        padded = list(raw) + [None] * (len(header) - len(raw))
        row = {header[i]: padded[i] for i in range(len(header))}
        rows.append(row)
    return header, rows


def load_pz_codes() -> dict[str, str]:
    """Load PZ_CODES from paediatric_diabetes_units.py and return
    {npda_code: ods_code} for the lead organisation of each PDU."""
    # PZ_CODES is a list of dicts with 'npda_code' and 'ods_code' keys.
    # We exec the file to avoid importing Django.
    namespace: dict = {}
    with open(PZ_CODES_PATH) as f:
        exec(f.read(), namespace)
    pz_codes = namespace.get("PZ_CODES", [])
    return {entry["npda_code"]: entry["ods_code"] for entry in pz_codes}


def try_resolve_welsh_lead_by_name(pdu_name: str | None) -> str | None:
    """Attempt to resolve an inactive predecessor's lead organisation ODS code
    by matching the pdu_name against Organisation.name in the database.

    Returns the ODS code if a unique match is found, otherwise None.
    This requires Django to be set up; if it is not, returns None silently.
    """
    if not pdu_name:
        return None
    # Strip the PZ prefix to get the hospital name.
    hospital_name = strip_pz_prefix(pdu_name)
    if not hospital_name:
        return None
    try:
        import django

        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE", "rcpch_nhs_organisations.settings"
        )
        django.setup()
        from rcpch_nhs_organisations.hospitals.models import Organisation
    except Exception:
        # Not in a Django environment — skip the lookup.
        return None

    # Try a case-insensitive contains match on the first few words.
    # The spreadsheet names are human-readable (e.g. "Nevill Hall Hospital");
    # the DB names are uppercase (e.g. "NEVILL HALL CHILDRENS CENTRE").
    # Use the first significant word to avoid false positives.
    words = [w for w in hospital_name.split() if w.lower() not in (
        "the", "hospital", "general", "nhs", "trust", "foundation", "and",
        "of", "&", "royal", "university", "teaching",
    )]
    if not words:
        return None
    # Try progressively shorter fragments until we get a unique match.
    for n in range(min(len(words), 3), 0, -1):
        fragment = " ".join(words[:n])
        qs = Organisation.objects.filter(name__icontains=fragment)
        if qs.count() == 1:
            return qs.get().ods_code
    return None


# ---------------------------------------------------------------------------
# Manual lead-organisation overrides for inactive predecessors
# ---------------------------------------------------------------------------
# The spreadsheet has no ODS_site for inactive predecessor PDUs (the column
# is blank or NA). The name lookup above resolves most of them, but some are
# ambiguous (multiple organisations match the name fragment) or the lead org
# is not in the database. These overrides are the authoritative resolution,
# confirmed by inspecting the successor PDU's child organisations and the
# ODS record. See documentation/docs/developer/pdu-history-planning.md.
#
# PZ code -> lead organisation ODS code.
# Entries here take precedence over both PZ_CODES and the name lookup.
INACTIVE_PREDECESSOR_LEAD_OVERRIDES = {
    # Welsh inactive predecessors (resolved by name lookup, confirmed here):
    "PZ052": "7A623",  # Nevill Hall Hospital
    "PZ056": "7A2AA",  # West Wales General Hospital -> Glangwili Hospital
    "PZ185": "7A2AJ",  # Bronglais General Hospital
    "PZ188": "7A6AR",  # Royal Gwent Hospital
    "PZ190": "7A2BL",  # Withybush General Hospital
    # English inactive predecessors (resolved by name lookup, confirmed here):
    "PZ029": "RM321",  # Pennine Acute (trust-level PDU, lead = Trafford General)
    "PZ090": "RXF03",  # Pontefract General Infirmary (not RXF3C Paediatrics)
    "PZ095": "RXWAS",  # Shrewsbury and Telford
    "PZ116": "RX1RA",  # Nottingham University Hospitals
    "PZ134": "RM321",  # Trafford General Hospital (not Q3K9W Local Care Org)
    "PZ155": "RR801",  # Leeds Teaching Hospitals
    "PZ158": "RVR50",  # Epsom General Hospital
    "PZ166": "RWY02",  # Calderdale & Huddersfield
    "PZ175": "RVR07",  # Queen Mary's Hospital for Children, Carshalton
    "PZ184": "RXC02",  # Eastbourne District General Hospital
    "PZ195": "R1K02",  # Central Middlesex Hospital
    "PZ234": "R0A66",  # North Manchester General Hospital
    # Never-participated PDUs (allocated but never used; allocation
    # transferred to a successor). The lead org is the site the PZ code
    # would have identified, resolved by name lookup:
    "PZ066": "RDU52",  # Heatherwood Hospital
    "PZ071": "R1LCT",  # Broomfield Hospital
    "PZ123": "RCUEF",  # Sheffield Children's Hospital
    "PZ210": "RVWAE",  # University Hospital of North Tees
    # The following predecessors' lead organisations are NOT in the
    # database by name. They are resolved here by cross-referencing the
    # successor PDU's lead organisation or the successor trust's child
    # organisations, so that the as_of workflow (PDU -> lead org -> trust/LHB)
    # can still answer "which trust/LHB was this PDU under on date Y".
    # See documentation/docs/developer/pdu-history-planning.md.
    "PZ013": "RTXBU",  # Morecambe Bay (never participated) -> Furness General (child of RTX, successor PZ167's trust)
    "PZ043": "R0A03",  # Central Manchester (never participated) -> Manchester Children's Hospital (successor PZ136's lead)
    "PZ044": "R0A66",  # Royal Oldham -> North Manchester General (successor PZ234's lead, same trust R0A)
    "PZ046": "RTH08",  # Oxford Radcliffe -> John Radcliffe Hospital (successor PZ007's lead, same trust RTH)
    "PZ143": "RF4QH",  # King George -> Queen's Hospital (successor PZ232's lead, same trust RF4)
    "PZ148": "RHU03",  # Portsmouth -> Queen Alexandra Hospital (successor PZ238's lead, same trust RHU)
    "PZ208": "RTXBU",  # Morecambe Bay (never participated) -> Furness General (child of RTX, successor PZ167's trust)
}

# ---------------------------------------------------------------------------
# Name-source overrides (carried over from backfill_pdu_lead_organisations.py)
# ---------------------------------------------------------------------------

NAME_SOURCE_TRUST = "trust"
NAME_SOURCE_LOCAL_HEALTH_BOARD = "local_health_board"

# PDUs that identify by their parent trust, not a single lead site.
HARDCODED_NAME_SOURCE_TRUST = {
    "PZ024",  # East Kent Hospitals University NHS Foundation Trust
    "PZ120",  # Northumbria Healthcare NHS Foundation Trust
    "PZ167",  # UNIVERSITY HOSPITALS OF MORECAMBE BAY NHS FOUNDATION TRUST
    "PZ172",  # WEST HERTFORDSHIRE TEACHING HOSPITALS NHS TRUST
    "PZ186",  # CALDERDALE AND HUDDERSFIELD NHS FOUNDATION TRUST
    "PZ232",  # BARKING, HAVERING AND REDBRIDGE UNIVERSITY HOSPITALS NHS TRUST
    "PZ246",  # NORTHERN CARE ALLIANCE NHS FOUNDATION TRUST
    "PZ249",  # SOUTH TEES HOSPITALS NHS FOUNDATION TRUST
    "PZ250",  # SOUTH TYNESIDE AND SUNDERLAND NHS FOUNDATION TRUST
    "PZ253",  # MAIDSTONE AND TUNBRIDGE WELLS NHS TRUST
    "PZ254",  # NORTH WEST ANGLIA NHS FOUNDATION TRUST
}

HARDCODED_NAME_SOURCE_LOCAL_HEALTH_BOARD = {
    "PZ244",  # Welsh PDU — names itself by its local health board
}


def name_source_for(pz_code: str) -> str:
    if pz_code in HARDCODED_NAME_SOURCE_TRUST:
        return NAME_SOURCE_TRUST
    if pz_code in HARDCODED_NAME_SOURCE_LOCAL_HEALTH_BOARD:
        return NAME_SOURCE_LOCAL_HEALTH_BOARD
    return "lead_organisation"


# ---------------------------------------------------------------------------
# Core: build PDU_HISTORY and PDU_SUCCESSIONS
# ---------------------------------------------------------------------------


def build_history(header, rows, pz_codes_map):
    """Build the PDU_HISTORY and PDU_SUCCESSIONS structures."""

    # Group rows by PZ code, preserving spreadsheet order.
    pz_rows: dict[str, list[dict]] = defaultdict(list)
    pz_order: list[str] = []
    for row in rows:
        pz = row.get("PZ Code")
        if not pz:
            continue
        if pz not in pz_rows:
            pz_order.append(pz)
        pz_rows[pz].append(row)

    pdu_history = []
    pdu_successions = []

    for pz in pz_order:
        states_rows = pz_rows[pz]
        # Use the first row's pdu_name as the PDU's display name.
        first_row = states_rows[0]
        unit_name = strip_pz_prefix(first_row.get("pdu_name"))

        # Build the states list, sorted by first_audit_year.
        # Rows with first_audit_year == '-' (never participated) sort last.
        def sort_key(r):
            ay = r.get("First Audit Year") or "-"
            return (ay == "-", ay)

        states_rows_sorted = sorted(states_rows, key=sort_key)

        states = []
        for row in states_rows_sorted:
            first_ay = row.get("First Audit Year")
            last_ay = row.get("Last Audit Year")
            status = row.get("Status") or ""
            active = status == "Active"
            ods_site = row.get("ODS_site")
            if ods_site in ("NA", "", None):
                ods_site = None
            ods_trust = row.get("ODS_trust")
            if ods_trust in ("NA", "", None):
                ods_trust = None
            icb_lhb = row.get("ICB_LHB")
            if icb_lhb in ("NA", "", None):
                icb_lhb = None
            regional_network = row.get("regionalnetwork")
            if regional_network in ("NA", "", None):
                regional_network = None
            nhs_england_region = row.get("nhseregion")
            if nhs_england_region in ("NA", "", None):
                nhs_england_region = None
            country = row.get("country")
            if country in ("NA", "", None):
                country = None

            states.append(
                {
                    "first_audit_year": first_ay,
                    "last_audit_year": last_ay if last_ay else None,
                    "active": active,
                    "ods_site": ods_site,
                    "ods_trust": ods_trust,
                    "icb_lhb": icb_lhb,
                    "regional_network": regional_network,
                    "nhs_england_region": nhs_england_region,
                    "country": country,
                    "reason_for_change": row.get("Reason for Change") or None,
                }
            )

        # Resolve the lead organisation ODS code for each state.
        # 1. If the state has an ods_site, use it.
        # 2. Else, check the manual overrides (authoritative for inactive
        #    predecessors whose lead org is ambiguous or not in PZ_CODES).
        # 3. Else (Welsh/active PDU), look up PZ_CODES.
        # 4. Else (inactive predecessor with a name), try name lookup
        #    against the database.
        # 5. Else (Never participated, no name), leave as None — no lead to
        #    resolve. No TODO flag.
        welsh_lead_todo = False
        for state in states:
            if state["ods_site"]:
                continue
            # No ods_site in the spreadsheet. Check overrides first.
            lead = INACTIVE_PREDECESSOR_LEAD_OVERRIDES.get(pz)
            if lead:
                state["ods_site"] = lead
                continue
            # Not in overrides. Try PZ_CODES (active PDUs).
            lead = pz_codes_map.get(pz)
            if lead:
                state["ods_site"] = lead
                continue
            # Not in PZ_CODES. If this is a Never-participated PDU with no
            # name, there is nothing to resolve — skip silently.
            is_never_participated = all(
                (s.get("active") is False and not s.get("first_audit_year"))
                or s.get("first_audit_year") == "-"
                for s in states
            )
            if is_never_participated and not unit_name:
                continue
            # Inactive predecessor with a name — try name lookup.
            lead = try_resolve_welsh_lead_by_name(unit_name)
            if lead:
                state["ods_site"] = lead
            elif unit_name:
                # Has a name but couldn't resolve — flag for manual review.
                welsh_lead_todo = True

        # Collect replaced_by and notes from any row that has them.
        replaced_by = None
        notes = None
        for row in states_rows:
            if row.get("Replaced By"):
                replaced_by = row["Replaced By"]
            if row.get("Notes"):
                notes = row["Notes"]

        pdu_history.append(
            {
                "pz_code": pz,
                "unit_name": unit_name,
                "states": states,
                "replaced_by": replaced_by,
                "notes": notes,
                "_welsh_lead_todo": welsh_lead_todo,
            }
        )

    # Build PDU_SUCCESSIONS from the replaced_by values.
    # We need the successor's first audit year to compute the succession date.
    # Build a lookup: pz -> sorted states (for first_audit_year).
    pz_states = {entry["pz_code"]: entry["states"] for entry in pdu_history}

    for entry in pdu_history:
        pz = entry["pz_code"]
        replaced_by = entry["replaced_by"]
        if not replaced_by:
            continue
        successors = [s.strip() for s in replaced_by.split(",")]
        # Find the predecessor's last audit year.
        pred_states = pz_states.get(pz, [])
        pred_last_ay = None
        for s in pred_states:
            if s["last_audit_year"]:
                pred_last_ay = s["last_audit_year"]
        # Determine the reason for change (Merged / Split / closure).
        # A "Never participated" PDU (Status == Never participated, no audit
        # years) is always a closure with successor set, regardless of the
        # reason_for_change value on the row — the PZ code was allocated but
        # never used, and its allocation transferred to the successor.
        is_never_participated = all(
            (s.get("active") is False and (not s.get("first_audit_year") or s.get("first_audit_year") == "-"))
            for s in pred_states
        )
        if is_never_participated:
            reason = "closure"
        else:
            reason = None
            for s in pred_states:
                if s["reason_for_change"] in ("Merged", "Split"):
                    reason = s["reason_for_change"]
                    break
            if reason is None:
                # Inactive PDU with a replaced_by but no explicit reason —
                # treat as a merger (the PDU was absorbed into the successor).
                reason = "merger"

        for succ_pz in successors:
            # Find the successor's first audit year.
            succ_states = pz_states.get(succ_pz, [])
            succ_first_ay = None
            for s in succ_states:
                if s["first_audit_year"] and s["first_audit_year"] != "-":
                    succ_first_ay = s["first_audit_year"]
                    break

            # Apply the succession-date rule.
            if reason == "closure" and not pred_last_ay and not succ_first_ay:
                # Never participated, no dates on either side. Use sentinel.
                succession_date = "1900-01-01"
            else:
                # Normal case: succession_date = audit_year_to_date(succ_first_ay)
                # if the successor's first audit year is after the predecessor's
                # last. Otherwise (successor predates predecessor, or same year,
                # or gap), use the start of the audit year after the
                # predecessor's last.
                if succ_first_ay and pred_last_ay:
                    succ_start = audit_year_to_date(succ_first_ay)
                    pred_end_next = audit_year_to_date(
                        _next_audit_year(pred_last_ay)
                    )
                    if succ_start is not None and pred_end_next is not None and succ_start >= pred_end_next:
                        # Successor started after predecessor ended — use
                        # successor's start date.
                        succession_date = succ_start.isoformat()
                    else:
                        # Successor predates predecessor, or same year — use
                        # the start of the audit year after the predecessor's
                        # last.
                        succession_date = pred_end_next.isoformat() if pred_end_next else "1900-01-01"
                elif succ_first_ay:
                    d = audit_year_to_date(succ_first_ay)
                    succession_date = d.isoformat() if d else "1900-01-01"
                elif pred_last_ay:
                    d = audit_year_to_date(_next_audit_year(pred_last_ay))
                    succession_date = d.isoformat() if d else "1900-01-01"
                else:
                    succession_date = "1900-01-01"

            # Determine the succession type from the reason.
            if reason == "closure":
                succession_type = "closure"
                note_text = (
                    f"Allocated but never participated; allocation "
                    f"transferred to {succ_pz}."
                )
            elif reason == "Split":
                succession_type = "split"
                note_text = _succession_note(pz, succ_pz, entry)
            else:
                succession_type = "merger"
                note_text = _succession_note(pz, succ_pz, entry)

            pdu_successions.append(
                {
                    "predecessor": pz,
                    "successor": succ_pz,
                    "succession_date": succession_date,
                    "succession_type": succession_type,
                    "notes": note_text,
                }
            )

    return pdu_history, pdu_successions


def _next_audit_year(ay: str) -> str:
    """Given '2024-25', return '2025-26'."""
    m = re.match(r"^(\d{4})-(\d{2})$", ay)
    if not m:
        return ay
    start = int(m.group(1))
    next_start = start + 1
    next_end = (next_start + 1) % 100
    return f"{next_start}-{next_end:02d}"


def _succession_note(pred_pz, succ_pz, pred_entry):
    """Build a human-readable note for a succession row."""
    pred_name = pred_entry.get("unit_name") or pred_pz
    return f"{pred_name} ({pred_pz}) -> {succ_pz}."


# ---------------------------------------------------------------------------
# Emit the Python module
# ---------------------------------------------------------------------------


def format_date_literal(s: str) -> str:
    """Format a date string 'YYYY-MM-DD' as a datetime.date() literal."""
    d = parse_date(s)
    if d is None:
        return "datetime.date(1900, 1, 1)  # sentinel — undated"
    return f"datetime.date({d.year}, {d.month}, {d.day})"


def emit_module(pdu_history, pdu_successions) -> str:
    """Emit the Python source for pdu_history.py."""
    lines = []
    lines.append('"""')
    lines.append(
        "Generated PDU history constants for the backfill_pdu_successions"
    )
    lines.append("management command.")
    lines.append("")
    lines.append(
        "This file is GENERATED by scripts/generate_pdu_history_constants.py"
    )
    lines.append(
        "from Master_PDU_Lookup.xlsx. Do not edit by hand — re-run the"
    )
    lines.append(
        "generator when the xlsx is updated. The diff in this file is the"
    )
    lines.append("review surface for xlsx changes.")
    lines.append("")
    lines.append(
        "See documentation/docs/developer/pdu-history-planning.md for the"
    )
    lines.append("full design, including the audit-year-to-date conversion")
    lines.append("and the succession-date rules.")
    lines.append('"""')
    lines.append("")
    lines.append("import datetime")
    lines.append("")
    lines.append("# Audit years are NPDA audit years (April to March).")
    lines.append(
        "# '2024-25' means the audit year starting 1 April 2024."
    )
    lines.append(
        "# The backfill command converts these to dates via the same"
    )
    lines.append(
        "# audit_year_to_date() helper used by the generator."
    )
    lines.append("")
    lines.append("PDU_HISTORY = [")
    for entry in pdu_history:
        lines.append("    {")
        lines.append(f'        "pz_code": {repr(entry["pz_code"])},')
        lines.append(f'        "unit_name": {repr(entry["unit_name"])},')
        lines.append('        "states": [')
        for state in entry["states"]:
            lines.append("            {")
            lines.append(
                f'                "first_audit_year": {repr(state["first_audit_year"])},'
            )
            lines.append(
                f'                "last_audit_year": {repr(state["last_audit_year"])},'
            )
            lines.append(f'                "active": {repr(state["active"])},')
            lines.append(
                f'                "ods_site": {repr(state["ods_site"])},'
            )
            lines.append(
                f'                "ods_trust": {repr(state["ods_trust"])},'
            )
            lines.append(
                f'                "icb_lhb": {repr(state["icb_lhb"])},'
            )
            lines.append(
                f'                "regional_network": {repr(state["regional_network"])},'
            )
            lines.append(
                f'                "nhs_england_region": {repr(state["nhs_england_region"])},'
            )
            lines.append(f'                "country": {repr(state["country"])},')
            lines.append(
                f'                "reason_for_change": {repr(state["reason_for_change"])},'
            )
            lines.append("            },")
        lines.append("        ],")
        lines.append(f'        "replaced_by": {repr(entry["replaced_by"])},')
        lines.append(f'        "notes": {repr(entry["notes"])},')
        if entry.get("_welsh_lead_todo"):
            lines.append(
                '        # TODO: Welsh lead organisation not resolved —'
            )
            lines.append(
                '        # confirm manually (see pdu-history-planning.md).'
            )
        lines.append("    },")
    lines.append("]")
    lines.append("")
    lines.append("PDU_SUCCESSIONS = [")
    for succ in pdu_successions:
        lines.append("    {")
        lines.append(f'        "predecessor": {repr(succ["predecessor"])},')
        lines.append(f'        "successor": {repr(succ["successor"])},')
        # Format the succession_date as a datetime.date literal.
        sd = succ["succession_date"]
        if sd == "1900-01-01":
            lines.append(
                '        "succession_date": datetime.date(1900, 1, 1),  # sentinel — undated (never participated)'
            )
        else:
            lines.append(
                f'        "succession_date": {format_date_literal(sd)},'
            )
        lines.append(
            f'        "succession_type": {repr(succ["succession_type"])},'
        )
        lines.append(f'        "notes": {repr(succ["notes"])},')
        lines.append("    },")
    lines.append("]")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if not XLSX_PATH.exists():
        print(f"ERROR: xlsx not found at {XLSX_PATH}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {XLSX_PATH}...")
    header, rows = load_xlsx_rows()
    print(f"  {len(rows)} data rows, {len(header)} columns.")

    print(f"Loading PZ_CODES from {PZ_CODES_PATH}...")
    pz_codes_map = load_pz_codes()
    print(f"  {len(pz_codes_map)} PZ codes with lead organisation ODS codes.")

    print("Building PDU_HISTORY and PDU_SUCCESSIONS...")
    pdu_history, pdu_successions = build_history(header, rows, pz_codes_map)
    print(f"  {len(pdu_history)} PDUs, {len(pdu_successions)} successions.")

    # Report any unresolved Welsh leads.
    todos = [e for e in pdu_history if e.get("_welsh_lead_todo")]
    if todos:
        print()
        print("WARNING: unresolved Welsh lead organisations:")
        for e in todos:
            print(f"  {e['pz_code']} ({e['unit_name']})")
        print(
            "  These are left as None in the dict with a TODO comment."
        )
        print(
            "  Run the generator inside the Django container to resolve by name lookup."
        )

    print(f"Writing {OUTPUT_PATH}...")
    source = emit_module(pdu_history, pdu_successions)
    with open(OUTPUT_PATH, "w") as f:
        f.write(source)
    print("done.")


if __name__ == "__main__":
    main()
