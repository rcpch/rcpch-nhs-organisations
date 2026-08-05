# Backfill plan: recovering historical states

## Status

This document covers two related but distinct backfill problems:

1. **ODS-driven recovery** — changes within the 185-day ODS API window that
   can be fetched automatically. **Steps 1 and 2 are implemented** (the
   `--time-frame` argument on the `cron` command, and the ODS `LastChangeDate`
   surfaced in the dry-run report). Step 3 (a `--backfill` flag) is a future
   enhancement.
2. **Manual backfill** — mergers, renames, and closures older than the 185-day
   window that have been overwritten on the main entity row. The `backfill_*`
   helpers exist and are documented here with a worked example.

## Background

The temporal history layer (see [`temporal-history.md`](temporal-history.md))
records entity attribute changes and affiliation changes from installation day
forward. Before the temporal layer was installed, the main entity rows
(`Organisation`, `Trust`, etc.) were overwritten in place when attributes
changed, so the version table has no record of past names, addresses, or
affiliations.

There are two recovery paths, depending on how far back the change happened:

- **Within 185 days** — the ODS API can return the change. The function
  `fetch_updated_organisations(time_frame=30)` in
  `general_functions/ods_update.py` accepts a `time_frame` parameter (days, max
  185) and returns the list of organisations that changed in that period. The
  function `update_organisation_model_with_ORD_changes(dry_run=False, time_frame=30)`
  iterates that list, diffs each against the current database row, and either
  writes through the temporal helpers (non-dry-run) or produces a markdown
  report (dry-run).
- **Older than 185 days** — the ODS API cannot return the change. The
  historical state must be researched manually (e.g. from ODS Trac bulk dumps
  or known merger dates) and inserted via the `backfill_*` helpers.

## Part 1 — ODS-driven recovery (proposal)

### The problem

The `time_frame` parameter exists on `fetch_updated_organisations` and
`update_organisation_model_with_ORD_changes`, but the `cron` management
command that calls them hardcodes the default (30 days). There is no way to
run the sync for a longer window from the command line without dropping into
a shell and calling the function directly:

```python
# Today: the only way to see the last 185 days of changes
from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    update_organisation_model_with_ORD_changes,
)
update_organisation_model_with_ORD_changes(dry_run=True, time_frame=185)
```

This is the function the GitHub Action already calls (with `time_frame=30`
and `--dry-run`), but the longer window — which is the one that matters for
backfill — is not exposed.

### Step 1: Add a `--time-frame` argument to the `cron` command (implemented)

Pass it through to `update_organisation_model_with_ORD_changes`. Validate
that it is between 1 and 185 (the ODS API limit). Default remains 30 so
existing behaviour and the GitHub Action are unchanged.

```python
# cron.py
def add_arguments(self, parser):
    # ... existing args ...
    parser.add_argument(
        "--time-frame",
        type=int,
        default=30,
        help=(
            "Number of days of ODS changes to fetch (1-185). "
            "Default 30. Use 185 for the full recovery window."
        ),
    )

def handle(self, *args, **options):
    time_frame = options["time_frame"]
    if time_frame < 1 or time_frame > ODS_MAX_TIME_FRAME_DAYS:
        raise CommandError(
            f"--time-frame must be between 1 and {ODS_MAX_TIME_FRAME_DAYS} days "
            f"(the ODS API hard limit). Got {time_frame}."
        )
    # ... pass time_frame through to update_organisation_model_with_ORD_changes ...
```

Both of these now work:

```bash
# See the last 185 days of changes (no writes)
python manage.py cron --service organisations --dry-run --time-frame 185

# Apply the last 185 days of changes
python manage.py cron --service organisations --time-frame 185
```

### Step 2: Surface the ODS `LastChangeDate` and succession events in the dry-run report (implemented)

The dry-run report now includes two pieces of context per organisation:

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

The non-dry-run path still applies the change with `effective_date=today`
(the forward-looking helpers). To backfill a change at its historical date,
read the report, note the `LastChangeDate` and any succession events, and use
the `backfill_*` helpers in a shell with that date — see Part 2 below.

> **Why not auto-populate succession rows from the `Succs` block?** The ODS
> `Succs` semantics are occasionally ambiguous — a single trust can have
> multiple `Successor` entries (e.g. Pennine Acute has two: RM3 and R0A),
> and the `Rels` block (operational/managed relationships) is distinct from
> the `Succs` block (legal succession). Automatically creating succession
> rows from this would sometimes be wrong. The succession tables are
> populated manually via the admin; the report surfaces the ODS data so the
> operator can make the decision.

### Step 3 (implemented): Review-gated apply for merger-driven changes

When a change has **recent** ODS succession events (merger / acquisition /
ssplit, within the `time_frame` window) and the sync is run **without**
`--dry-run`, the change is **not applied automatically**. Instead a
`review_callback` is invoked with the entity details, the proposed changes,
and the succession events. The operator must agree (apply as a forward-looking
change, effective today) or refuse (skip, so the change can be handled via
the merger workflow or the `backfill_*` helpers).

Old succession events (outside the `time_frame` window) do **not** trigger the
review — a 12-year-old merger is part of the entity's permanent ODS record
and should not gate a routine website update.

Changes **without** recent succession events are applied automatically at the
ODS `LastChangeDate` (see Step 2a below), not today.

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

### Step 2a (implemented): Non-merger changes applied at ODS LastChangeDate

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

### Step 4 (optional, future): A `--backfill` flag

If step 2 shows that most 185-day changes are genuinely historical (i.e. the
change date is in the past, not today), a future `--backfill` flag could
route the sync through the `backfill_*` helpers instead of the
forward-looking `update_*` helpers. The change would be applied with
`valid_from = LastChangeDate` and `valid_to = None` (closing the current
version row at `LastChangeDate` and opening a new one from that date).

This is left as a future enhancement because:

- It requires a decision per change: is this a historical change that should
  be backfilled, or a current change that should be applied today? The ODS
  API does not distinguish — it returns everything that changed in the
  window. A blanket `--backfill` flag would apply all of them at their
  historical date, which may be wrong for changes that happened yesterday.
- The `backfill_*` helpers currently take explicit `valid_from`/`valid_to`
  values, not a single `effective_date`. Wiring them into the sync requires
  deciding what `valid_to` should be for each change (the date of the *next*
  change, which the sync does not know).

For now, the manual workflow is: run `--dry-run --time-frame 185`, read the
report, and for each change that is genuinely historical, use the
`backfill_*` helpers in a shell with the `LastChangeDate` from the report.

## Part 2 — Manual backfill (implemented)

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

## Part 3 — Backfilling the full succession history (implemented)

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
python manage.py backfill_successions --entity pdu --dry-run
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
- A **placeholder `succession_type` of `merger`** — ODS does not distinguish
  merger/acquisition/split/closure, so the operator should review and correct
  the type via the admin if needed.
- A **notes** field recording that the row was backfilled from the ODS `Succs`
  block.

### What the command does not recover

- The **succession type** (merger vs acquisition vs split vs closure). ODS
  only has `Successor` / `Predecessor`. The command creates rows with
  `succession_type="merger"` as a placeholder.
- The **child organisation reassignments**. The `Succs` block tells us which
  trusts merged, but not which organisations moved from which predecessor to
  which successor. That's in the child organisations' own `Rels` blocks.
- The **predecessor names at the time of the merger**. ODS does not keep
  historical name snapshots.

These require human review via the admin or the `backfill_*` helpers (see
Part 2).

### Worked example

Running `python manage.py backfill_successions --entity trust --dry-run`
would produce output like:

```
Backfilling successions for 137 trust(s)...

  RW6 (PENNINE ACUTE HOSPITALS NHS TRUST)
  Successor → RM3 (NORTHERN CARE ALLIANCE NHS FOUNDATION TRUST)
  Legal date: 2021-10-01
  Suggested succession_type: merger (review and correct via the admin if needed)
  [dry-run] would create succession row

  RW6 (PENNINE ACUTE HOSPITALS NHS TRUST)
  Successor → R0A (MANCHESTER UNIVERSITY NHS FOUNDATION TRUST)
  Legal date: 2021-10-01
  Suggested succession_type: merger (review and correct via the admin if needed)
  [dry-run] would create succession row

Summary:
  Found (missing): 2
done.
```

In non-dry-run mode, each row prompts:

```
Create succession row Pennine Acute → Northern Care Alliance on 2021-10-01? [y/n/s=skip]
```

## What this does not solve

The 185-day window is the ODS API's hard limit. Changes older than 185 days
are not recoverable from the API at all — they require the `backfill_*`
helpers with manually-researched dates (as in the Northern Care Alliance
example above). If audit data going back further needs to be re-run at scale,
this would require a one-off import from ODS Trac bulk dumps — a separate
project.

## Implementation status

- ✅ **Step 1** — `--time-frame` argument on `cron` (implemented). Validates
  1-185, defaults 30, passes through to the sync function.
- ✅ **Step 2** — `LastChangeDate` and succession events in the dry-run report
  (implemented). The sync function reads `LastChangeDate` from the full
  organisation record and surfaces it in the report alongside the effective
  date applied. Succession events from the `Succs` block are also surfaced.
- ✅ **Step 2a** — Non-merger changes applied at ODS `LastChangeDate`
  (implemented). Address, website, telephone, and other routine changes are
  applied at the ODS date, not today, so the version row records when the
  change actually happened.
- ✅ **Step 3** — Review-gated apply for merger-driven changes (implemented).
  Changes with **recent** succession events (within the `time_frame` window)
  are not applied automatically; the operator must agree or refuse via a
  review callback. Changes with only old succession events (outside the
  window) are applied automatically at the ODS date.
- ✅ **Part 3** — `backfill_successions` command (implemented). Iterates every
  entity in the database, fetches its full ODS record, reads the `Succs` block,
  and reports or creates missing succession rows with a yes/no/skip prompt.
  Recovers the full historical merger chain, not just the last 185 days.
- ⬜ **Step 4** (future) — `--backfill` flag on `cron`, if needed.
