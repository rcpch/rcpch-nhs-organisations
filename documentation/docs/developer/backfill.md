---
title: Backfilling historical states
author: Dr Simon Chapman
---

# Backfilling historical states

This document describes how to recover organisational history that was
overwritten before the temporal history layer was installed — past names,
past trust affiliations, and merger/succession links. It covers the ODS
API's recovery window, the manual `backfill_*` helpers, and the two
management commands that recover the full succession and membership chain
from ODS.

It should be read alongside [`temporal-history.md`](temporal-history.md),
which describes the schema, and [`merger-handling.md`](merger-handling.md),
which describes the merger types and the forward-looking admin workflow.

## Background

The temporal history layer (see [`temporal-history.md`](temporal-history.md))
records entity attribute changes and affiliation changes from installation day
forward. Before the temporal layer was installed, the main entity rows
(`Organisation`, `Trust`, etc.) were overwritten in place when attributes
changed, so the version table has no record of past names, addresses, or
affiliations.

There are two recovery paths, depending on how far back the change happened:

- **Within 185 days** — the ODS `/sync` endpoint can return the change. The
  `cron` command's `--time-frame` argument (1–185 days) controls the window.
- **Older than 185 days** — the ODS `/sync` endpoint cannot return the change,
  but the `/organisations/{ods_code}` endpoint returns the full `Succs` and
  `Rels` history regardless of when the events happened. The
  `backfill_successions` and `backfill_trust_memberships` commands use this to
  recover the full merger and membership chain. For historical names and
  addresses (which ODS overwrites in place), the `backfill_*` helpers are used
  with manually-researched dates.

## Part 1 — ODS-driven recovery (within 185 days)

### The `--time-frame` argument on the `cron` command

The `cron` command accepts a `--time-frame` argument (days, 1–185) that is
passed through to `update_organisation_model_with_ORD_changes`. The default is
30 so existing behaviour and the GitHub Action are unchanged.

```bash
# See the last 185 days of changes (no writes)
python manage.py cron --service organisations --dry-run --time-frame 185

# Apply the last 185 days of changes
python manage.py cron --service organisations --time-frame 185
```

### The dry-run report

The dry-run report includes two pieces of context per organisation:

1. **`LastChangeDate`** — the date the change actually happened on the ODS
   side, read from the full organisation record (fetched via
   `get_organisation`), not from the `/sync` list item (which only returns
   `OrgLink`). This lets operators decide whether to apply a change as
   forward-looking (effective today) or as a backfill (effective on the
   `LastChangeDate`).

2. **Succession events** — the `Succs` block from the ODS record, which
   records legal succession (merger, acquisition, split). Each `Succ` has a
   `Type` (`"Successor"` = this org was absorbed into the target;
   `"Predecessor"` = this org absorbed the target), a legal date, and a
   target ODS code. This is surfaced so operators can see whether a
   name/active change is the consequence of a merger and, if so, record it
   manually via the admin or the `backfill_*` helpers rather than via the
   forward-looking sync.

The report format:

```markdown
### Trust RW6 (Pennine Acute Hospitals NHS Trust)

ODS last change date: 2021-10-15
Effective date applied: 2025-08-05

**This trust has succession events (merger/acquisition/split) recorded in ODS:**
- Successor → RM3 (legal date: 2021-10-01)
- Predecessor → RMK (legal date: 2002-04-01)
If the change above is the consequence of this succession, record it via the
admin or the `backfill_*` helpers, not the forward-looking sync.

| Field | Old | New |
|---|---|---|
| name | Pennine Acute Hospitals NHS Trust | New Name |
```

If the ODS response omits `LastChangeDate`, the report shows `unknown`. If
the record has no `Succs` block, the succession section is omitted entirely.

> **Why not auto-populate succession rows from the `Succs` block?** The ODS
> `Succs` semantics are occasionally ambiguous — a single trust can have
> multiple `Successor` entries (e.g. Pennine Acute has two: RM3 and R0A),
> and the `Rels` block (operational/managed relationships) is distinct from
> the `Succs` block (legal succession). Automatically creating succession
> rows from this would sometimes be wrong. The succession tables are
> populated manually via the admin; the report surfaces the ODS data so the
> operator can make the decision.

### Review-gated apply for merger-driven changes

When a change has **recent** ODS succession events (merger / acquisition /
split, within the `time_frame` window) and the sync is run **without**
`--dry-run`, the change is **not applied automatically**. Instead a
`review_callback` is invoked with the entity details, the proposed changes,
and the succession events. The operator must agree (apply as a forward-looking
change, effective today) or refuse (skip, so the change can be handled via
the merger workflow or the `backfill_*` helpers).

Old succession events (outside the `time_frame` window) do **not** trigger the
review — a 12-year-old merger is part of the entity's permanent ODS record
and should not gate a routine website update.

Changes **without** recent succession events are applied automatically at the
ODS `LastChangeDate` (see below), not today.

The `cron` management command wires up an interactive callback that prints
the details and prompts:

```
Review: Trust RW6 (Pennine Acute Hospitals NHS Trust)
ODS last change date: 2021-10-15
Effective date applied: 2025-08-05

Succession events recorded in ODS:
  - Successor → RM3 (legal date: 2021-10-01)
  - Predecessor → RMK (legal date: 2002-04-01)

Proposed changes:
  name: 'Pennine Acute Hospitals NHS Trust' → 'New Name'

If this change is the consequence of the merger above, refuse and handle
it via the admin or the backfill_* helpers.

Apply this change as a forward-looking change? [y/N]
```

If no callback is provided (e.g. running from a script or the GitHub
Action, which uses `--dry-run` anyway), merger-driven changes are **skipped**
with a warning — they must not be applied without human review.

### Non-merger changes applied at ODS LastChangeDate

Non-merger changes (address, website, telephone, etc. — the majority of
what the sync sees) are applied at the ODS `LastChangeDate`, not today.
This means the version row records when the change actually happened on the
ODS side, so the audit trail is accurate. For example, if ODS recorded a
website change on 2024-03-15 and the sync runs on 2025-08-05, the new
`TrustVersion` row will have `valid_from=2024-03-15`, not `2025-08-05`.

If the ODS record omits `LastChangeDate`, the change falls back to today's
date.

This uses the `update_*_attributes` helper (which updates the entity row in
place and closes/opens version rows) with `effective_date` set to the ODS
date — not the `backfill_*` helpers, which are for inserting historical
states without touching the current entity row.

### Manual workflow for genuinely historical changes

The ODS API does not distinguish between a change that happened yesterday
and a change that happened 180 days ago — it returns everything that changed
in the window. For changes that are genuinely historical (the `LastChangeDate`
is well in the past), the manual workflow is:

1. Run `python manage.py cron --service organisations --dry-run --time-frame 185`.
2. Read the report and note the `LastChangeDate` for each change.
3. For changes that should be backfilled at their historical date, use the
   `backfill_*` helpers in a shell with the `LastChangeDate` from the report
   (see Part 2).

A future `--backfill` flag on the `cron` command could automate this, but it
requires a per-change decision (historical vs. current) that the ODS API
does not surface, so it is left as a manual step for now.

## Part 2 — Manual backfill (historical names and attributes)

### The baseline migration

A one-off data migration (already run) created a `*Version` row and a
`*Membership` row for every existing entity, with `valid_from =
installation_date` and `valid_to = None`. This is the baseline. From this
point forward, every change is captured by the temporal helpers.

### Why the admin actions cannot backfill

The admin actions (Edit attributes as of…, Rename…, Deactivate…) are
forward-looking: they snapshot the *current* entity row into the "old"
version row, so the closed row would record the current name for the period
before the change date — which is wrong for a backfill. The closed row
should record the *historical* name, not the current one.

### The `backfill_*` helpers

For mergers and renames older than the recovery window, use the `backfill_*`
helpers in a Django shell. These insert a version row with an explicit
`[valid_from, valid_to)` interval and explicit attribute values, without
touching the current entity row or the current version row. They are
idempotent: if a row already exists for the same interval, it is updated in
place rather than duplicated.

- `backfill_trust_attributes(trust, valid_from, valid_to, **fields)` —
  inserts a `TrustVersion` row.
- `backfill_organisation_attributes(organisation, valid_from, valid_to, **fields)` —
  inserts an `OrganisationVersion` row.
- `backfill_organisation_trust_membership(organisation, trust, valid_from, valid_to)` —
  inserts a historical `OrganisationTrustMembership` row recording a past
  affiliation.

### Worked example: Northern Care Alliance (1 October 2021)

The Northern Care Alliance NHS Foundation Trust (`RM3`) was officially
established on 1 October 2021. The legal merger occurred when Salford Royal
NHS Foundation Trust (also `RM3` — the ODS code was retained) acquired The
Pennine Acute Hospitals NHS Trust (`RW6`) and changed its corporate name to
the Northern Care Alliance NHS Foundation Trust.

Before the temporal layer was installed, the `Trust` row for `RM3` was
overwritten in place when the rename happened, so the version table has no
record of the "Salford Royal" name. To backfill it:

```python
import datetime
from rcpch_nhs_organisations.hospitals.models import Trust, TrustSuccession
from rcpch_nhs_organisations.hospitals.general_functions.membership import (
    backfill_trust_attributes,
    backfill_organisation_trust_membership,
)

nca = Trust.objects.get(ods_code="RM3")      # Northern Care Alliance (current)
pennine = Trust.objects.get(ods_code="RW6")  # Pennine Acute (predecessor)

# 1. Backfill the pre-merger name on RM3. Before 2021-10-01, RM3 was called
#    "Salford Royal NHS Foundation Trust". The current version row (which
#    records "Northern Care Alliance" from installation day forward) is
#    untouched.
backfill_trust_attributes(
    nca,
    valid_from=datetime.date(2001, 4, 1),   # Salford Royal's establishment
    valid_to=datetime.date(2021, 10, 1),    # the rename date
    name="Salford Royal NHS Foundation Trust",
    active=True,
)

# 2. Backfill the acquisition succession row. RM3 (as Salford Royal) acquired
#    RW6 (Pennine Acute) on 2021-10-01. This records *why* the rename happened.
TrustSuccession.objects.create(
    predecessor=pennine,
    successor=nca,
    succession_date=datetime.date(2021, 10, 1),
    succession_type="acquisition",
    notes=(
        "Salford Royal NHS Foundation Trust acquired The Pennine Acute "
        "Hospitals NHS Trust and changed its corporate name to the Northern "
        "Care Alliance NHS Foundation Trust."
    ),
)

# 3. Backfill the child organisations' trust memberships. The organisations
#    that were in Pennine Acute (RW6) before the merger moved to Northern
#    Care Alliance (RM3) on 2021-10-01. Their current membership row points
#    to RM3 (correct for today); this backfills the historical RW6 row.
for org in nca.trust_organisations.all():
    backfill_organisation_trust_membership(
        org,
        trust=pennine,
        valid_from=datetime.date(2001, 4, 1),   # or the org's original join date
        valid_to=datetime.date(2021, 10, 1),    # the merger date
    )

# 4. (Optional) Deactivate Pennine Acute (RW6) with a backfilled closure date.
#    If RW6 is still marked active=True, flip it with a backfilled version row
#    and a closure succession row. Use the deactivate_trust helper but note it
#    is forward-looking — for a backfilled closure, write the rows directly:
from rcpch_nhs_organisations.hospitals.general_functions.membership import backfill_trust_attributes
backfill_trust_attributes(
    pennine,
    valid_from=datetime.date(2021, 10, 1),
    valid_to=None,                            # current state: inactive
    name="Pennine Acute Hospitals NHS Trust",
    active=False,
)
pennine.active = False
pennine.save(update_fields=["active"])
```

After this, an as-of query for `RM3` on, say, 2015-01-01 returns
"Salford Royal NHS Foundation Trust", and the succession table records the
acquisition link from `RW6` to `RM3` on 2021-10-01.

> **Why not the admin?** The admin actions are forward-looking: they close
> the current version row and open a new one from the effective date,
> snapshotting the current entity row into the closed row. For a backfill,
> the closed row would record the *current* name for the period before the
> change date, which is wrong. The `backfill_*` helpers avoid this by
> inserting a row with an explicit interval and explicit values, without
> snapshotting the current row. A future admin action could expose this,
> but it requires a different form (two dates, not one) and a different
> mental model ("record a past state" vs "record a change from today"),
> so it is left to the shell for now.

## Part 3 — Backfilling the full succession history

The 185-day limit on `/sync` does not apply to `/organisations/{ods_code}` —
the full organisation record always includes the complete `Succs` block,
recording every predecessor and successor the entity has ever had, back to
its origin. This makes it possible to recover the **full historical merger
chain** for every entity in the database, regardless of when the mergers
happened.

### The `backfill_successions` command

```
python manage.py backfill_successions --entity trust --dry-run
python manage.py backfill_successions --entity trust
python manage.py backfill_successions --entity organisation --dry-run
```

The command iterates every entity of the given type in the database, fetches
its full ODS record via `/organisations/{ods_code}`, reads the `Succs` block,
and for each missing succession row:

- In `--dry-run` mode: reports the missing row without creating it.
- In non-dry-run mode: prompts the operator with `[y/n/s=skip]` for each row.
  `y` creates the row, `n` refuses it, `s` skips it.

### What the command recovers

For each `Succ` entry in the ODS record:

- The **predecessor and successor entities** (mapped from the `Type`:
  `Successor` means this entity was absorbed into the target, so
  predecessor=this, successor=target; `Predecessor` means this entity
  absorbed the target, so predecessor=target, successor=this).
- The **legal date** of the succession.
- The **succession type** (`merger` or `acquisition`), detected by
  comparing the successor's own `Legal.Start` (when it was established) to
  the event's legal date:
  - `Legal.Start == event date` → `merger` (a new entity was created fresh
    on the merger date; e.g. R1L Essex Partnership from RRD + RWN on
    2017-04-01, R0A Manchester University from RW3 + RM2 on 2017-10-01).
  - `Legal.Start < event date` → `acquisition` (an existing entity absorbed
    another and may have been renamed; e.g. RM3 Northern Care Alliance
    acquired RW6 Pennine Acute on 2021-10-01).
  - `Legal.Start` missing or after the event date → `merger` as a fallback;
    the command logs a warning for the operator to review via the admin.
  `split` and `closure` are not auto-detected by this command: `closure` is
  set by the deactivate helpers, and `split` has no real-world cases yet.
- A **notes** field recording that the row was backfilled from the ODS `Succs`
  block.
- **Closure of the predecessor.** Every ODS succession type (merger /
  acquisition / split / closure) has the predecessor ceasing to exist on the
  legal date, so confirming a row also closes the predecessor: a closure
  `*Version` row is written (`active=False` from the succession date forward)
  and the entity row's `active` flag is flipped. This is the same write the
  backfill-merger admin wizard performs, via the same `backfill_*_attributes`
  helper, so the write path is identical. If the predecessor is already
  inactive (e.g. from a previous run), only the succession row is created —
  the command is idempotent.
- **Successor establishment / name backfill (Pass 2).** The command runs in
  two passes: Pass 1 creates all missing succession rows and closes
  predecessors; Pass 2 backfills the successor's establishment or name-change
  row. The two-pass design decouples the backfill from iteration order — a
  predecessor iterated before its successor would otherwise create the
  succession row and leave nothing for the successor's iteration to do, so
  the backfill would never run.
  - For a **true merger** (`Legal.Start == event date`): no name prompt — a
    new entity never had a different name. Pass 2 backfills an establishment
    row at `Legal.Start` with the successor's current name, replacing the
    baseline-migration row that starts at the baseline date.
  - For an **acquisition** (`Legal.Start < event date`): Pass 2 looks up the
    `(successor_ods_code, succession_date)` pair in the constants tables (see
    "Known acquisitions" below) and applies one of three paths:
    1. **`KNOWN_ACQUISITIONS`** (name changed): auto-backfills the name-change
       row covering `[Legal.Start, rename_date)` with the pre-merger name,
       **without prompting**. `rename_date` is the date the successor adopted
       its post-merger name — the correct `valid_to` for the name-change row.
       ODS sometimes reports a legal succession date that differs by a day or
       two from the operational rename date, so the constants carry an explicit
       `rename_date` when they differ (e.g. RTG: legal 2018-06-30, rename
       2018-07-01).
    2. **`KNOWN_ACQUISITIONS_NO_NAME_CHANGE`** (no name change): skips the name
       backfill silently (counted as 'name unchanged').
    3. **Neither list**: falls back to the `y/n/skip` + date prompt. The prompt
       is **pre-populated from the version table** if the operator has already
       entered the pre-merger name via the admin (the `*Version` row whose
       `valid_to == event date`). ODS overwrites the successor's `Name` in place
       when a rename happens, so the old name is not recoverable from the API —
       the operator must look it up in ODS Trac or another source. If supplied
       (or accepted via the default), a name-change `*Version` row is backfilled
       for the successor covering `[Legal.Start, rename_date)`. If the operator
       leaves the prompt blank (or stdin is closed) and there is no
       pre-populated default, the name backfill is skipped.
    This only applies to `Predecessor` events — for a `Successor` event, this
    entity is the predecessor being closed, not the continuing entity.
    The prompt signposts what was acquired (the predecessor trust(s) and the
    date) so the operator can decide whether a rename happened.
    **The current name is read from the ODS record**, not the entity row —
    ODS always has the post-merger name, while the entity row may be stale
    (if the `cron` sync hasn't run since the rename). If the two differ, the
    command logs a warning and updates the entity row to match ODS so the
    database is consistent with the version rows being written.
    If ODS does not expose a `Legal.Start` for the successor, the command
    falls back to the `valid_from` of the pre-populated version row; if
    neither is available, the operator is prompted for the establishment
    date (look it up in ODS Trac or another source), since it is needed to
    date the name-change row.
  - **Bridging the baseline gap.** When Pass 2 backfills a name-change row
    for an acquisition, it also inserts a **bridging row** covering
    `[rename_date, baseline_date)` with the successor's current name,
    so the version timeline is continuous. Without this, there would be a
    gap between the rename date and the baseline migration date where no
    version row exists — an as-of query for a date in that interval would
    find no row and crash. The bridging row is only inserted if the rename
    date is before the baseline date (which is always true for backfilled
    events). The true-merger path does not need a bridging row: the
    establishment row replaces the baseline row and covers everything from
    the merger date forward.

### What the command does not recover

- The **succession type for `Successor` events.** When the command iterates
  a predecessor (a `Successor` event), it does not have the successor's ODS
  record to hand, so it cannot compare `Legal.Start` to the event date. It
  falls back to `succession_type="merger"` as a placeholder; the operator
  should review and correct via the admin. (The type only matters for the
  name/establishment backfill in Pass 2, which runs on `Predecessor` events
  where the successor's ODS record is available.)
- `split` and `closure` types. `closure` is set by the deactivate helpers
  (admin "Deactivate…" action); `split` has no real-world cases yet. Neither
  is auto-detected by this command.
- The **child organisation reassignments**. The `Succs` block tells us which
  trusts merged, but not which organisations moved from which predecessor to
  which successor. That's in the child organisations' own `Rels` blocks —
  see Part 4 below for the dedicated recovery command.
- The **successor's pre-merger name automatically from ODS.** ODS overwrites
  the `Name` of an active renamed trust in place, so the old name is gone from
  the API. The command recovers it from the `KNOWN_ACQUISITIONS` constants
  table (see "Known acquisitions" below) for trusts that are listed there; for
  trusts not listed, the operator is prompted (see above). If the operator
  skips and the trust is not in the constants, the name must be backfilled
  separately via the admin or the `backfill_*` helpers (see Part 2).
  Renames that are not associated with an ODS `Succs` event (e.g. RW1's
  2011-04-01 rename from Hampshire Partnership to Southern Health) cannot be
  backfilled by this command at all — they must be added manually.

The child organisation reassignments are now recoverable via
`backfill_trust_memberships` (see Part 4).

### Known acquisitions with a pre-merger name change

The table below lists NHS trusts that were formed by **acquisition** (an
existing trust absorbed another and changed its name in the process), where
the pre-merger name differs from the current name and is not recoverable from
ODS. ODS overwrites the `Name` of an active renamed trust in place, so the old
name is gone from the API by the time `backfill_successions` runs.

These entries live in `KNOWN_ACQUISITIONS` in
`rcpch_nhs_organisations/hospitals/constants/known_acquisitions.py`. The
command's Pass 2 looks up each `(successor_ods_code, succession_date)` pair in
this table and, if found, **auto-backfills the name-change row without
prompting**. If the acquisition is not in this table (or in the no-name-change
table below), the command falls back to the `y/n/skip` + date prompt.

The columns are:

- **Legal.Start** — the `valid_from` of the name-change row (the start of the
  interval `[Legal.Start, rename_date)`). This is the successor's own
  establishment date where known; otherwise the earliest date the pre-merger
  name is known to have been in use.
- **Succession date** — the ODS `Succs` legal date (the lookup key, and the
  second half of the `(ods_code, succession_date)` pair the command knows at
  Pass 2 time). ODS sometimes reports a legal date that differs by a day or
  two from the operational rename date.
- **Rename date** — the `valid_to` of the name-change row (the date the
  successor adopted its post-merger name). Shown only when it differs from the
  succession date; otherwise the succession date is used.

Trusts formed by a **true merger** (a new entity with a new ODS code) are not
listed here — a new entity never had a different name, so no name-change row is
needed and the command backfills an establishment row silently. A trust that
was *created* by a true merger and *later* acquired another trust appears here
for the later acquisition only. For example, R0A (Manchester University NHS
Foundation Trust) was created on 2017-10-01 from RW3 + RM2 (true merger,
establishment row) and later acquired RW6 (Pennine Acute) on 2021-10-01
(acquisition, no name change — see the no-name-change table below).

| ODS | Successor (current name) | Pre-merger name | Legal.Start | Succession date | Rename date | Notes |
|---|---|---|---|---|---|---|
| RC9 | Bedfordshire Hospitals NHS Foundation Trust | Luton and Dunstable University Hospital | 2020-04-01 | 2020-04-01 | | acquired Bedford Hospital NHS Trust (RC1) |
| RQ3 | Birmingham Women's and Children's NHS Foundation Trust | Birmingham Children's Hospital NHS Foundation Trust | 2017-02-01 | 2017-02-01 | | acquired Birmingham Women's NHS Foundation Trust (RLU) |
| RDE | East Suffolk and North Essex NHS Foundation Trust | Colchester Hospital University NHS Foundation Trust | 2018-07-01 | 2018-07-01 | | acquired The Ipswich Hospital NHS Trust (RGQ) |
| RTQ | Gloucestershire Health and Care NHS Foundation Trust | 2gether NHS Foundation Trust | 2019-10-01 | 2019-10-01 | | acquired Gloucestershire Care Services NHS Trust (R1J) |
| RAX | Kingston Hospital NHS Foundation Trust | Kingston Hospital NHS Trust | 2024-11-01 | 2024-11-01 | | acquired Hounslow and Richmond Community Healthcare NHS Trust (RY9) |
| REM | Liverpool University Hospitals NHS Foundation Trust | Aintree University Hospital NHS Foundation Trust | 2019-10-01 | 2019-10-01 | | acquired Royal Liverpool and Broadgreen University Hospitals NHS Trust (RQ6) |
| RW4 | Mersey Care NHS Foundation Trust | Mersey Care NHS Trust | 2016-07-01 | 2016-07-01 | | acquired Calderstones Partnership NHS Foundation Trust (RJX) |
| RRE | MIDLANDS PARTNERSHIP NHS FOUNDATION TRUST | South Staffordshire and Shropshire Healthcare NHS Foundation Trust | 2018-06-01 | 2018-05-31 | 2018-06-01 | acquired Staffordshire and Stoke-on-Trent Partnership NHS Trust (R1E). ODS legal date is 31 May; rename was 1 June. |
| RY3 | East of England Community Health and Care NHS Trust | Norfolk Community Health and Care NHS Trust | 2026-04-01 | 2026-04-01 | | acquired Cambridgeshire Community Services NHS Trust (RYV) |
| RNN | North Cumbria Integrated Care NHS Foundation Trust | North Cumbria University Hospitals NHS Trust | 2019-10-01 | 2019-10-01 | | acquired Cumbria Partnership NHS Foundation Trust (RNL) |
| RM3 | Northern Care Alliance NHS Foundation Trust | Salford Royal NHS Foundation Trust | 2001-04-01 | 2021-10-01 | | acquired Pennine Acute Hospitals NHS Trust (RW6) on 2021-10-01; documented in Part 2. |
| RGN | NORTH WEST ANGLIA NHS FOUNDATION TRUST | Peterborough and Stamford Hospitals NHS Foundation Trust | 2017-04-01 | 2017-04-01 | | acquired Hinchingbrooke Health Care NHS Trust (RQQ) |
| RH8 | ROYAL DEVON UNIVERSITY HEALTHCARE NHS FOUNDATION TRUST | Royal Devon and Exeter NHS Foundation Trust | 2022-04-01 | 2022-04-01 | | acquired Northern Devon Healthcare NHS Trust (RBZ) |
| RAL | ROYAL FREE LONDON NHS FOUNDATION TRUST | Royal Free Hampstead NHS Trust | 2014-07-01 | 2014-07-02 | 2014-07-01 | acquired Barnet and Chase Farm Hospitals NHS Trust (RVL). ODS legal date is 2 July; rename was 1 July. |
| RH5 | Somerset NHS Foundation Trust | Somerset Partnership NHS Foundation Trust | 2020-04-01 | 2020-04-01 | | acquired Taunton and Somerset NHS Foundation Trust (RBA) |
| RH5 | Somerset NHS Foundation Trust | Somerset NHS Foundation Trust | 2023-04-01 | 2023-04-01 | | acquired Yeovil District Hospital NHS Foundation Trust (RA4); name unchanged (pre-merger name == current name, so the command skips the backfill). |
| RW1 | HAMPSHIRE AND ISLE OF WIGHT HEALTHCARE NHS FOUNDATION TRUST | Southern Health NHS Foundation Trust | 2011-04-01 | 2024-10-01 | 2024-10-01 | acquired Solent NHS Trust (R1C) on 2024-10-01; renamed from Southern Health NHS FT. Legal.Start is 2011-04-01 (when the 'Southern Health' name was adopted). NOTE: the 2011-04-01 rename (Hampshire Partnership → Southern Health) is NOT in ODS's Succs block for RW1, so this command cannot backfill it — it must be done manually via the admin or the `backfill_trust_attributes` helper. |
| RBN | Mersey and West Lancashire Teaching Hospitals NHS Trust | ST HELENS AND KNOWSLEY TEACHING HOSPITALS NHS TRUST | 2023-07-01 | 2023-07-01 | | acquired Southport and Ormskirk Hospital NHS Trust (RVY) |
| RAJ | MID AND SOUTH ESSEX NHS FOUNDATION TRUST | Southend University Hospital NHS Foundation Trust | 2020-04-01 | 2020-04-01 | | acquired Basildon and Thurrock University Hospitals NHS Foundation Trust and Mid Essex Hospital Services NHS Trust |
| RA9 | TORBAY AND SOUTH DEVON NHS FOUNDATION TRUST | South Devon Healthcare NHS Foundation Trust | 2015-10-01 | 2015-10-01 | | acquired Torbay and Southern Devon Health and Care NHS Trust (R1G) |
| RA7 | UNIVERSITY HOSPITALS BRISTOL AND WESTON NHS FOUNDATION TRUST | University Hospitals Bristol NHS Foundation Trust | 2020-04-01 | 2020-04-01 | | acquired Weston Area Health NHS Trust (RA3) |
| RA7 | Bristol NHS Foundation Trust | University Hospitals Bristol and Weston NHS Foundation Trust | 2026-07-01 | 2026-07-01 | | acquired North Bristol NHS Trust (RVJ) |
| RTG | UNIVERSITY HOSPITALS OF DERBY AND BURTON NHS FOUNDATION TRUST | Derby Teaching Hospitals NHS Foundation Trust | 2018-07-01 | 2018-06-30 | 2018-07-01 | acquired Burton Hospitals NHS Foundation Trust (RJF). ODS legal date is 30 June; rename was 1 July. |
| RYR | UNIVERSITY HOSPITALS SUSSEX NHS FOUNDATION TRUST | Western Sussex Hospitals NHS Foundation Trust | 2021-04-01 | 2021-04-01 | | acquired Brighton and Sussex University Hospitals NHS Trust (RXH) |
| RWW | North Cheshire and Mersey NHS Foundation Trust | WARRINGTON AND HALTON TEACHING HOSPITALS NHS FOUNDATION TRUST | 2026-04-01 | 2026-04-01 | | acquired Bridgewater Community Healthcare NHS Foundation Trust (RY2) |

### Known acquisitions with no name change

The table below lists acquisitions where the successor trust was **not**
renamed. These entries live in `KNOWN_ACQUISITIONS_NO_NAME_CHANGE` in the same
constants file. The command's Pass 2 looks up each
`(successor_ods_code, succession_date)` pair and, if found, **skips the name
prompt silently** (counted as 'name unchanged'). If the acquisition is not in
this table (or in the name-change table above), the command falls back to the
`y/n/skip` + date prompt.

RRK (University Hospitals Birmingham) acquiring RR1 (Heart of England) is
listed here, not in the name-change table, because the only "change" was
casing (Title Case → ALL CAPS), not a real rename.

| ODS | Successor | Succession date | Notes |
|---|---|---|---|
| RQM | CHELSEA AND WESTMINSTER HOSPITAL NHS FOUNDATION TRUST | 2015-09-01 | acquired West Middlesex University Hospital NHS Trust (RFW); name unchanged. |
| RJ1 | GUY'S AND ST THOMAS' NHS FOUNDATION TRUST | 2021-02-01 | acquired Royal Brompton & Harefield NHS Foundation Trust (RT3); name unchanged. |
| R0A | MANCHESTER UNIVERSITY NHS FOUNDATION TRUST | 2021-10-01 | acquired Pennine Acute Hospitals NHS Trust (RW6); name unchanged. (R0A was created by a true merger of RM2+RW3 on 2017-10-01, which takes the establishment-row path; this is the later RW6 acquisition.) |
| RW4 | MERSEY CARE NHS FOUNDATION TRUST | 2018-03-31 | acquired Liverpool Community Health NHS Trust (RY1); name unchanged. |
| RW4 | MERSEY CARE NHS FOUNDATION TRUST | 2021-06-01 | acquired North West Boroughs Healthcare NHS Foundation Trust (RTV); name unchanged. |
| RAL | ROYAL FREE LONDON NHS FOUNDATION TRUST | 2025-01-01 | acquired North Middlesex University Hospital NHS Trust (RAP); name unchanged. (RAL's earlier 2014-07-02 acquisition of RVL is in the name-change table above.) |
| RRK | UNIVERSITY HOSPITALS BIRMINGHAM NHS FOUNDATION TRUST | 2018-04-02 | acquired Heart of England NHS Foundation Trust (RR1); name unchanged (only casing changed: Title Case → ALL CAPS). |


### Worked example

Running `python manage.py backfill_successions --entity trust --dry-run`
would produce output like:

```
Backfilling successions for 137 trust(s)...

  RW6 (PENNINE ACUTE HOSPITALS NHS TRUST)
  Successor → RM3 (NORTHERN CARE ALLIANCE NHS FOUNDATION TRUST)
  Legal date: 2021-10-01
  Suggested succession_type: merger
  This will also close PENNINE ACUTE HOSPITALS NHS TRUST (set active=False from 2021-10-01).
  [dry-run] would create succession row
  [dry-run] would close PENNINE ACUTE HOSPITALS NHS TRUST (active=False from 2021-10-01).

  RW6 (PENNINE ACUTE HOSPITALS NHS TRUST)
  Successor → R0A (MANCHESTER UNIVERSITY NHS FOUNDATION TRUST)
  Legal date: 2021-10-01
  Suggested succession_type: merger
  This will also close PENNINE ACUTE HOSPITALS NHS TRUST (set active=False from 2021-10-01).
  [dry-run] would create succession row
  [dry-run] would close PENNINE ACUTE HOSPITALS NHS TRUST (active=False from 2021-10-01).

Summary:
  Found (missing): 2
done.
```

In non-dry-run mode, each row prompts:

```
Create succession row Pennine Acute → Northern Care Alliance on 2021-10-01 and close Pennine Acute? [y/n/s=skip]
```

For a `Predecessor` event (this entity absorbed the target and is the
continuing entity), the command also prompts for the successor's pre-merger
name **in Pass 2**, after all succession rows have been created. For example,
running on RM3 (which absorbed RW6 and renamed to Northern Care Alliance):

```
  RM3 (NORTHERN CARE ALLIANCE NHS FOUNDATION TRUST)
  Predecessor → RW6 (PENNINE ACUTE HOSPITALS NHS TRUST)
  Legal date: 2021-10-01
  Suggested succession_type: acquisition
  This will also close PENNINE ACUTE HOSPITALS NHS TRUST (set active=False from 2021-10-01).
  NORTHERN CARE ALLIANCE NHS FOUNDATION TRUST may have had a different name before 2021-10-01. Pass 2 will prompt for the pre-merger name (pre-populated from the version table if known); leave blank to skip.
  [dry-run] would create succession row
  [dry-run] would close PENNINE ACUTE HOSPITALS NHS TRUST (active=False from 2021-10-01).
  [dry-run] Pass 2 would backfill NORTHERN CARE ALLIANCE NHS FOUNDATION TRUST's establishment/name row.
```

For a true merger (new entity, `Legal.Start == event date`), the command
reports that no name prompt will be issued and an establishment row will be
backfilled. For example, running on R1L (Essex Partnership, created from RRD
+ RWN on 2017-04-01):

```
  R1L (ESSEX PARTNERSHIP UNIVERSITY NHS FOUNDATION TRUST)
  Predecessor → RRD (NORTH ESSEX PARTNERSHIP UNIVERSITY NHS FT)
  Legal date: 2017-04-01
  Suggested succession_type: merger
  This will also close NORTH ESSEX PARTNERSHIP UNIVERSITY NHS FT (set active=False from 2017-04-01).
  ESSEX PARTNERSHIP UNIVERSITY NHS FOUNDATION TRUST is a new entity created by this merger (Legal.Start == 2017-04-01). No name prompt; an establishment row will be backfilled.
  [dry-run] would create succession row
  [dry-run] would close NORTH ESSEX PARTNERSHIP UNIVERSITY NHS FT (active=False from 2017-04-01).
  [dry-run] Pass 2 would backfill ESSEX PARTNERSHIP UNIVERSITY NHS FOUNDATION TRUST's establishment/name row.
```

In non-dry-run mode, after answering `y` to the main prompt, Pass 2 runs.
For an acquisition in `KNOWN_ACQUISITIONS` (name changed), the name-change
row is auto-backfilled without prompting; for an acquisition in
`KNOWN_ACQUISITIONS_NO_NAME_CHANGE`, the name backfill is skipped silently;
for a true merger, the establishment row is written silently. For example,
RM3 (Northern Care Alliance) acquired RW6 (Pennine Acute) on 2021-10-01 and
is in `KNOWN_ACQUISITIONS`, so Pass 2 auto-backfills the pre-merger name
'Salford Royal NHS Foundation Trust':

```
Create succession row Pennine Acute → Northern Care Alliance on 2021-10-01 and close Pennine Acute? [y/n/s=skip] y
  Created.
  Closed PENNINE ACUTE HOSPITALS NHS TRUST (active=False from 2021-10-01).

Pass 2: backfilling successor name/establishment for 1 event(s)...
  Auto-backfilled NORTHERN CARE ALLIANCE NHS FOUNDATION TRUST name 'Salford Royal NHS Foundation Trust' (2001-04-01 → 2021-10-01) from KNOWN_ACQUISITIONS.
```

For an acquisition not in either constants list, Pass 2 falls back to the
`y/n/skip` + date prompt. The prompt is pre-populated from the version table
if the operator has already entered the pre-merger name via the admin. If the
operator presses Enter at the prompt and a default is shown, the default is
accepted. If the operator leaves the prompt blank (no default, or the name was
unchanged), the name backfill is skipped and the successor's name history is
left as-is. The prompt signposts what was acquired so the operator can decide
whether a rename happened — for example, R0A (Manchester University) acquired
part of RW6 (Pennine Acute) on 2021-10-01 but was not renamed, so it is listed
in `KNOWN_ACQUISITIONS_NO_NAME_CHANGE` and the name backfill is skipped
silently without a prompt.

If the predecessor is already inactive, the prompt and output reflect that
no closure write is needed:

```
  Predecessor Pennine Acute Hospitals NHS Trust is already inactive — only the succession row will be created.
Create succession row Pennine Acute → Northern Care Alliance on 2021-10-01? [y/n/s=skip]
```

## Part 4 — Backfilling child organisation trust memberships

Part 3 recovers the **Layer 3 succession rows** (which trusts merged), but
not the **Layer 2 membership rows** (which child organisations sat under
which trust, and when). The `Succs` block on a trust's record tells us that
`RW6` was absorbed into `RM3` on 2021-10-01, but not which hospitals moved
from `RW6` to `RM3` on that date.

That information lives in the child organisations' own `Rels` blocks. Each
NHS Trust Site (`PrimaryRoleId == RO198`) has a `Rel` with `id == "RE6"`
("is a site of") pointing at its parent NHS Trust (`RO197`), with an
operational `[Start, End]` interval. Unlike the `/sync` endpoint,
`/organisations/{ods_code}` returns the complete `Rels` history regardless
of when the relationship ended, so this recovers memberships that were
overwritten before the temporal layer was installed.

### The `backfill_trust_memberships` command

```bash
# Preview what would be backfilled (no writes)
python manage.py backfill_trust_memberships --dry-run

# Preview with a custom lookback window (default: 5 years)
python manage.py backfill_trust_memberships --dry-run --since 2020-01-01

# Preview the full ODS history (use with care)
python manage.py backfill_trust_memberships --dry-run --all

# Apply with interactive yes/no/skip prompts
python manage.py backfill_trust_memberships
```

The command iterates every `Organisation` in the database, fetches its full
ODS record via `/organisations/{ods_code}`, reads the `Rels` block, and for
each `RE6` rel pointing at an `RO197` target:

- In `--dry-run` mode: reports the missing membership row without creating
  it.
- In non-dry-run mode: prompts the operator with `[y/n/s=skip]` for each
  row. `y` calls `backfill_organisation_trust_membership` (the same helper
  the admin wizard and Part 2 use), `n` refuses it, `s` skips it.

### What the command recovers

For each `RE6` rel on each organisation:

- The **parent trust** (mapped from the rel's `Target.OrgId.extension`).
- The **operational interval** `[valid_from, valid_to)` from the rel's
  `Date` block. If the rel has no Operational date, the command falls back
  to the Legal interval (some older ODS records only carry the Legal one).
- An `OrganisationTrustMembership` row recording that the organisation was a
  member of that trust over that interval.

The command is **idempotent**: if a membership row already exists for the
same `(organisation, trust, valid_from, valid_to)` interval, it is skipped.
This makes it safe to re-run.

### What the command does not recover

- **Trusts not in the database.** If an `RE6` rel points at a trust that
  is not in the database (e.g. a dissolved predecessor that has not been
  created yet), the row is skipped with a warning. Run
  `backfill_successions --entity trust` first — it creates the predecessor
  trust rows (marked inactive) that this command needs to look up.
- **Historical organisation names and addresses.** ODS overwrites these in
  place on the organisation's own record. Only the trust-membership timeline
  is recoverable from `Rels`. For names, use the `backfill_*` helpers (see
  Part 2) or the `backfill_successions` name-prompt.
- **ICB / region / OPEN UK / PDU membership history.** The same `Rels` block
  contains `RE5`/`RE8` rels (ICB commissioning) with dates, so the same
  pattern *could* backfill `OrganisationIntegratedCareBoardMembership`. This
  is left as a follow-up extension; trust memberships are the merger-critical
  ones.

### Relationship to the other commands

The recovery commands are designed to be run in order:

1. **`backfill_successions --entity trust`** (Part 3) — creates the
   predecessor trust rows (marked inactive) and the `TrustSuccession` rows
   linking them to their successors.
2. **`backfill_trust_memberships`** (Part 4) — backfills the
   `OrganisationTrustMembership` rows pointing to those predecessors, so an
   as-of query for a hospital on a pre-merger date returns the predecessor
   trust rather than the current successor.

After this one-off recovery, future mergers (1–2 per year) use the
forward-looking `reassign_organisation_trust` helper, which the admin wizard
and `mergers` command already call. The `backfill_*` commands are not part
of the ongoing sync.

### Worked example

Running `python manage.py backfill_trust_memberships --dry-run --all` would
produce output like:

```
Backfilling trust memberships for 137 organisation(s) (the full ODS history)...

  RAA01 (Barnet Hospital)
  was a site of RVL (Barnet & Chase Farm Hospitals NHS Trust)
  Operational interval: 2010-04-01 → 2014-04-01
  [dry-run] would backfill membership row

  RAA01 (Barnet Hospital)
  was a site of RAL (Royal Free London NHS Foundation Trust)
  Operational interval: 2014-04-01 → now
  [dry-run] would backfill membership row

Summary:
  Organisations processed: 137
  Organisations with RE6 rels: 96
  Found (missing): 142
done.
```

In non-dry-run mode, each row prompts:

```
  Backfill membership RAA01 → RVL (2010-04-01 → 2014-04-01)? [y/n/s=skip]
```

## What this does not solve

The 185-day window is the ODS API's hard limit on the `/sync` endpoint.
`/organisations/{ods_code}` is not subject to that limit — it returns the
full `Succs` and `Rels` history regardless of when the events happened — so
`backfill_successions` and `backfill_trust_memberships` can recover the full
merger and membership chain, not just the last 185 days.

What is **not** recoverable from the ODS API at all is the historical
**names and addresses** of active entities, because ODS overwrites those in
place. Those require the `backfill_*` helpers with manually-researched dates
(as in the Northern Care Alliance example in Part 2). If audit data going
back further needs to be re-run at scale, this would require a one-off import
from ODS Trac bulk dumps — a separate project.

## ODS-divergent organisation codes

ODS is an **administrative** directory: it models how the NHS codes
organisations for national reporting flows (Spine, SUS, CDS), not how
clinicians experience them on the ground. A site can be re-coded, folded
into a parent site record, or issued a parallel code, without the physical
site closing. When that happens, ODS marks the old code `Status: Inactive`
and ends its `RE6` rel on the retirement date — even though the site is
still open and still under the same parent trust.

The backfill commands trust ODS's `Status` and `RE6` end dates as the source
of truth for "is this site active" and "when did this membership end". For
ODS-divergent codes, that is wrong: the membership ends on the ODS
retirement date, and an as-of query for a date after that returns "no
current membership" for a site that is actually still operating.

To handle this, the project maintains a curated list of ODS-divergent codes
in `rcpch_nhs_organisations/hospitals/constants/ods_divergent_codes.py`.
The `Organisation` model carries two fields populated from that list:

- `diverged_from_ods` (boolean) — True if ODS considers this organisation
  Inactive but the RCPCH audit system still uses the code.
- `ods_replacement_code` (nullable char) — the active ODS code for the same
  site, where one exists. Null when ODS folded the site into a parent site
  record rather than issuing a twin.

These fields are populated by migration `0031_ods_divergent_organisations`
and are intended to be surfaced in the admin and API so the consuming
software can identify divergent codes and, when ready, flip its references
from `ods_code` to `ods_replacement_code`.

### Known ODS-divergent codes

| Seeded code | Name | Parent trust | ODS status | ODS closure date | Replacement code | Notes |
|---|---|---|---|---|---|---|
| `R1APF` | COVERCROFT | `R1A` | Inactive | 2023-05-31 | `R1A1R` (COVER CROFT CENTRE) | Same address (Colman Road, Droitwich, WR9 8QU), same parent trust. ODS ran two codes in parallel from 2011-06-22 until `R1APF` was closed on 2023-05-31; `R1A1R` remains active. The consuming software references `R1APF`, so the code is retained and the membership is extended to now. When the consuming software is ready to switch, flip references from `R1APF` to `R1A1R`. |

### Cases considered and left as per ODS

The following seeded codes are also Inactive in ODS, but are **not** flagged
as divergent because they are not surfaced in the consuming software (so
the ODS closure date can stand), or because the consuming software already
uses the active canonical code:

| Seeded code | Name | Reason for not flagging |
|---|---|---|
| `RHW0C` | DINGLEY SPECIALIST CHILDREN'S CENTRE | Not used in consuming software. Active twin `RTH88` exists (identical name, same postcode, same trust). |
| `RTD10` | GREAT NORTH CHILDREN'S HOSPITAL | Consuming software uses `RTD02` (the Royal Victoria Infirmary), the active parent-site record for the same address. ODS folded GNCH into the RVI in 2017 rather than issuing a twin. |
| `RVJT4` | PATCHWAY LOCALITY HUB | Not used in consuming software. Possible active twin `NLX25` (PATCHWAY CLINIC) at the same postcode. |
| `RBTCP` | COMMUNITY PAEDIATRICS | Not used in consuming software. No clear active twin — the candidates at the same postcode are unrelated services. |
| `RATE2` | CHILD DEVELOPMENT CENTRE | Not used in consuming software. No clear active twin — the candidate at the same postcode is a different service (renal). |
| `C1G7Z` | CDC POOLE @ DORSET HEALTH VILLAGE | Genuinely closed (2023-04-30). No active twin. |
| `RY327` | COMMUNITY CHILDRENS SERVICES | Genuinely closed (2024-02-29). No active twin. |

### Adding a new divergent code

1. Confirm the site is still open and still under the same parent trust
   (the seeded `ParentODSCode` should match the ODS `RE6` target — see the
   audit script in the project root, `ods_parallel_audit.py`).
2. Confirm the consuming software references the seeded code and would
   break if it were treated as closed.
3. Add an entry to `ODS_DIVERGENT_ORGANISATIONS` in
   `rcpch_nhs_organisations/hospitals/constants/ods_divergent_codes.py`,
   including `ods_replacement_code` if an active twin exists.
4. Add a row to the "Known ODS-divergent codes" table above.
5. Run the migration (or, for an existing instance, update the
   `Organisation` row directly: `diverged_from_ods=True,
   ods_replacement_code=...`).

### Effect on the backfill

The backfill commands do not currently read `diverged_from_ods`. A
follow-up is to teach `backfill_trust_memberships` to extend the membership
to now (rather than ending it on the ODS retirement date) for flagged
codes. Until then, the membership extension for `R1APF` is a manual data
fix: add an `OrganisationTrustMembership` row with
`valid_from=2023-05-31, valid_to=None`.
