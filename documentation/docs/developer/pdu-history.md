---
title: PDU history backfill
author: Dr Simon Chapman
---

# PDU history backfill

This document describes how the historical relationships between Paediatric
Diabetes Units (PDUs), their lead organisations, parent trusts, and
Integrated Care Boards / Local Health Boards are recovered from the master
PDU lookup spreadsheet and written into the temporal layer.

It should be read alongside:

- [`temporal-history.md`](temporal-history.md) — the schema (Layer 1 version
  tables, Layer 2 membership tables, Layer 3 succession tables).
- [`merger-handling.md`](merger-handling.md) — the PDU merger types and the
  forward-looking admin workflow (the *Acquire another…* and *Merge into a
  new…* wizards).
- [`backfill.md`](backfill.md) — the ODS-driven trust backfill, which this
  feature mirrors for PDUs. PDUs are **not** tracked by the ODS, so there is
  no API to call; the spreadsheet is the source of truth.

## Background and motivation

The temporal layer records PDU state from installation day forward. Before
it was installed, PDU affiliations were overwritten in place on the
`Organisation` row, and PDU mergers were recorded only as hardcoded special
cases in the `PaediatricDiabetesUnit.organisations` property (now removed)
and in the `active` flag on the `PaediatricDiabetesUnit` row.

The audit (NPDA) reports longitudinal outcomes against the PDU geography
that was in force at the time the data was collected. PDUs merge, split,
and are reassigned between ICBs over time, so an as-of query — "which PDU
was organisation X under on date Y, and what was that PDU's lead
organisation, parent trust, and ICB?" — must walk the membership and
succession tables, not read a single current-state FK.

Unlike trusts, PDUs have **no ODS source of truth**. The ODS does not track
PZ codes at all. The historical record is maintained manually by the NPDA
team in a master spreadsheet, `Master_PDU_Lookup.xlsx`, which has been
committed to the constants folder. This document describes how that
spreadsheet is turned into temporal rows.

## The source file

`rcpch_nhs_organisations/hospitals/constants/Master_PDU_Lookup.xlsx`

- **Sheet:** `Master Lookup Clean` (single sheet)
- **Rows:** 298 data rows + 1 header row
- **Source provenance:** the workbook's `absPath` metadata points at the
  NPDA SharePoint (`rcpch.sharepoint.com/teams/national-paediatric-diabetes-audit/.../Contact database/`).
  It is the NPDA team's authoritative contact database, exported to xlsx.

### Columns

| # | Column | Meaning |
|---|---|---|
| 1 | `pdu_last` | A grouping index — rows sharing the same value describe the same PDU across successive states (e.g. an "Old ICB" row and a "New ICB" row for the same PZ code). Not a stable identifier; the PZ code is. |
| 2 | `PZ Code` | The PDU's PZ code. The primary key. |
| 3 | `pdu_name` | Display name, prefixed with the PZ code (e.g. `PZ002 Norfolk and Norwich University Hospital`). |
| 4 | `ICB_LHB` | The ICB (England) or Local Health Board (Wales) the PDU sat under, prefixed with the country (e.g. `England - NHS Norfolk and Waveney Integrated Care Board`). `NA` for non-participating / Welsh rows where the LHB is in column 7's country only. |
| 5 | `regionalnetwork` | The paediatric diabetes regional network (e.g. `East of England`, `Wales`). This is the **network name**, not the PN code — it maps to `PaediatricDiabetesNetwork` via the network's name. |
| 6 | `nhseregion` | The NHS England region (England only). `Wales` for Welsh rows. |
| 7 | `country` | `England`, `Wales`, `Jersey`, `Isle of Man`. `None` for "Never participated" rows that carry no geography. |
| 8 | `ODS_site` | The ODS code of the lead organisation (site). `NA` or blank for Welsh PDUs keyed by LHB, and for "Never participated" rows. |
| 9 | `ODS_trust` | The ODS code of the parent trust (England) or LHB (Wales). `NA` or blank as above. |
| 10 | `Status` | `Active`, `Inactive`, or `Never participated`. |
| 11 | `First Audit Year` | The NPDA audit year this state began, in `YYYY-YY` form (e.g. `2024-25`). The NPDA audit year runs April–March, so `2024-25` starts on 1 April 2024. `-` for "Never participated". |
| 12 | `Last Audit Year` | The last audit year this state was in force. Blank (open) for the current state of an active PDU. |
| 13 | `Reason for Change` | Why this state ended: `Merged`, `Split`, `Old ICB` (an ICB reorganisation), `New ICB` (the successor state after an ICB reorg), or blank. |
| 14 | `Replaced By` | The successor PZ code(s), comma-separated. Present when a PDU merged or split. Blank for ICB reorganisations (the PZ code is unchanged; only the ICB membership moves). |
| 15 | `Notes` | Free-text provenance notes from the NPDA team. |

### Audit-year → date convention

The spreadsheet records time in NPDA audit years (`YYYY-YY`), not calendar
dates. The NPDA audit year runs **1 April → 31 March**, so `2024-25` starts
on **1 April 2024**. The conversion rule used throughout the backfill is:

```
audit_year_to_date("2024-25") → date(2024, 4, 1)
```

This is the `valid_from` for the state described by that row. The
`valid_to` is the `valid_from` of the next row for the same PZ code (i.e.
the `First Audit Year` of the successor state), or `None` if this is the
current (open) state.

For a merger/split, the **succession date** is the first day of the audit
year of the successor PDU's first row. PDUs do not currently carry
succession dates in the live system — only organisations and trusts do.
The first day of the new audit year is the correct `succession_date` for a
PDU acquisition/merger/closure. Where `merger-handling.md` quotes an
operational date (e.g. "January 2026" for PZ216+PZ125→PZ253), that is the
operational rename date; the temporal row uses the audit-year boundary (1
April 2025) and the operational date is recorded in `notes` for provenance.

### What the spreadsheet contains

- **256 distinct PZ codes.**
- **172 active states**, **73 inactive states**, **53 "Never participated"** rows.
- **42 PZ codes have multiple rows** — these are state changes over time.
  Of these:
  - **40 are ICB reorganisations** (an "Old ICB" row ending 2025-26 and a
    "New ICB" row starting 2026-27, reflecting the 2026 NHS England ICB
    reorganisation). The PZ code is unchanged; only the ICB membership
    moves. These are **not** successions.
  - **2 are splits** (PZ003 → PZ251 + PZ252; PZ206 → PZ246 + PZ247).
- **33 rows carry a `Replaced By` value** — these are the PDU successions
  (mergers and splits). Of these:
  - **25 are mergers** (one predecessor → one successor).
  - **2 are splits** (one predecessor → two successors).
  - **6 are "Never participated"** rows with a `Replaced By` — these are
    PZ codes that were allocated but never used, and their allocation was
    later transferred to another PZ code. These are recorded as closures
    with a successor (see [Never-participated codes](#never-participated-codes)).

### The full succession list

This is the complete set of PDU successions recoverable from the
spreadsheet — **35 succession rows** (some predecessors split into two
successors, giving 33 `Replaced By` entries but 35 predecessor → successor
pairs counting splits as two rows).

| Predecessor | Last audit year | Successor(s) | First audit year | Type | Notes |
|---|---|---|---|---|---|
| PZ003 | 2024-25 | PZ251, PZ252 | 2025-26 | split | Pinderfields General Hospital split into PZ251 (Pinderfields) + PZ252 (Pontefract). |
| PZ013 | — | PZ167 | 2004-05 | closure | Never participated; allocation transferred to PZ167. |
| PZ027 | 2023-24 | PZ249 | 2024-25 | merger | Friarage Hospital → South Tees (PZ249). |
| PZ043 | — | PZ136 | 2005-06 | closure | Never participated; Central Manchester allocation → PZ136. |
| PZ044 | 2010-11 | PZ234 | 2010-11 | merger | Royal Oldham → Barking, Havering and Redbridge (PZ234). Same audit year — succession date 2010-04-01. |
| PZ046 | 2011-12 | PZ007 | 2004-05 | merger | Oxford Radcliffe → Buckinghamshire (PZ007). Successor predates predecessor — PZ007 was already active; PZ046 was folded into it. Succession date 2012-04-01. |
| PZ052 | 2019-20 | PZ245 | 2020-21 | merger | Nevill Hall → Aneurin Bevan (PZ245, Welsh). |
| PZ056 | 2018-19 | PZ244 | 2019-20 | merger | West Wales General → Hywel Dda (PZ244, Welsh). |
| PZ066 | — | PZ021 | 2009-10 | closure | Never participated; Heatherwood & Wexham allocation → PZ021. |
| PZ080 | 2024-25 | PZ250 | 2025-26 | merger | Sunderland Royal → South Tyneside and Sunderland (PZ250). |
| PZ086 | 2025-26 | PZ254 | 2026-27 | merger | Hinchingbrooke → North West Anglia (PZ254). |
| PZ095 | 2009-10 | PZ094 | 2006-07 | merger | Shrewsbury and Telford → PZ094. Successor predates predecessor. Succession date 2010-04-01. |
| PZ116 | 2003-04 | PZ042 | 2005-06 | merger | Nottingham University Hospitals → Nottingham Children's Hospital (PZ042). Gap of two audit years between predecessor end and successor start — succession date 2004-04-01. |
| PZ123 | — | PZ219 | 2005-06 | closure | Never participated; Sheffield Children's allocation → PZ219. |
| PZ125 | 2024-25 | PZ253 | 2025-26 | merger | Maidstone Hospital → Maidstone and Tunbridge Wells (PZ253). |
| PZ131 | 2025-26 | PZ254 | 2026-27 | merger | Peterborough City → North West Anglia (PZ254). |
| PZ133 | 2023-24 | PZ249 | 2024-25 | merger | James Cook University Hospital → South Tees (PZ249). |
| PZ141 | 2024-25 | PZ250 | 2025-26 | merger | South Tyneside District → South Tyneside and Sunderland (PZ250). |
| PZ143 | 2014-15 | PZ232 | 2005-06 | merger | King George → Barking, Havering and Redbridge (PZ232). Successor predates predecessor. Succession date 2015-04-01. |
| PZ148 | 2010-11 | PZ238 | 2011-12 | merger | Portsmouth Hospitals → PZ238. |
| PZ155 | 2009-10 | PZ101 | 2003-04 | merger | Leeds Teaching Hospitals → PZ101. Successor predates predecessor. Succession date 2010-04-01. |
| PZ158 | 2014-15 | PZ050 | 2005-06 | merger | Epsom General → PZ050. Successor predates predecessor. Succession date 2015-04-01. |
| PZ166 | 2012-13 | PZ186 | 2004-05 | merger | Calderdale & Huddersfield → PZ186. Successor predates predecessor. Succession date 2013-04-01. |
| PZ175 | 2019-20 | PZ151 | 2009-10 | merger | Queen Mary's → PZ151. Successor predates predecessor. Succession date 2020-04-01. |
| PZ184 | 2013-14 | PZ230 | 2009-10 | merger | Eastbourne District General → Conquest Hospital (PZ230). Successor predates predecessor. Succession date 2014-04-01. |
| PZ185 | 2018-19 | PZ244 | 2019-20 | merger | Bronglais General → Hywel Dda (PZ244, Welsh). |
| PZ188 | 2019-20 | PZ245 | 2020-21 | merger | Royal Gwent → Aneurin Bevan (PZ245, Welsh). |
| PZ190 | 2018-19 | PZ244 | 2019-20 | merger | Withybush General → Hywel Dda (PZ244, Welsh). |
| PZ195 | 2012-13 | PZ089 | 2006-07 | merger | Central Middlesex → PZ089. Successor predates predecessor. Succession date 2013-04-01. |
| PZ206 | 2021-22 | PZ246, PZ247 | 2021-22 | split | Pennine Acute split into PZ246 (Northern Care Alliance, Rochdale/Bury/Oldham) + PZ247 (North Manchester General). Same audit year — succession date 2021-04-01. |
| PZ208 | — | PZ167 | 2004-05 | closure | Never participated; Morecambe Bay allocation → PZ167. |
| PZ210 | — | PZ163 | 2003-04 | closure | Never participated; North Tees allocation → PZ163. |
| PZ216 | 2024-25 | PZ253 | 2025-26 | merger | Tunbridge Wells Hospital → Maidstone and Tunbridge Wells (PZ253). |

### Succession-date rule

Given a predecessor row with `Last Audit Year = L` and a successor row with
`First Audit Year = F`:

1. **Normal case (`F` is the audit year after `L`):**
   `succession_date = audit_year_to_date(F)` — i.e. the start of the
   successor's first audit year.

2. **Successor predates predecessor (`F` is earlier than `L`, or the
   successor was already active):** the predecessor was folded into an
   existing PDU. `succession_date = audit_year_to_date(L) + 1 year` — i.e.
   the start of the audit year *after* the predecessor's last. Example:
   PZ046 last `2011-12` → succession date `2012-04-01` (PZ007 was already
   active from `2004-05`).

3. **Same audit year (`F == L`):** `succession_date =
   audit_year_to_date(F)`. Example: PZ044 → PZ234, both `2010-11` →
   `2010-04-01`.

4. **Gap between predecessor end and successor start:** use the start of
   the audit year after the predecessor's last. Example: PZ116 last
   `2003-04`, PZ042 first `2005-06` → succession date `2004-04-01`.

5. **Never participated (no audit years):** `succession_date` is the
   successor's first audit year (when the allocation transferred). If
   neither predecessor nor successor has an audit year, a sentinel date
   (`1900-01-01`) is used. See [Never-participated codes](#never-participated-codes).

### Never-participated codes

Six PZ codes were allocated but never used in the audit, and their
allocation was later transferred to another PZ code:

| PZ code | Name | Replaced by | Reason |
|---|---|---|---|
| PZ013 | University Hospitals of Morecambe Bay NHS Trust | PZ167 | allocation transferred |
| PZ043 | Central Manchester University Hospitals NHS Foundation Trust | PZ136 | merged (allocation) |
| PZ066 | Heatherwood & Wexham Park Hospitals Trust | PZ021 | allocation transferred |
| PZ123 | Sheffield Children's NHS Foundation Trust | PZ219 | allocation transferred |
| PZ208 | University Hospitals of Morecambe Bay NHS Trust | PZ167 | allocation transferred |
| PZ210 | North Tees and Hartlepool NHS Trust | PZ163 | merged (allocation) |

These are recorded as `PaediatricDiabetesUnit` rows with `active=False`
and a `PaediatricDiabetesUnitSuccession` row with
`succession_type="closure"` and `successor` set (not `None`, because
there *is* a successor — the allocation moved). This mirrors the trust
closure-with-successor pattern. The `succession_date` is the start of
the successor PDU's first audit year where the spreadsheet exposes one;
for codes where neither predecessor nor successor has an audit year, a
sentinel date (`1900-01-01`) is used. The `notes` field records "Allocated
but never participated; allocation transferred to PZxxx."

## Design

### Source of truth: xlsx or Python dict?

The xlsx is the NPDA team's living document — they edit it in SharePoint
as PDU structures change. But the backfill command needs a deterministic,
version-controlled source. The xlsx is binary and opaque in diffs; a
Python dict is reviewable in a PR.

The approach mirrors the existing `known_acquisitions.py` pattern: a
curated Python list of dicts, with a docstring recording the provenance,
consumed by a management command. The xlsx remains in the constants
folder as the **source of provenance** (so a reviewer can open it), but
the **source of truth** for the code is the generated dict.

A generator script (`scripts/generate_pdu_history_constants.py`) reads the
xlsx and emits `pdu_history.py`. This is run once to produce the initial
dict, and re-run manually when the NPDA team updates the xlsx (the diff
in the generated file is the review surface). The generator is not run at
import time — the dict is committed.

The generator cross-references the existing `PZ_CODES` in
`paediatric_diabetes_units.py` to fill in the **Welsh lead organisation
ODS codes**, which the spreadsheet records as `NA` for `ODS_site`. The
existing constants already carry these (e.g. `7A3C7` for PZ001
Morriston, `7A1A1` for PZ011 Glan Clwyd, `7A6G9` for PZ245 The Grange).
For inactive Welsh predecessors not in `PZ_CODES` (PZ052, PZ056, PZ185,
PZ188, PZ190), the generator resolves the lead organisation by matching
the spreadsheet's `pdu_name` against `Organisation.name` in the database
at generation time, and records the ODS code in the dict. For PZ056
("West Wales General Hospital"), the lead is Glangwili Hospital
(`7A2AA`) — the site was renamed West Wales General → Glangwili General
in 2010, before the audit window, so no organisation-level rename row is
backfilled; the PDU succession (PZ056 → PZ244) is still recorded.

For inactive English predecessors whose lead organisations are not in the
database by name, the generator cross-references the successor PDU's lead
organisation or the successor trust's child organisations, so that the
`as_of` workflow (PDU → lead org → trust/LHB) can still answer "which
trust/LHB was this PDU under on date Y". These resolutions are recorded in
the `INACTIVE_PREDECESSOR_LEAD_OVERRIDES` dict in the generator script,
confirmed by inspecting the database.

### The constants file

`rcpch_nhs_organisations/hospitals/constants/pdu_history.py`

Two top-level structures:

```python
PDU_HISTORY = [
    {
        "pz_code": "PZ002",
        "unit_name": "Norfolk and Norwich University Hospital",
        "states": [
            {
                "first_audit_year": "2004-05",
                "last_audit_year": "2025-26",
                "active": False,
                "ods_site": "RM102",
                "ods_trust": "RM1",
                "icb_lhb": "England - NHS Norfolk and Waveney Integrated Care Board",
                "regional_network": "East of England",
                "nhs_england_region": "East of England",
                "country": "England",
                "reason_for_change": "Old ICB",
            },
            {
                "first_audit_year": "2026-27",
                "last_audit_year": None,
                "active": True,
                "ods_site": "RM102",
                "ods_trust": "RM1",
                "icb_lhb": "England - NHS Norfolk and Suffolk Integrated Care Board",
                "regional_network": "East of England",
                "nhs_england_region": "East of England",
                "country": "England",
                "reason_for_change": "New ICB",
            },
        ],
        "replaced_by": None,
        "notes": None,
    },
    # ...
]

PDU_SUCCESSIONS = [
    {
        "predecessor": "PZ216",
        "successor": "PZ253",
        "succession_date": datetime.date(2025, 4, 1),
        "succession_type": "merger",
        "notes": "Tunbridge Wells Hospital (PZ216) -> PZ253.",
    },
    # ... one entry per predecessor → successor pair (splits produce two entries)
]
```

`PDU_HISTORY` is the per-PDU state timeline (one entry per PZ code, with a
list of states). `PDU_SUCCESSIONS` is the flat list of succession events
(predecessor → successor), derived from the `Replaced By` column. The two
are kept separate because they map to different temporal layers
(membership/version vs succession).

### What gets written into the temporal layer

The `backfill_pdu_successions` command writes the following rows.

#### Pass 1 — PDU history (per entry in `PDU_HISTORY`)

1. **`PaediatricDiabetesUnit` row** — created if it does not exist. This
   happens for inactive predecessors and never-participated codes that
   `seed_pdus` did not create (it only creates active PDUs from
   `PZ_CODES`). The created PDU is set `active=False` (for inactive
   predecessors) or `active=True` (for the rare case of an active PDU not
   in `PZ_CODES`), with `unit_name`, `lead_organisation`, and
   `paediatric_diabetes_network` resolved from the last state. A baseline
   `PaediatricDiabetesUnitVersion` row is written covering the PDU's
   active period.

   For existing PDUs (created by `seed_pdus`), if the `lead_organisation`
   FK is `None` (the seed predates the field), it is set from the last
   state's `ods_site`. This is idempotent — if the FK is already set, it
   is not changed.

2. **`PaediatricDiabetesUnitVersion` rows** — one per historical state
   (states with `valid_to` set), with:
   - `valid_from = audit_year_to_date(state.first_audit_year)`
   - `valid_to = audit_year_to_date(next_state.first_audit_year)`
   - `active = state.active`
   - `unit_name = entry.unit_name`
   - `lead_organisation` — resolved from `state.ods_site`.
   - `paediatric_diabetes_network_id` — resolved from
     `state.regional_network` (the network name) via
     `PaediatricDiabetesNetwork.objects.get(name=...)`.

   The current-state version row (the one with `valid_to IS NULL`) is
   **not** overwritten — the seed and `backfill_pdu_lead_organisations`
   have already written it for existing PDUs, and the PDU-creation step
   wrote a baseline for created PDUs.

3. **`PaediatricDiabetesUnitNetworkMembership` rows** — one per state
   (both historical and current), linking the PDU to the network resolved
   from `state.regional_network`, over the same `[valid_from, valid_to)`
   interval as the version row. The seed does not write network membership
   rows, so the current state is written here too.

4. **`OrganisationPaediatricDiabetesUnitMembership` rows** — for each
   state with an `ods_site`, the lead organisation is linked to the PDU
   over the state's interval (both historical and current). This is the
   critical row for as-of queries: "which PDU was organisation X under on
   date Y?" **Welsh PDUs are included** — the generator resolves their
   lead organisation ODS codes from `PZ_CODES` (or by name lookup for
   inactive predecessors), so the spreadsheet's `NA` does not block the
   Welsh backfill. Only the **lead** organisation's membership is written;
   the spreadsheet does not enumerate sibling organisations, and
   backfilling them is out of scope (the existing seed + the
   forward-looking `reassign_organisation_paediatric_diabetes_unit`
   helper handle child reassignment for future mergers).

5. **`OrganisationIntegratedCareBoardMembership` rows** — **not** written
   by this command, and there is no `PaediatricDiabetesUnitICBMembership`
   table. A PDU does not have its own ICB membership; it walks to its
   parent ICB through its lead organisation and the lead organisation's
   parent trust (or LHB for Welsh PDUs). The `as_of` workflow
   (`organisation_snapshot`, `trust_as_of`, etc.) is the read path for
   "which parent organisation, trust/LHB, ICB, and NHS England region a
   given PDU had on a given date" — query the PDU's lead organisation as
   of the date, then walk up. The spreadsheet's `ICB_LHB` column is
   recorded in the version row's `notes` for provenance only.

#### Pass 2 — PDU successions (per entry in `PDU_SUCCESSIONS`)

6. **`PaediatricDiabetesUnitSuccession` row** — `predecessor` and
   `successor` resolved to `PaediatricDiabetesUnit` instances via
   `pz_code`. `succession_date` from the entry. `succession_type` from
   the entry. `notes` from the entry. Idempotent: if a row already
   exists for the same `(predecessor, successor, succession_date)`, it is
   skipped.

7. **Predecessor closure** — the predecessor PDU's `active` flag is set
   to `False` (if not already), and a `PaediatricDiabetesUnitVersion` row
   with `active=False` is written from the `succession_date` forward. This
   mirrors the trust backfill's predecessor-closure write. The
   `PaediatricDiabetesUnitSuccession` row from step 6 is the audit record
   of *why* the closure happened.

8. **Lead organisation reassignment** — the predecessor's lead
   organisation is reassigned to the successor PDU. The current
   `OrganisationPaediatricDiabetesUnitMembership` row pointing to the
   predecessor is closed (`valid_to = succession_date`), and a new one
   pointing to the successor is opened (`valid_from = succession_date`,
   `valid_to = None`). The denormalised `Organisation.paediatric_diabetes_unit`
   FK is updated to point to the successor. This is the same write the
   forward-looking `reassign_organisation_paediatric_diabetes_unit` helper
   performs, but backfilled to the succession date. This ensures the
   `as_of` workflow returns the correct PDU before and after the
   succession date, and that the PDU → lead org → trust/LHB chain is
   intact for both the predecessor and successor periods.

### Relationship to the existing seed and backfill commands

The existing `seed_pdus()` function in `seed_functions/pdus.py` reads
`PZ_CODES` from `paediatric_diabetes_units.py` and creates
`PaediatricDiabetesUnit` rows with a single current-state `active` flag.
It does **not** write version rows, membership rows, or succession rows —
it predates the temporal layer. **It is not modified by this work.**
Changing `seed_pdus()` would break initial seeding, which must remain a
minimal current-state seed.

The existing `backfill_pdu_lead_organisations` command writes the
`lead_organisation` FK and `name_source` on `PaediatricDiabetesUnit` (and
snapshots them on the current `PaediatricDiabetesUnitVersion` row),
replacing the hardcoded PZ-code lists that were in
`PaediatricDiabetesUnit.primary_organisation` and `.name`. It does **not**
write historical version rows, network memberships, or succession rows.

This work adds a **new** `backfill_pdu_successions` command (named to
mirror `backfill_successions` for trusts) that writes the full PDU entity
history: `PaediatricDiabetesUnitVersion` rows, network memberships,
lead-organisation memberships, and `PaediatricDiabetesUnitSuccession`
rows. It runs **after** `seed_pdus` (which creates the current-state
rows) and **after** `backfill_pdu_lead_organisations` (which sets the
current lead FK). The new command is idempotent and does not touch the
current-state rows the seed and lead-organisations commands have already
written — it only backfills the historical rows and the succession rows.

The two backfill commands are complementary:

- `backfill_pdu_lead_organisations` — current-state `lead_organisation`
  FK + `name_source` (already exists).
- `backfill_pdu_successions` — historical `PaediatricDiabetesUnitVersion`
  rows, `PaediatricDiabetesUnitNetworkMembership` rows,
  `OrganisationPaediatricDiabetesUnitMembership` rows (lead org only),
  and `PaediatricDiabetesUnitSuccession` rows (new).

## Running the backfill

### Prerequisites

The `backfill_pdu_successions` command assumes the database has been
seeded with `seed_pdus` (which creates the active PDU rows from
`PZ_CODES`). Inactive predecessor PDUs and never-participated codes that
are not in `PZ_CODES` are created by the backfill command itself.

### The management command

```bash
# Preview what would be backfilled (no writes)
python manage.py backfill_pdu_successions --dry-run

# Apply with interactive yes/no prompts
python manage.py backfill_pdu_successions

# Apply all without prompts (for re-runs / CI)
python manage.py backfill_pdu_successions --yes
```

The command runs in two passes:

1. **Pass 1 — PDU history.** For each PDU in `PDU_HISTORY`:
   - Creates the `PaediatricDiabetesUnit` row if it doesn't exist (inactive
     predecessors and never-participated codes), with `active=False` and a
     baseline version row.
   - Sets `lead_organisation` on existing PDUs that have it as `None`.
   - Writes `PaediatricDiabetesUnitVersion` rows for historical states.
   - Writes `PaediatricDiabetesUnitNetworkMembership` rows for all states.
   - Writes `OrganisationPaediatricDiabetesUnitMembership` rows for the
     lead organisation for all states.

2. **Pass 2 — Successions.** For each succession in `PDU_SUCCESSIONS`:
   - Writes the `PaediatricDiabetesUnitSuccession` row.
   - Closes the predecessor (`active=False` + closure version row).
   - Reassigns the predecessor's lead organisation to the successor
     (closes the old membership, opens a new one, updates the FK).

In `--dry-run` mode, reports what *would* be written without writing. In
interactive mode, prompts `[y/n]` per PDU and per succession. With
`--yes`, all prompts are auto-answered 'y'.

### Regenerating the constants

When the NPDA team updates `Master_PDU_Lookup.xlsx`, re-run the generator
to produce an updated `pdu_history.py`:

```bash
# Inside the django container (so Welsh lead-org name lookup works):
python /app/scripts/generate_pdu_history_constants.py
```

The generator reads the xlsx, cross-references `PZ_CODES` for Welsh lead
organisations, resolves inactive predecessors by name lookup against the
database, and emits `pdu_history.py`. The diff in the generated file is
the review surface for the xlsx change. Commit both the updated xlsx and
the regenerated `pdu_history.py`.

`openpyxl` is required by the generator and is listed in
`requirements/development-requirements.txt`.

### Idempotency

Every write is idempotent:

- `PaediatricDiabetesUnit`: created only if it doesn't exist.
- `PaediatricDiabetesUnitVersion`: skip if a row exists for
  `(pdu, valid_from)`.
- `PaediatricDiabetesUnitNetworkMembership`: skip if a row exists for
  `(pdu, valid_from)`.
- `OrganisationPaediatricDiabetesUnitMembership`: skip if a row exists
  for `(organisation, pdu, valid_from)`.
- `PaediatricDiabetesUnitSuccession`: skip if a row exists for
  `(predecessor, successor, succession_date)`.

This makes the command safe to re-run, and means `seed_pdus`,
`backfill_pdu_lead_organisations`, and `backfill_pdu_successions` can all
run against the same database without duplicating rows.

### Verifying the backfill

After running the backfill, verify with an as-of query. For example, PZ216
(Tunbridge Wells) merged into PZ253 on 2025-04-01 — the lead organisation
RWFTW should return PZ216 before that date and PZ253 after:

```python
import datetime
from django.db.models import Q
from rcpch_nhs_organisations.hospitals.models import (
    OrganisationPaediatricDiabetesUnitMembership,
)

def pdu_as_of(ods_code, on_date):
    m = OrganisationPaediatricDiabetesUnitMembership.objects.filter(
        organisation__ods_code=ods_code,
        valid_from__lte=on_date,
    ).filter(
        Q(valid_to__gt=on_date) | Q(valid_to__isnull=True),
    ).first()
    return m.paediatric_diabetes_unit.pz_code if m else None

pdu_as_of("RWFTW", datetime.date(2024, 1, 1))  # → PZ216
pdu_as_of("RWFTW", datetime.date(2025, 5, 1))  # → PZ253
```

To walk from the PDU to its parent trust/LHB, query the lead
organisation's trust as of the same date:

```python
from rcpch_nhs_organisations.hospitals.models import OrganisationTrustMembership

def trust_as_of(organisation, on_date):
    m = OrganisationTrustMembership.objects.filter(
        organisation=organisation,
        valid_from__lte=on_date,
    ).filter(
        Q(valid_to__gt=on_date) | Q(valid_to__isnull=True),
    ).first()
    return m.trust if m else None
```

## Design decisions

1. **Succession date.** PDUs do not currently carry succession dates in
   the live system. The first day of the new audit year is the correct
   `succession_date` for a PDU acquisition/merger/closure. Where
   `merger-handling.md` quotes an operational date (e.g. "January 2026"),
   that is recorded in `notes`; the temporal row uses the audit-year
   boundary.

2. **Never-participated succession type.** Use `closure` with `successor`
   set, mirroring the trust closure-with-successor pattern. No new
   `succession_type` choice is added.

3. **Welsh PDU lead organisations.** The spreadsheet's `ODS_site` is
   `NA` for Welsh PDUs, but the lead organisations **must** be seeded. The
   generator resolves the Welsh lead organisation ODS codes from
   `PZ_CODES` (for active PDUs) and by name lookup against `Organisation`
   (for inactive predecessors not in `PZ_CODES`). The backfill writes the
   lead-organisation `OrganisationPaediatricDiabetesUnitMembership` rows
   for Welsh PDUs the same way as for English PDUs.

4. **PDU → ICB membership.** There is no `PaediatricDiabetesUnitICBMembership`
   table and none is added. A PDU walks to its parent ICB through its lead
   organisation and the lead organisation's parent trust (or LHB for Welsh
   PDUs). The `as_of` workflow is the read path for "which parent
   organisation, trust/LHB, ICB, and NHS England region a given PDU had
   on a given date".

5. **Backfill scope: lead organisation only.** Only the lead
   organisation's `OrganisationPaediatricDiabetesUnitMembership` is
   backfilled. Sibling organisations are not enumerated — the spreadsheet
   does not carry them, and the existing seed + forward-looking helper
   handle child reassignment for future mergers.

6. **No change to `seed_pdus()`.** The seed function is the minimal
   current-state seed and must not be modified (it would break initial
   seeding). The PDU history is written by a **new**
   `backfill_pdu_successions` command, run after `seed_pdus` and
   `backfill_pdu_lead_organisations`.

7. **Inactive predecessor PDUs created by the backfill.** The backfill
   command creates missing PDU rows (inactive predecessors and
   never-participated codes not in `PZ_CODES`), rather than requiring them
   to be added to `PZ_CODES` first. This keeps `PZ_CODES` as the
   current-state seed and lets the backfill own the historical entities.

## Out of scope

- **Future PDU mergers.** These use the forward-looking admin wizards
  (*Acquire another…*, *Merge into a new…*) and the
  `reassign_organisation_paediatric_diabetes_unit` helper, as described in
  `merger-handling.md`. This backfill is a one-off recovery of historical
  state.
- **PDU attribute history beyond what the spreadsheet records.** The
  spreadsheet carries audit-year granularity, not exact dates. If a PDU
  was renamed mid-audit-year, the rename is not captured. This matches
  the NPDA's own reporting granularity.
- **Child organisation PDU membership history for non-lead organisations.**
  The spreadsheet does not enumerate every child site of every PDU. A
  complete child-membership history would require a different source (the
  NPDA's full membership records, not the contact database).
- **PDU → ICB membership table.** The PDU reaches its ICB through the
  lead organisation and trust/LHB; no dedicated membership table is
  added.