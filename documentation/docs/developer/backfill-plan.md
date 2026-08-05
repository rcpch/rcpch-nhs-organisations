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

### Step 2: Surface the ODS `LastChangeDate` in the dry-run report (implemented)

The dry-run report now includes the ODS `LastChangeDate` per organisation —
the date the change actually happened on the ODS side — alongside the
effective date that would be applied (today). This lets operators decide
whether to apply a change as forward-looking (effective today) or as a
backfill (effective on the `LastChangeDate`).

The `/sync` endpoint already returns `LastChangeDate` in each organisation
object (alongside `OrgLink`); the sync function now reads it and surfaces it
in the report:

```markdown
### Organisation RAA01 (Old Org Name)

ODS last change date: 2024-03-15
Effective date applied: 2025-08-05

| Field | Old | New |
|---|---|---|
| name | Old Org Name | New Org Name |
```

If the ODS response omits `LastChangeDate` (older fixtures did), the report
shows `unknown` rather than crashing.

The non-dry-run path still applies the change with `effective_date=today`
(the forward-looking helpers). To backfill a change at its historical date,
read the report, note the `LastChangeDate`, and use the `backfill_*` helpers
in a shell with that date — see Part 2 below.

### Step 3 (optional, future): A `--backfill` flag

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
- ✅ **Step 2** — `LastChangeDate` in the dry-run report (implemented). The
  sync function reads `LastChangeDate` from the `/sync` response and surfaces
  it in the report alongside the effective date applied.
- ⬜ **Step 3** — Document the manual backfill-from-report workflow in more
  detail (read the report, use the `backfill_*` helpers for genuinely
  historical changes). The worked example in Part 2 below already covers
  this.
- ⬜ **Step 4** (future) — `--backfill` flag, if step 2 shows it is needed.
