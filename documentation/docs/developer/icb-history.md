---
title: ICB history and succession
author: Dr Simon Chapman
---

# ICB history and succession

This document describes how Integrated Care Board (ICB) mergers, splits,
and successions are modelled and backfilled. ICBs are tracked by the ODS
(unlike PDUs), so the source of truth is the ODS API — specifically the
`Succs` block on each ICB's `/organisations/{ods_code}` record. The
backfill follows the same pattern as the trust and organisation backfill
(`backfill_successions --entity trust/organisation`), extended to support
`--entity icb`.

It should be read alongside:

- [`temporal-history.md`](temporal-history.md) — the schema (Layer 1
  version tables, Layer 2 membership tables, Layer 3 succession tables).
- [`backfill.md`](backfill.md) — the ODS-driven trust backfill, which
  this feature extends for ICBs.
- [`ods-api.md`](ods-api.md) — the ODS API reference, including the
  `Succs` block semantics.
- [`merger-handling.md`](merger-handling.md) — the merger types and the
  forward-looking admin workflow.

## Background and motivation

ICBs were established on 1 July 2022, replacing Clinical Commissioning
Groups (CCGs). The 42 ICBs created in 2022 are being reorganised on
**1 April 2026**: 12 of the original 42 will merge/split into 6 new ICBs,
and 1 existing ICB (QRL, Hampshire and Isle of Wight) will gain territory
from one of the dissolving ICBs.

The temporal layer already models ICB attribute history
(`IntegratedCareBoardVersion`, Layer 1) and ICB membership history
(`OrganisationIntegratedCareBoardMembership` and
`TrustIntegratedCareBoardMembership`, Layer 2). This feature adds the
**Layer 3 succession table** (`IntegratedCareBoardSuccession`) to record
the predecessor → successor link when ICBs merge or split.

Without it, an as-of query for "which ICB was this organisation under on
date X" can only walk the membership table. If the membership rows have
been backfilled (closing the old ICB membership and opening the new one),
the query works — but there is no audit record of *why* the membership
changed, and no way to trace the ICB succession chain independently of
the organisation memberships.

## What exists

| Layer | Table | Status |
|---|---|---|
| 1 — Entity version | `IntegratedCareBoardVersion` | Snapshots `name`, boundary fields, `publication_date`, `active`. |
| 2 — Relationship membership | `OrganisationIntegratedCareBoardMembership` | Tracks org → ICB over time. |
| 2 — Relationship membership | `TrustIntegratedCareBoardMembership` | Tracks trust → ICB over time. |
| 3 — Succession | `IntegratedCareBoardSuccession` | Records predecessor → successor links. Added by this feature. |

Helper functions:

- `update_integrated_care_board_attributes()` — Layer 1 forward-looking
  attribute update.
- `backfill_integrated_care_board_attributes()` — Layer 1 historical
  attribute backfill (added by this feature).
- `reassign_organisation_integrated_care_board()` — Layer 2 forward-looking
  org → ICB reassignment.
- `reassign_trust_integrated_care_board()` — Layer 2 forward-looking
  trust → ICB reassignment.

## The 2026 ICB reorganisation

On **1 April 2026**, 12 of the 42 ICBs established in 2022 will cease to
exist. Their territories will be redistributed:

- **6 new ICBs** will be created, each absorbing territory from 2–3 of
  the dissolving ICBs.
- **1 existing ICB** (QRL, Hampshire and Isle of Wight) will gain
  territory from one dissolving ICB (Frimley, QNQ).
- **3 of the 12 dissolving ICBs** will split, their territory going to
  multiple successors.

All data is from the ODS API (`/organisations/{ods_code}` → `Succs`
block), verified on both sides (each predecessor's `Successor` event
matches the corresponding successor's `Predecessor` event). The
succession date is **2026-04-01** for all 16 events.

### ODS-verified succession map

The table below is the complete set of ICB succession events, confirmed
against the ODS API. Each row is one predecessor → successor pair. The
`Legal.Start` column is the successor's own establishment date from the
ODS `Date` block — where it equals the succession date, the successor is
a new entity (true merger); where it is earlier, the successor is an
existing entity absorbing territory (acquisition).

| Predecessor (ODS) | Predecessor name | Successor (ODS) | Successor name | Succession date | Succession type | Notes |
|---|---|---|---|---|---|---|
| QHG | NHS Bedfordshire, Luton and Milton Keynes | S1Y5D | NHS Central East | 2026-04-01 | merger | New ICB (Legal.Start=2026-04-01). 3 predecessors. |
| QUE | NHS Cambridgeshire and Peterborough | S1Y5D | NHS Central East | 2026-04-01 | merger | Same as above. |
| QM7 | NHS Hertfordshire and West Essex | S1Y5D | NHS Central East | 2026-04-01 | split | QM7 also → D7T5G (Essex). |
| QM7 | NHS Hertfordshire and West Essex | D7T5G | NHS Essex | 2026-04-01 | split | QM7 also → S1Y5D (Central East). |
| QH8 | NHS Mid and South Essex | D7T5G | NHS Essex | 2026-04-01 | merger | New ICB (Legal.Start=2026-04-01). 3 predecessors. |
| QJG | NHS Suffolk and North East Essex | D7T5G | NHS Essex | 2026-04-01 | split | QJG also → T6Y0W (Norfolk and Suffolk). |
| QJG | NHS Suffolk and North East Essex | T6Y0W | NHS Norfolk and Suffolk | 2026-04-01 | split | QJG also → D7T5G (Essex). |
| QMM | NHS Norfolk and Waveney | T6Y0W | NHS Norfolk and Suffolk | 2026-04-01 | merger | New ICB (Legal.Start=2026-04-01). 2 predecessors. |
| QNQ | NHS Frimley | S0E4D | NHS Thames Valley | 2026-04-01 | split | QNQ also → S9B9J and QRL. 3-way split. |
| QNQ | NHS Frimley | S9B9J | NHS Surrey and Sussex | 2026-04-01 | split | QNQ also → S0E4D and QRL. 3-way split. |
| QNQ | NHS Frimley | QRL | NHS Hampshire and Isle of Wight | 2026-04-01 | acquisition | QRL is an existing ICB (Legal.Start=None). Gains territory from Frimley. |
| QU9 | NHS Buckinghamshire, Oxfordshire and Berkshire West | S0E4D | NHS Thames Valley | 2026-04-01 | merger | New ICB (Legal.Start=2026-04-01). 2 predecessors. |
| QXU | NHS Surrey Heartlands | S9B9J | NHS Surrey and Sussex | 2026-04-01 | merger | New ICB (Legal.Start=2026-04-01). 3 predecessors. |
| QNX | NHS Sussex | S9B9J | NHS Surrey and Sussex | 2026-04-01 | merger | Same as above. |
| QMJ | NHS North Central London | Z9B2Z | NHS West and North London | 2026-04-01 | merger | New ICB (Legal.Start=2026-04-01). 2 predecessors. |
| QRV | NHS North West London | Z9B2Z | NHS West and North London | 2026-04-01 | merger | Same as above. |

**Summary:** 16 succession rows, 12 predecessors (3 splitting), 7
successors (6 new + 1 existing), all on 2026-04-01.

### The three splits

Three of the 12 dissolving ICBs split their territory across multiple
successors:

| Predecessor | Successors | Type |
|---|---|---|
| QNQ (Frimley) | S0E4D (Thames Valley), S9B9J (Surrey and Sussex), QRL (Hampshire and Isle of Wight) | 3-way split |
| QM7 (Hertfordshire and West Essex) | S1Y5D (Central East), D7T5G (Essex) | 2-way split |
| QJG (Suffolk and North East Essex) | D7T5G (Essex), T6Y0W (Norfolk and Suffolk) | 2-way split |

For these, the child organisation and trust ICB memberships need to be
reassigned to the correct successor — which successor depends on the
organisation's geographic location. The ODS `Rels` block on each child
organisation's record will show which new ICB it reports to. This is a
follow-up (see [Out of scope](#out-of-scope)).

### Cross-check against the spreadsheet

The `Master_PDU_Lookup.xlsx` spreadsheet's `ICB_LHB` column records the
"Old ICB" and "New ICB" for each PDU state. The 6 new ICB names in the
spreadsheet match the 6 new ICB names from the ODS:

| Spreadsheet name (stripped) | ODS code | ODS name |
|---|---|---|
| NHS Central East Integrated Care Board | S1Y5D | NHS CENTRAL EAST INTEGRATED CARE BOARD |
| NHS Essex Integrated Care Board | D7T5G | NHS ESSEX INTEGRATED CARE BOARD |
| NHS Norfolk and Suffolk Integrated Care Board | T6Y0W | NHS NORFOLK AND SUFFOLK INTEGRATED CARE BOARD |
| NHS Surrey and Sussex Integrated Care Board | S9B9J | NHS SURREY AND SUSSEX INTEGRATED CARE BOARD |
| NHS Thames Valley Integrated Care Board | S0E4D | NHS THAMES VALLEY INTEGRATED CARE BOARD |
| NHS West and North London Integrated Care Board | Z9B2Z | NHS WEST AND NORTH LONDON INTEGRATED CARE BOARD |

The spreadsheet does not record QRL (Hampshire and Isle of Wight) as a
"New ICB" because it already exists — it is gaining territory, not being
created. The ODS is the source of truth for this; the spreadsheet's
"Old ICB" / "New ICB" columns are PDU-centric and do not surface the
QRL acquisition.

## Design

### New model: `IntegratedCareBoardSuccession`

A Layer 3 succession table, mirroring `TrustSuccession` and
`PaediatricDiabetesUnitSuccession`. The `successor` FK is nullable to
support closures with no successor (same as trusts and PDUs).

File: `rcpch_nhs_organisations/hospitals/models/integrated_care_board_succession.py`

### New helper: `backfill_integrated_care_board_attributes`

A Layer 1 backfill helper, mirroring `backfill_trust_attributes`. Inserts
an `IntegratedCareBoardVersion` row with an explicit `[valid_from,
valid_to)` interval and explicit attribute values, without touching the
current entity row or the current version row. Used by
`backfill_successions` for the predecessor closure write and the successor
establishment row.

File: `rcpch_nhs_organisations/hospitals/general_functions/membership.py`

### `active` field

An `active` boolean (defaulting to `True`) was added to both
`IntegratedCareBoard` and `IntegratedCareBoardVersion`, mirroring the trust
and PDU pattern. This allows the closure workflow to set `active=False` on
dissolved ICBs.

### Boundary fields made nullable

The boundary fields (`bng_e`, `bng_n`, `long`, `lat`, `globalid`, `geom`)
on `IntegratedCareBoardBoundaries` were made nullable so the backfill can
create new ICB rows without boundary data. The long-term intention is to
deprecate the geometry fields from this project entirely and leave all
boundary data to the
[RCPCH Census Platform](https://github.com/rcpch/rcpch-census-platform).
A future feature on the census platform would expose a REST endpoint
serving ICB geometry by ODS code. The geometry fields can be fully removed
in a future migration once that endpoint is available and consuming
applications have migrated.

### Auto-classification of the QRL acquisition

QRL (NHS Hampshire and Isle of Wight) is an existing ICB that gains
territory from Frimley (QNQ) on 2026-04-01. ODS does not expose a
`Legal.Start` for QRL, so the `backfill_successions` command's
`Legal.Start == event date` check cannot distinguish it from a true
merger. A constants table auto-classifies it as an acquisition,
mirroring the `KNOWN_ACQUISITIONS` table for trusts.

The constants live in `KNOWN_ICB_ACQUISITIONS` in
`rcpch_nhs_organisations/hospitals/constants/known_icb_acquisitions.py`.
The command looks up each `(successor_ods_code, succession_date)` pair
and, if found, auto-classifies the succession type as `acquisition`.

| ODS | Successor (current name) | Predecessor | Legal.Start | Succession date | Notes |
|---|---|---|---|---|---|
| QRL | NHS Hampshire and Isle of Wight Integrated Care Board | QNQ (NHS Frimley) | 2017-04-01 | 2026-04-01 | Existing ICB gains territory from Frimley (3-way split: QNQ → S0E4D, S9B9J, QRL). Name unchanged. |

### Creating missing successor ICBs

The 6 new ICBs (S1Y5D, S0E4D, S9B9J, D7T5G, T6Y0W, Z9B2Z) do not exist
in the database or constants. The `backfill_successions` command creates
them on the fly from the ODS record (the `_create_missing_icb` method),
matching the PDU backfill pattern. The ICB row is created with `ods_code`,
`name`, and `publication_date` from the ODS record. The boundary/shape
fields are left as `None` (they are now nullable). A baseline
`IntegratedCareBoardVersion` row is written at `Legal.Start`.

### Admin registration

`IntegratedCareBoardSuccession` is registered in the admin, mirroring
`TrustSuccessionAdmin` — list display, filter, search, date hierarchy,
and the shared succession change templates.

## Running the backfill

```bash
# Preview what would be backfilled (no writes)
python manage.py backfill_successions --entity icb --dry-run

# Apply with interactive yes/no prompts
python manage.py backfill_successions --entity icb

# Apply all without prompts (for re-runs / CI)
python manage.py backfill_successions --entity icb --yes
```

The command runs the same two-pass logic as `--entity trust`:

1. **Pass 1** — iterates every ICB in the database, fetches its ODS
   record, reads the `Succs` block, and for each missing succession row:
   creates the `IntegratedCareBoardSuccession` row, creates missing
   successor ICBs from the ODS record, and closes the predecessor
   (`active=False` + closure version row).
2. **Pass 2** — backfills the successor's establishment/name row for each
   applied `Predecessor` event. For true mergers (new ICBs with
   `Legal.Start == event date`), writes an establishment row. For
   acquisitions (QRL), auto-classifies via `KNOWN_ICB_ACQUISITIONS` and
   skips the name backfill (ICBs are not renamed when they gain
   territory).

The command is idempotent: re-running creates no duplicate rows.

### GitHub Action

The monthly ODS change detection GitHub Action
(`.github/workflows/ods-change-detection.yml`) now includes the ICB
succession backfill as a third check. It runs
`backfill_successions --entity icb --dry-run` alongside the ODS sync and
trust succession backfill, and combines all three reports into a single
GitHub issue. See [`temporal-history.md`](temporal-history.md) → "GitHub
Action for ODS change detection".

## Out of scope

- **Boundary/shape data for new ICBs.** The long-term intention is to
  deprecate the geometry fields from this project entirely and leave all
  boundary data to the RCPCH Census Platform. The fields are made
  nullable now so the backfill can proceed; a future migration will
  remove them once the census platform exposes a geometry endpoint and
  consuming applications have migrated.
- **Future ICB mergers.** These will use the forward-looking admin
  workflow (once the admin actions for ICB reassignment are built) and
  the `reassign_organisation_integrated_care_board` /
  `reassign_trust_integrated_care_board` helpers.
- **CCG / STP history.** The ODS `Rels` block on each trust's record
  contains historical CCG (`RO210`) and STP (`RO132`) relationships dating
  back to 1996, but these entities are not in our database and audit
  reporting does not rely on them. Reporting walks the chain
  organisation → trust/LHB → ICB → NHS England region → country, so
  only ICB-level affiliations are recovered.
- **Organisation → ICB membership backfill.** Organisations do not have
  their own ICB rels in the ODS — only trusts do. An organisation's ICB
  affiliation is implicit through its parent trust. The
  `OrganisationIntegratedCareBoardMembership` table is populated by the
  seed (current state) and the forward-looking `reassign_*` helper
  (future changes). Recovering historical org → ICB memberships would
  require deriving them from the trust → ICB + org → trust membership
  intervals — a separate command if needed.

## Child membership backfill

When the 12 old ICBs dissolve on 2026-04-01, the trusts under them need
to be reassigned to the correct successor ICB. The ODS holds the full
trust → ICB affiliation history in the `Rels` block of each trust's
record — `RE5` ("managed by / reports to") and `RE8` ("operates /
is operated by") rels pointing at ICBs (`RO261`), with operational
`[Start, End]` intervals.

The `backfill_icb_memberships` command recovers this history:

```bash
# Preview what would be backfilled (no writes)
python manage.py backfill_icb_memberships --dry-run

# Apply with interactive prompts
python manage.py backfill_icb_memberships

# Apply all without prompts
python manage.py backfill_icb_memberships --yes
```

The command:

1. Iterates every trust in the database.
2. Fetches its ODS record via `/organisations/{ods_code}`.
3. Reads the `RE5`/`RE8` rels pointing at `RO261` (ICBs) — ignoring
   `RO210` (CCGs) and `RO132` (STPs), which are not needed for audit
   reporting.
4. For each rel, backfills a `TrustIntegratedCareBoardMembership` row
   with the operational `[Start, End]` interval (idempotent on
   `(trust, icb, valid_from, valid_to)`).

Organisations do not have their own ICB rels in the ODS — only trusts do.
An organisation's ICB affiliation is implicit through its parent trust:
the `as_of` workflow walks organisation → trust → ICB, so recovering the
trust → ICB membership is sufficient. The `OrganisationIntegratedCareBoardMembership`
table is populated by the seed (current state) and the forward-looking
`reassign_organisation_integrated_care_board` helper (future changes).

The command mirrors `backfill_trust_memberships` (which reads `RE6` rels
to recover trust membership history) and reuses the same ODS-fetch,
idempotency, `--dry-run`, `--yes`, and `--since`/`--all` window patterns.
The default window is 2020-04-01 (when ICB rels first appear in ODS).
