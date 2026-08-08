---
title: ICB history and succession (planning)
author: Dr Simon Chapman
---

# ICB history and succession (planning)

> **Status:** Planning document. This file will be converted into the
> reference documentation for the feature once the implementation is
> complete. It captures the ODS-verified ICB succession data, the design
> decisions, and the implementation plan. On completion, rename to
> `icb-history.md` and trim the planning-specific framing.

This document describes how Integrated Care Board (ICB) mergers, splits,
and successions are modelled and backfilled. ICBs are tracked by the ODS
(unlike PDUs), so the source of truth is the ODS API — specifically the
`Succs` block on each ICB's `/organisations/{ods_code}` record. The
backfill follows the same pattern as the trust and organisation
backfill (`backfill_successions --entity trust/organisation`), extended
to support `--entity icb`.

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
`TrustIntegratedCareBoardMembership`, Layer 2). What is missing is the
**Layer 3 succession table** — there is no `IntegratedCareBoardSuccession`
model to record the predecessor → successor link when ICBs merge or split.

Without it, an as-of query for "which ICB was this organisation under on
date X" can only walk the membership table. If the membership rows have
been backfilled (closing the old ICB membership and opening the new one),
the query works — but there is no audit record of *why* the membership
changed, and no way to trace the ICB succession chain independently of
the organisation memberships.

## What exists today

| Layer | Table | Status |
|---|---|---|
| 1 — Entity version | `IntegratedCareBoardVersion` | ✅ Exists. Snapshots `name`, `bng_e`, `bng_n`, `long`, `lat`, `globalid`, `geom`, `publication_date`. |
| 2 — Relationship membership | `OrganisationIntegratedCareBoardMembership` | ✅ Exists. Tracks org → ICB over time. |
| 2 — Relationship membership | `TrustIntegratedCareBoardMembership` | ✅ Exists. Tracks trust → ICB over time. |
| 3 — Succession | `IntegratedCareBoardSuccession` | ❌ Does not exist. This feature adds it. |

Helper functions that exist:

- `update_integrated_care_board_attributes()` — Layer 1 forward-looking
  attribute update (closes current version row, opens new one).
- `reassign_organisation_integrated_care_board()` — Layer 2 forward-looking
  org → ICB reassignment.
- `reassign_trust_integrated_care_board()` — Layer 2 forward-looking
  trust → ICB reassignment.

Helper functions that are missing (added by this feature):

- `backfill_integrated_care_board_attributes()` — Layer 1 historical
  attribute backfill (inserts a version row with an explicit interval,
  without touching the current entity row). Needed by
  `backfill_successions` for the predecessor closure write and the
  successor establishment row.

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
organisation's geographic location. This is the same challenge as the
trust split case (see `merger-handling.md` → "Dissolution with split").
The ODS `Rels` block on each child organisation's record will show which
new ICB it reports to, so the `backfill_trust_memberships` pattern (which
reads `Rels` to recover membership history) can be extended for ICB
memberships too — but that is a follow-up, not part of this initial
backfill.

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

A new Layer 3 succession table, mirroring `TrustSuccession` and
`PaediatricDiabetesUnitSuccession`:

```python
class IntegratedCareBoardSuccession(TimeStampAbstractBaseClass):
    predecessor = models.ForeignKey(
        to=IntegratedCareBoard,
        on_delete=models.PROTECT,
        related_name="succession_predecessor_links",
    )
    successor = models.ForeignKey(
        to=IntegratedCareBoard,
        on_delete=models.PROTECT,
        related_name="succession_successor_links",
        null=True,
        blank=True,
        default=None,
    )
    succession_date = models.DateField()
    succession_type = models.CharField(
        max_length=20,
        choices=[
            ("merger", "Merger"),
            ("acquisition", "Acquisition"),
            ("rename", "Rename"),
            ("closure", "Closure"),
            ("split", "Split"),
        ],
    )
    notes = models.TextField(blank=True, default="")
```

The `successor` FK is nullable to support closures with no successor
(same as trusts and PDUs).

### New helper: `backfill_integrated_care_board_attributes`

A Layer 1 backfill helper, mirroring `backfill_trust_attributes` and
`backfill_organisation_attributes`. Inserts an
`IntegratedCareBoardVersion` row with an explicit `[valid_from,
valid_to)` interval and explicit attribute values, without touching the
current entity row or the current version row. Needed by
`backfill_successions` for:

- The predecessor closure write (an `active=False` version row from the
  succession date forward).
- The successor establishment row (for true mergers, a version row at
  `Legal.Start` with the current name, replacing the baseline row).

### Extend `backfill_successions --entity icb`

The existing `backfill_successions` command already supports `--entity
trust` and `--entity organisation`. Adding `icb` as a third entity type
requires:

1. Add `IntegratedCareBoard`, `IntegratedCareBoardSuccession`, and
   `IntegratedCareBoardVersion` to the imports.
2. Add an `icb` entry to `ENTITY_CONFIG` with the model, succession
   model, version model, version parent field, ods code field,
   backfill helper, and name field.
3. Add `backfill_integrated_care_board_attributes` to the membership
   helpers import.

The command's existing logic (Pass 1: create succession rows + close
predecessors; Pass 2: backfill successor establishment/name rows) then
works unchanged for ICBs. The `Legal.Start == event date` check
distinguishes the 6 true mergers (new ICBs) from the 1 acquisition (QRL).

### Creating the 6 new ICB rows

The 6 new ICBs (S1Y5D, S0E4D, S9B9J, D7T5G, T6Y0W, Z9B2Z) do not exist
in the database or in the `INTEGRATED_CARE_BOARDS` constants. They need
to be created before the succession rows can link to them. Two options:

1. **Add them to `INTEGRATED_CARE_BOARDS` in `integrated_care_boards.py`**
   and re-run the seed. This is the simplest approach — the seed creates
   the `IntegratedCareBoard` row and the baseline `IntegratedCareBoardVersion`
   row. The boundary/shape data (`bng_e`, `bng_n`, `long`, `lat`,
   `globalid`, `geom`) is not available from the ODS; it would need to be
   sourced from the ONS ICB boundary shapefiles (a separate data source).
   For now, the new ICBs can be created without boundary data (the fields
   are nullable on `IntegratedCareBoardBoundaries` — actually they are
   not currently nullable, so the model may need adjusting, or the seed
   can use placeholder values).

2. **Have `backfill_successions` create missing successor ICB rows** on
   the fly, the same way `backfill_pdu_successions` creates missing PDU
   rows. This keeps the seed as the current-state seed and lets the
   backfill own the historical entities.

**Decision: option 2** — have `backfill_successions` create missing
successor ICB rows, matching the PDU backfill pattern. The ICB row is
created with `ods_code`, `name`, and `publication_date` from the ODS
record. The boundary/shape fields are left as defaults (the model will
need the non-nullable boundary fields made nullable, or the seed will
need to provide placeholder values — see [Open questions](#open-questions)
below). A baseline `IntegratedCareBoardVersion` row is written at
`Legal.Start`.

### Admin registration

Register `IntegratedCareBoardSuccession` in the admin, mirroring
`TrustSuccessionAdmin`:

```python
class IntegratedCareBoardSuccessionAdmin(admin.ModelAdmin):
    list_display = ("predecessor", "successor", "succession_date", "succession_type")
    list_filter = ("succession_type",)
    search_fields = (
        "predecessor__ods_code",
        "successor__ods_code",
        "predecessor__name",
        "successor__name",
    )
    date_hierarchy = "succession_date"
    ordering = ("-succession_date",)
```

### Auto-classification of the QRL acquisition

QRL (NHS Hampshire and Isle of Wight) is an existing ICB that gains
territory from Frimley (QNQ) on 2026-04-01. ODS does not expose a
`Legal.Start` for QRL, so the `backfill_successions` command's
`Legal.Start == event date` check cannot distinguish it from a true
merger. A constants table auto-classifies it as an acquisition,
mirroring the `KNOWN_ACQUISITIONS` table for trusts.

The constants live in `KNOWN_ICB_ACQUISITIONS` in
`rcpch_nhs_organisations/hospitals/constants/known_icb_acquisitions.py`.
The command's Pass 2 looks up each
`(successor_ods_code, succession_date)` pair and, if found,
auto-classifies the succession type as `acquisition` without prompting.

| ODS | Successor (current name) | Predecessor | Legal.Start | Succession date | Notes |
|---|---|---|---|---|---|
| QRL | NHS Hampshire and Isle of Wight Integrated Care Board | QNQ (NHS Frimley) | 2017-04-01 | 2026-04-01 | Existing ICB gains territory from Frimley (3-way split: QNQ → S0E4D, S9B9J, QRL). Name unchanged. |

### What about child organisation/trust ICB membership reassignment?

When an ICB merges or splits, the child organisations and trusts that
were under the old ICB need to be reassigned to the new ICB. This is
the Layer 2 membership update — the same pattern as
`backfill_trust_memberships` (which reads the `Rels` block on each
organisation's ODS record to recover trust membership history).

For ICBs, the `Rels` block on each organisation's record contains `RE5`
/ `RE8` rels pointing at ICBs (`RO261`), with operational `[Start, End]`
intervals. A `backfill_icb_memberships` command (mirroring
`backfill_trust_memberships`) could read these rels and backfill
`OrganisationIntegratedCareBoardMembership` and
`TrustIntegratedCareBoardMembership` rows.

**This is a follow-up, not part of the initial ICB succession backfill.**
The initial backfill creates the Layer 3 succession rows and the
Layer 1 version rows (establishment/closure). The Layer 2 membership
reassignment can be done separately, either via a dedicated
`backfill_icb_memberships` command or via the forward-looking
`reassign_organisation_integrated_care_board` /
`reassign_trust_integrated_care_board` helpers.

## Implementation plan

In order, with dependencies:

1. **Make `IntegratedCareBoardBoundaries` boundary fields nullable.**
   The new ICBs created by the backfill do not have boundary/shape data
   (ONS has not yet published 2026 ICB boundary shapefiles). The fields
   `bng_e`, `bng_n`, `long`, `lat`, `globalid`, and `geom` need to be
   nullable (`null=True, blank=True, default=None`) so the backfill can
   create ICB rows without them. Migration. The boundary data can be
   loaded later from ONS shapefiles once published.

2. **Add `active` field to `IntegratedCareBoard` and
   `IntegratedCareBoardVersion`.** Add an `active` boolean
   (defaulting to `True`) to both models, mirroring the trust and PDU
   pattern. This allows the closure workflow to set `active=False` on
   dissolved ICBs. Migration + data migration to set `active=True` on
   all existing ICBs.

3. **Add `IntegratedCareBoardSuccession` model.** New model in
   `models/integrated_care_board_succession.py`, mirroring
   `TrustSuccession`. Register in `models/__init__.py`. Migration.

4. **Add `backfill_integrated_care_board_attributes` helper.** In
   `general_functions/membership.py`, mirroring
   `backfill_trust_attributes`.

5. **Add `KNOWN_ICB_ACQUISITIONS` constants file.**
   `constants/known_icb_acquisitions.py`, mirroring
   `KNOWN_ACQUISITIONS` for trusts. Auto-classifies QRL as an
   acquisition (existing ICB absorbing territory from Frimley, QNQ).
   Surface the same in a table in the docs. Add a
   `lookup_known_icb_acquisition()` function, mirroring
   `lookup_known_acquisition()`.

6. **Extend `backfill_successions` to support `--entity icb`.** Add the
   `icb` entry to `ENTITY_CONFIG`. Add logic to create missing successor
   ICB rows (with `ods_code`, `name`, and `publication_date` from ODS,
   and a baseline version row at `Legal.Start`). Wire up the
   `KNOWN_ICB_ACQUISITIONS` lookup in Pass 2, mirroring the trust
   `KNOWN_ACQUISITIONS` path. The existing Pass 1 / Pass 2 logic then
   works unchanged.

7. **Register `IntegratedCareBoardSuccession` in the admin.** Mirroring
   `TrustSuccessionAdmin`.

8. **Add the 6 new ICBs to `INTEGRATED_CARE_BOARDS` constants.** So that
   a fresh seed creates them. The backfill command also creates them if
   they don't exist (idempotent), but having them in the constants is
   the right place for the current-state seed. Add entries to
   `INTEGRATED_CARE_BOARDS_LOCAL_AUTHORITIES` mapping the new ICBs to
   their NHS England regions.

9. **Tests.** `tests/test_backfill_icb_successions.py`:
   - Dry-run writes nothing.
   - Creates missing successor ICB rows.
   - Creates succession rows with correct type (merger for new ICBs,
     acquisition for QRL via `KNOWN_ICB_ACQUISITIONS`).
   - Closes predecessors (`active=False` + closure version row).
   - Backfills establishment rows for true mergers.
   - Idempotency (run twice, no duplicates).
   - Split case: QNQ → 3 successors, 3 succession rows created.

10. **Documentation.** Convert this planning document into
    `documentation/docs/developer/icb-history.md` (the reference doc),
    and add it to `documentation/mkdocs.yml` after `pdu-history.md`.
    Cross-link from `merger-handling.md` and `backfill.md`. Include the
    `KNOWN_ICB_ACQUISITIONS` table, mirroring the trust acquisitions
    table in `backfill.md`.

## Open questions

1. **Boundary/shape data for ICBs.** The current 42 ICBs all have boundary
   geometry loaded from ONS shapefiles
   (`Integrated_Care_Boards_April_2023_EN_BSC`). The long-term intention
   is to **deprecate the geometry fields from this project** and leave
   all boundary data to the
   [RCPCH Census Platform](https://github.com/rcpch/rcpch-census-platform),
   which already holds ICB boundary data (loaded from the ONS ArcGIS
   FeatureServer). A future feature on the census platform would expose
   a REST endpoint serving ICB geometry by ODS code, so consuming
   applications can fetch boundaries on demand rather than duplicating
   them here.

   For now, the boundary fields (`bng_e`, `bng_n`, `long`, `lat`,
   `globalid`, `geom`) on `IntegratedCareBoardBoundaries` are made
   **nullable** (`null=True, blank=True, default=None`) so that:
   - The backfill can create the 6 new ICB rows without boundary data.
   - Existing ICBs retain their geometry (no data loss).
   - The geometry fields can be fully removed in a future migration once
     the census platform endpoint is available and consuming applications
     have migrated.

   Each ICB is already part of an NHS England region and country via the
   `INTEGRATED_CARE_BOARDS_LOCAL_AUTHORITIES` constants, which map ICBs
   to regions — the new ICBs will need entries in this table too.

2. **Child membership reassignment.** When the 12 old ICBs dissolve, the
   organisations and trusts under them need to be reassigned to the
   correct successor ICB. For the 3 splits (QNQ, QM7, QJG), this
   requires knowing which successor each organisation goes to — the ODS
   `Rels` block on each organisation's record has this. Whether this is
   done as part of the initial backfill or as a follow-up depends on
   whether there will be any actual reassignment of children at the
   time the backfill runs. If the 2026 reorganisation has not yet
   happened (the succession date is in the future), the child
   memberships are still current and do not need reassignment yet — the
   forward-looking `reassign_*` helpers handle it when the time comes.
   If the backfill runs after the reorganisation, the child memberships
   need backfilling too. *Decision: defer this until we know whether
   the reorganisation has taken effect. The initial backfill creates
   the succession rows and version rows only; the membership
   reassignment is a separate command if needed.*

3. **QRL (Hampshire and Isle of Wight) acquisition.** QRL is an existing
   ICB gaining territory from Frimley (QNQ). ODS does not expose a
   `Legal.Start` for QRL, so the `backfill_successions` command's
   `Legal.Start == event date` check will classify it as a fallback
   merger. It should be an `acquisition` (existing entity absorbing
   territory). *Decision: auto-classify via a constants file
   (`KNOWN_ICB_ACQUISITIONS`), mirroring the `KNOWN_ACQUISITIONS`
   table for trusts. Surface the same in a table in the docs, as we do
   with orgs, trusts, and PDUs.*

4. **ICB `active` field.** The 12 old ICBs are still marked `Active` in
   the ODS (as of today). After the 2026-04-01 reorganisation, ODS will
   mark them `Inactive`. The backfill command closes predecessors by
   setting `active=False` and writing a closure version row — this is
   the same pattern as trusts. The `IntegratedCareBoard` model does not
   currently have an `active` field. *Decision: yes — add an `active`
   boolean to `IntegratedCareBoard` (defaulting to `True`), snapshotted
   on `IntegratedCareBoardVersion`. This mirrors the trust and PDU
   pattern and allows the closure workflow to work.*

## Out of scope

- **Child organisation/trust ICB membership reassignment.** The Layer 2
  membership update (reassigning organisations and trusts from old ICBs
  to new ICBs) is a follow-up command, not part of the initial
  succession backfill.
- **Boundary/shape data for new ICBs.** The long-term intention is to
  deprecate the geometry fields from this project entirely and leave all
  boundary data to the RCPCH Census Platform. The fields are made
  nullable now so the backfill can proceed; a future migration will
  remove them once the census platform exposes a geometry endpoint and
  consuming applications have migrated. Loading 2026 ONS shapefiles into
  this project is out of scope.
- **Future ICB mergers.** These will use the forward-looking admin
  workflow (once the admin actions for ICB reassignment are built) and
  the `reassign_organisation_integrated_care_board` /
  `reassign_trust_integrated_care_board` helpers.
- **CCG → ICB transition (2022).** The 2022 transition from CCGs to
  ICBs is not modelled in the temporal layer (it predates installation).
  The `Rels` block on each organisation's record may contain historical
  CCG (`RO210`) relationships, but recovering these is a separate
  project.
