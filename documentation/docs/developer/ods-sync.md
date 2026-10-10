---
title: ODS sync — periodic structural reconciliation
author: RCPCH Incubator
---

# ODS sync — periodic structural reconciliation

`reconcile_ods` is the single engine that keeps the local organisational
geography in step with NHS ODS. It treats ODS as the source of truth and
reconciles the database against it across four geography levels — detecting
**mergers, acquisitions, splits, closures, renames, re-parentings, and status
changes** — while **freezing** every superseded name and relationship into the
temporal layer so the as-of read path
(`GET /organisations/{ods_code}/snapshot/?date=…`) returns the geography that
was in force on any past date.

It replaces the overlapping detection surface of the old `cron`,
`backfill_successions`, `backfill_trust_memberships`, `backfill_icb_memberships`,
and `ods_change_report` commands with one code path. Those commands remain as
backward-compatible entry points, but new work should use `reconcile_ods`.

This document is the operational reference: what the command does, how it
writes, and **how often to run it**. For the temporal schema it writes into,
see [`temporal-history.md`](temporal-history.md); for the ODS endpoints it
reads, see [`ods-api.md`](ods-api.md); for the monthly Azure job and GitHub
issue, see [`ods-change-detection.md`](ods-change-detection.md).

## The four levels and the roster policy

| Level | Model | ODS role / source | Roster policy |
|---|---|---|---|
| Organisation (trust/LHB site) | `Organisation` | `RO198` (trust site), `RO144` (LHB site); parent via `RE6` | **Closed set** — succession-follow only |
| Trust | `Trust` | `RO197`; ICB via `RE5`/`RE8` → `RO261` | Full roster — hold all |
| Local Health Board | `LocalHealthBoard` | `RO142` | Full roster — hold all |
| Integrated Care Board | `IntegratedCareBoard` | `RO261` | Full roster — hold all |

The roster policy differs by level because **the organisation set is closed**.
The database holds *every* trust, LHB, and ICB in the UK, but only the
**subset** of organisations (sites) that the audits report against.

- **Trusts / LHBs / ICBs — full reconciliation.** Entities present in ODS but
  not in the DB are detected as roster adds; retired entities are detected for
  closure. The complete set is held at these levels.
- **Organisations — closed set, succession-follow only.** The full
  `RO198`/`RO144` roster is **not** imported. The engine only acts on
  organisations already held: if a held organisation's code has been superseded
  (its `Succs` block names a successor, or its `RE6` parent changed and ODS
  issued a new code), the successor is followed, created, and linked via
  `OrganisationSuccession`, and the old code is deactivated. Organisations that
  are new in ODS but unrelated to any held code are never created.

### Out of scope

- **NHS England Regions** and **Countries** — maintained by hand in the admin.
- **Paediatric Diabetes Units** and **PDU networks** — not tracked by ODS;
  maintained from `Master_PDU_Lookup.xlsx` (see [`pdu-history.md`](pdu-history.md)).
- **OPEN UK (epilepsy) networks** — not an ODS concept.
- **Boundary geometry** — being deprecated in favour of the RCPCH Census Platform.

## The temporal floor: 1 December 2020

The historical layer has a hard floor of **1 December 2020**
(`TEMPORAL_FLOOR`). Nothing earlier is reconstructed.

- **Pre-2020 codes are ignored.** Any entity whose ODS code was already
  inactive before the floor is out of scope entirely — no row, no stub, no
  succession. Succession references that point at a predecessor/target which
  does not exist in the database before the floor are collapsed into a single
  `legacy_skips` count rather than being reported line by line (this is what
  eliminated the ~350 lines of pre-2016 noise in older detection issues).
- **Held entities are reconstructed backward to the floor.** For every held
  entity, the backfill mode walks its ODS `Succs`/`Rels` history backward and
  bakes in every code/name/parent it had on or after 1 December 2020, then
  stops. The walk is bidirectional but bounded: forward to pick up current
  successors of held codes, backward to pick up predecessor codes/names/parents
  that were live on or after the floor.

**Worked example — North Middlesex.** This site shows both the backward
reconstruction *and* the end-date-aware closure logic. The database currently
holds the organisation under the code **`RAPNM`** (ODS `Status=Active`),
parented on North Middlesex University Hospital NHS Trust **`RAP`** (which the
DB already holds as `active=False`). In ODS, `RAPNM` is still stamped
`Status=Active` but carries a **Legal/Operational End of 2024-12-31** and has no
own `Succs`; its parent trust `RAP` was **succeeded by Royal Free London `RAL`
on 2025-01-01**, and the physical site re-opened under a parallel Royal-Free
code (`RAL27`). Two things follow:

- *Backward (floor) reconstruction.* For an as-of date in the covered window the
  layer freezes `RAPNM` under `RAP`: the `RAPNM` organisation row, its
  `OrganisationTrustMembership` → `RAP`, and the `RAP` trust row and its
  memberships are all reconstructed back to the floor (because `RAP` was active
  on 1 December 2020).
- *Forward closure.* Because `RAPNM` has effectively closed (past end date) with
  **no own successor**, the engine does not guess. It bridges via the
  **parent-trust succession** (`RAP` → `RAL`) and surfaces a `parallel-code`
  review item recording that bridge. It deliberately does **not** auto-pick a
  successor site, but it **does surface candidate successor codes** for the
  reviewer. The shared postcode (`N18 1QX`) returns ~90 co-located sites, ~29 of
  them `RO198` sites already parented on the successor trust `RAL` — because ODS
  mints a fresh departmental code (wards, clinics) for every sub-site on the
  merger date. The genuine parallel code is isolated by a **name-free temporal
  discriminator**: of those `RAL` sites, only `RAL27` was *already open before
  `RAPNM` closed* (its own legal start, 2003-04-01, predates the 2024-12-31
  end); the ~28 merger-date departmental codes all start on 2025-01-01 and are
  excluded. So the review item reads "… candidate successor code(s) under RAL:
  RAL27". Names are used only to *order* a bounded set of deep fetches (a
  name-matching site is confirmed first), never as a selection key, because a
  site's name may or may not survive a transfer. A human links the surviving
  code from the review queue (which then records the `OrganisationSuccession`
  and deactivates `RAPNM`).

> Note: in **incremental** mode the organisation-level deep diff only runs for
> codes the `/sync` feed flags in-window, so a *historical* closure like
> `RAPNM` (end-dated in 2024) surfaces under **`--mode backfill`**, not a
> routine incremental run. New closures going forward are `/sync`-flagged in
> their window and so are caught incrementally.

## What is detected, per level

Each entity has three independent timelines that can change — attributes,
relationships, and succession — plus roster presence for the full-roster
levels. The engine detects all of them and routes each to the correct temporal
write.

```mermaid
graph TD
    ODS[ODS source of truth] --> D{Diff per entity}
    D --> A[Attribute change<br/>name, address, active]
    D --> R[Relationship change<br/>parent re-pointing]
    D --> S[Succession event<br/>merger / acquisition / split / closure]
    D --> P[Roster presence<br/>new / missing / status mismatch]
    A --> L1[Layer 1 — Version tables<br/>close + open version row]
    R --> L2[Layer 2 — Membership tables<br/>close + open membership row]
    S --> L3[Layer 3 — Succession tables<br/>+ predecessor active=False<br/>+ successor create]
    P --> Q[PendingOdsChange queue<br/>roster-add / retire]
```

| Change class | ODS signal | Temporal write | Helper |
|---|---|---|---|
| `attribute` (name/address/active) | field diff; `Status` flip | Layer 1 version row closed + opened at the ODS effective date | `update_*_attributes` / `backfill_*_attributes` |
| `relationship` (new parent) | `RE6` (org→trust), `RE5`/`RE8` (trust→ICB) | Layer 2 membership row closed + opened | `reassign_*` / `backfill_*_membership` |
| `succession` (merger/acq/split/closure) | `Succs` block | Layer 3 succession row + predecessor `active=False` + successor baseline | succession helpers via the apply path |
| `superseded-code` | `Succs` on the held org + new `RE6` | `OrganisationSuccession` + new `Organisation` + membership transfer | succession helpers via the apply path |
| `roster-add` (**trust/LHB/ICB only**) | roster list + deep-fetch confirms still open | create entity | roster helpers via the apply path |
| `retire` (**trust/LHB/ICB only**) | `Status` = Inactive, **or** past end date, **or** absent from roster and deep-fetch confirms closed | deactivate entity | `deactivate_*` via the apply path |
| `parallel-code` | held site effectively closed (past end date) with no own successor, but its parent trust was succeeded | review only | human decision (see below) |

### Detection sources

Three ODS data sources are used together (see
[`ods-api.md`](ods-api.md) and `general_functions/reconcile/ods_sources.py`):

1. **`/sync?LastChangeDate=`** — the cheap trigger feed. Lists codes changed
   since a date (≤185 days). Drives *which* entities to deep-fetch on an
   incremental run.
2. **`/organisations?{filter}={role}&Limit=500`, paginated with `Offset`** —
   the roster per level, carrying `Status` and `LastChangeDate`. Used for trust
   / LHB / ICB presence and status reconciliation (organisations are a closed
   set and are not roster-reconciled). Two details matter:
    - **Pagination.** The directory caps a page at 500 rows, so the roster is
      paged with `Offset` until a short page is returned. (The `RO197` trust
      roster is ~544 rows; without paging it truncated at 500 and every entity
      past the first page looked "absent from ODS" — a false retirement.) The
      first page omits `Offset` (ODS rejects `Offset=0` with HTTP 406) and the
      page size is held at 500 (`Limit>500` is incompatible with `Offset`).
    - **ICB role.** Trusts and LHBs are selected by their *primary* role
      (`PrimaryRoleId=RO197` / `RO142`). ICBs are **not** selected by their
      primary role `RO261` ("STRATEGIC PARTNERSHIP"), which is far broader than
      ICBs (it also returns mental-health provider collaboratives, shared care
      records, commissioning alliances — ~125 orgs). The reliable, name-free
      discriminator is the *non-primary* ICB-specific role **`RO318`**, queried
      via `Roles=RO318`, which returns exactly the real Integrated Care Boards.
3. **`/organisations/{ods_code}`** — per-entity detail (`Status`, `Date`
   (Legal/Operational start+end), `Rels`/`RE6`, `Succs`). One deep-fetch returns
   an entity's entire history, so each entity needs only one such call per run
   (results are cached within a run). Drives attribute, relationship, and
   succession diffs; is how superseded organisation codes are followed to their
   successors; and carries the **end date** the status logic depends on (see
   below — the roster list items do not carry it).

### End-date-aware status: trust the end date, not the `Status` flag

The ODS `Status` header is **unreliable**: ODS leaves long-dissolved trusts and
re-coded sites stamped `Status=Active` for years after they actually closed
(e.g. South London Healthcare `RYQ` and NHS Direct `RYH`, both dissolved in
2013, are still `Active` in the directory). Taken at face value, these zombies
produced dozens of false "new entity in ODS" and "absent from ODS" lines.

The authoritative signal is the **Operational/Legal End date**. An entity is
*effectively active* (`ods_sources.is_effectively_active`) only when its
`Status` is `Active` **and** it has no end date (or an end date in the future).
The engine applies this in three places:

- **Roster-add zombie filter.** A roster candidate that is in ODS but not in the
  DB is deep-fetched before it is flagged; if its end date has passed it is
  skipped (it is a long-dead code, not a genuinely new entity). A candidate that
  cannot be deep-fetched is still surfaced — only a *confirmed* past end date
  suppresses it.
- **Retire-by-absence confirmation.** A held entity absent from the (English)
  roster roles is deep-fetched before it is retired. If it is still effectively
  active in ODS it is **not** retired — it simply sits outside the queried roles
  (e.g. a Welsh LHB like Powys `7A7`, or a Crown-dependency site like Jersey
  General `RGT1W`, both of which happen to live in the `Trust` table). Only an
  entity ODS confirms as gone or closed is retired.
- **Organisation closure detection.** A held-active organisation that ODS has
  effectively closed (past end date) is detected even though its `Status` is
  still `Active` — see the North Middlesex example below.

### Rate limiting

ODS tolerates at most **5000 requests per 5 minutes** (~16.6 req/s). The engine
throttles below this with a token-bucket limiter
(`general_functions/reconcile/rate_limit.py`), defaulting to **10 req/s**
(`--rate`). A full backfill deep-scan is a few thousand calls (~215 trusts, ~7
LHBs, 42 ICBs, plus the held organisation subset) and completes in a few
minutes; incremental runs deep-fetch only the handful of entities flagged by
`/sync` or a roster diff.

## The `reconcile_ods` command

```
python manage.py reconcile_ods \
    [--levels organisation,trust,lhb,icb] \
    [--mode incremental|backfill] \
    [--since YYYY-MM-DD] \
    [--dry-run]            # default; detection only, writes nothing
    [--apply]             # auto-apply attribute-only changes; queue the rest
    [--queue]             # with --dry-run: fill the review queue, no temporal writes
    [--report-file PATH] \
    [--check-overlaps] \
    [--rate N] \
    [--upload-blob]
```

| Flag | Default | Meaning |
|---|---|---|
| `--levels` | all four | Comma-separated subset of `organisation,trust,lhb,icb`. |
| `--mode` | `incremental` | `incremental` = changes since the last successful run; `backfill` = deep-fetch every held entity and reconstruct history back to the floor. |
| `--since YYYY-MM-DD` | — | Override the window start. In incremental mode this is the `/sync` window start; in backfill mode it is the temporal floor (the one-off bake uses `2020-12-01`). |
| `--dry-run` | on (implied) | Detection and report only; **writes nothing**. The default when neither `--apply` nor `--dry-run` is given. |
| `--apply` | off | Auto-apply attribute-only changes to the temporal layer **and** queue structural changes. Mutually exclusive with `--dry-run`. |
| `--queue` | off | With `--dry-run`, still write structural deltas to `PendingOdsChange` (but no temporal rows). This is what the monthly Azure job uses. |
| `--report-file PATH` | stdout | Write the categorised markdown report to a file instead of stdout. |
| `--check-overlaps` | off | After reconciling, assert no entity has two open version rows and no overlapping intervals; exit non-zero on any violation. |
| `--rate N` | `10` | ODS request throttle in requests/second. |
| `--upload-blob` | off | Print the report between the `<<<ODS_REPORT_START>>>` / `<<<ODS_REPORT_END>>>` sentinel markers and upload it to Azure Blob Storage. Used by the monthly job; requires the storage env vars (see [`ods-change-detection.md`](ods-change-detection.md)). |

### Write semantics

This is the critical distinction. `--apply` and `--dry-run` are mutually
exclusive, and the default is dry-run.

| Invocation | Temporal layer | `PendingOdsChange` queue | Typical use |
|---|---|---|---|
| `--dry-run` (or no flag) | nothing written | nothing written | **Local verification** — compare detection against ODS by eye. |
| `--dry-run --queue` | nothing written | structural deltas queued | **Monthly Azure job** — fills the review queue and raises the issue. |
| `--apply` | attribute-only changes applied | structural deltas queued | Apply the auto-safe class; route everything structural to review. |

Structural changes (succession, superseded-code, relationship, roster-add,
retire, parallel-code) are **never** applied automatically — they always land
in the `PendingOdsChange` queue for human review. Only the **attribute-only**
class is auto-safe, and only when there is no succession in the window; it is
written at the ODS effective date.

### The categorised report

The report (`general_functions/reconcile/report.py`) groups actionable items
by level and change class, newest and most structural first. Pre-floor legacy
succession references are collapsed into a single count, and un-fetchable
entities are listed as a footnote. **An empty actionable report renders as an
empty string**, which is how the blob → GitHub-issue path knows there is
nothing to report.

## How often to run each mode

### Backfill — one-off, manual

`reconcile_ods --mode backfill --since 2020-12-01` is the **one-off history
bake**. It deep-fetches every held entity and reconstructs the full timeline of
names, relationships, and successions back to the temporal floor. History only
needs to be baked once. The workflow is:

1. `reconcile_ods --mode backfill --since 2020-12-01 --dry-run` — review the
   report.
2. `reconcile_ods --mode backfill --since 2020-12-01 --dry-run --queue` —
   populate the `PendingOdsChange` queue.
3. Review and **Approve & apply** from the admin (see below).
4. `reconcile_ods --check-overlaps` — confirm the bake added no overlaps.

This is a documented manual step, not scheduled.

### Incremental — monthly

`reconcile_ods --mode incremental` is the ongoing cadence, run **monthly** by
the Azure Container Apps Job as
`reconcile_ods --mode incremental --dry-run --queue --upload-blob` (see
[`ods-change-detection.md`](ods-change-detection.md)). Each run only catches
what changed since the last successful run.

The window is **self-adjusting**. `_resolve_window` reads
`OdsSyncRun.last_successful(mode="incremental").synced_through` and scans from
`synced_through − MARGIN_DAYS` (5 days of overlap to catch anything that landed
around the previous boundary). If there is no prior successful run, it falls
back to `DEFAULT_INCREMENTAL_WINDOW_DAYS` (35 days). A `--since` override
bypasses this and covers missed runs. Because the bake has already frozen
history, the monthly window never approaches the 185-day `/sync` ceiling.

## The review queue and admin

Detection fills the **`PendingOdsChange`** queue; a human reviews and applies.
Each detected structural delta is one upserted row, unique on
`(level, ods_code, change_class, effective_date)` so a monthly re-run never
re-queues an already-pending or already-applied change. Statuses are
`pending` → `approved`/`applied` or `dismissed`.

In the Django admin, `PendingOdsChangeAdmin` (grouped by level/change class,
filterable by status) offers two actions:

- **Approve & apply selected changes** — drives
  `general_functions/reconcile/apply.py::apply_pending_change`, which calls the
  **existing** idempotent temporal helpers (`update_*` / `reassign_*` /
  `deactivate_*` / `backfill_*` / succession helpers) in one transaction, then
  stamps `status=applied`, `applied_at`, and `reviewed_by`. Re-approving an
  already-applied row is a no-op. The engine never calls `Model.objects.create`
  on a temporal table directly — there is one apply path.
- **Dismiss selected changes** — requires a free-text reason, then stamps
  `status=dismissed` with the reason and reviewer.

### Parallel active codes and curated divergences

Some sites legitimately carry **two active-looking codes** at once, and ODS
cannot always disambiguate them automatically:

- **Resolvable by end date (the North Middlesex pattern).** One code has a past
  end date and the other is open. The closed code's parent trust was succeeded,
  so the engine emits a `parallel-code` review item carrying the parent-trust
  bridge (`predecessor_trust` → `successor_trust`) plus a `candidate_successors`
  list — active `RO198` sites at the closed code's postcode that are already
  parented on the successor trust **and** were open before the closed code ended
  (a name-free "pre-existing parallel" test that isolates the moved site from the
  departmental codes ODS mints on the merger date; see the North Middlesex
  worked example). The list is for review only — it is never auto-picked, since
  a postcode is not a unique key. The reviewer links the surviving code; applying
  a `parallel-code` flags the old code `diverged_from_ods` (and, when the
  reviewer supplies it, records `ods_replacement_code`) via
  `apply._apply_parallel_code`.
- **Not resolvable by end date (the Wythenshawe pattern).** Both codes are open
  (no end date, both `Status=Active`) — a genuine, persistent divergence. The
  end-date discriminator correctly leaves these **alone** (they are not flagged
  closed). Such known-good divergences are curated in
  `constants/ods_divergent_codes.py` and carried on the `Organisation` row as
  `diverged_from_ods` so the engine never re-flags them.

Every run is recorded as an **`OdsSyncRun`** row (mode, levels, since,
`synced_through`, dry-run flag, `changes_detected`, status, and the stored
report). `OdsSyncRun.last_successful(mode=…)` — the most recent non-dry-run
success — drives the self-adjusting incremental window. `OdsSyncRunAdmin` is
read-only.

For the merger-specific view of this workflow, see
[`merger-handling.md`](merger-handling.md).

## Idempotency and overlap safety

Production already contains rows written by the old `backfill_*` commands, so
the engine must treat those as authoritative and never duplicate them. Two
properties guarantee this:

- **Every Layer 1–3 write goes through the existing idempotent helpers** and
  derives interval endpoints identically to them (same `_parse_ods_date`
  source — Operational.Start falling back to Legal.Start — and the same
  half-open `[valid_from, valid_to)` convention). A second run over the same
  ODS record updates the matching row in place via `update_or_create`, or skips
  it on an `exists()` check, rather than inserting an overlapping duplicate. A
  re-run over already-backfilled data therefore adds **zero** temporal rows and
  **zero** new queue rows.
- **`--check-overlaps`** asserts that no entity has two open (`valid_to IS
  NULL`) version rows and that no two intervals overlap for the same entity. Run
  it before and after the one-off bake to prove the bake introduced no
  overlaps.

## The snapshot read path

The read side is unchanged by `reconcile_ods`. Because every applied change is
frozen into the temporal layer, `GET /organisations/{ods_code}/snapshot/?date=…`
assembles the entity version plus every relationship as of the requested date.
This is the mechanism behind the North Middlesex example above, and the primary
way to verify a run locally: compare the snapshot at a historical date and at
today against ODS.

## Related docs

- [`temporal-history.md`](temporal-history.md) — the Layer 1–3 schema this
  engine writes into.
- [`merger-handling.md`](merger-handling.md) — the merger workflow the review
  queue drives.
- [`backfill.md`](backfill.md) — the legacy one-off recovery commands this
  engine unifies.
- [`ods-change-detection.md`](ods-change-detection.md) — the monthly Azure job
  and GitHub-issue reporting wrapper.
- [`ods-api.md`](ods-api.md) — the ODS endpoints, roles, `Rels`, and `Succs`
  reference underpinning detection.
- [`models.md`](models.md) — the `OdsSyncRun` and `PendingOdsChange` models.
