---
title: How trust mergers are handled
author: Dr Simon Chapman
---

# How trust mergers are handled

This document describes the different types of trust merger that occur in the NHS,
what happens to the trusts and their child organisations in each case, and how each
case is recorded by the temporal history layer. It should be read alongside
[temporal-history.md](temporal-history.md), which describes the schema, and the
[ODS management command](#using-the-ods-management-command) section below for the
practical steps.

Worked examples are drawn from real mergers to make the semantics concrete.

## The three merger types

### 1. Acquisition

One trust acquires another. The acquiring trust retains its ODS code; the
acquired trust is dissolved and relinquishes its code.

**Example:** In 2014, Barnet & Chase Farm Hospitals NHS Trust (RVL) was acquired
by Royal Free London NHS Foundation Trust (RAL). RVL was dissolved; Barnet
Hospital adopted RAL as its parent.

| Element | What happens |
|---|---|
| Acquiring trust (RAL) | Retains ODS code. No change to the trust row. |
| Acquired trust (RVL) | Marked `active=False`. A `TrustSuccession` row is created: predecessor=RVL, successor=RAL, type=acquisition. |
| Child organisations | Reassigned from RVL to RAL. An `OrganisationTrustMembership` row is closed (valid_to set) for RVL and a new one opened for RAL. The `Organisation.trust` FK is updated. |
| Child ODS codes | Usually **retained** (Barnet keeps its org code; only the parent stem changes). If the ODS code does change, see [Organisation succession](#organisation-succession) below. |
| ICB / NHS England region | May change if the acquiring trust is in a different ICB or region. If so, the relevant membership rows are closed and new ones opened. See [Cross-boundary mergers](#cross-boundary-mergers) for the case where a merger spans an ICB boundary. |
| OPEN UK network | May change. Handled the same way via `OrganisationOPENUKNetworkMembership`. |
| PDU | Usually unchanged (the diabetes service continues), but can be reassigned via `OrganisationPaediatricDiabetesUnitMembership`. |

### 2. Full merger

Both predecessor trusts are dissolved and a new entity is created with a new ODS
code.

**Example:** In 2018, Ipswich Hospital NHS Trust (RGQ) and Colchester University
Hospitals NHS Foundation Trust (RDE) merged. Both RGQ and RDE were terminated,
and a new ODS code RJL was established for the merged entity (East Suffolk and
North Essex NHS Foundation Trust).

| Element | What happens |
|---|---|
| Predecessor trusts (RGQ, RDE) | Both marked `active=False`. Two `TrustSuccession` rows are created: RGQ → RJL and RDE → RJL, both type=merger. |
| Successor trust (RJL) | A new `Trust` row is created with the new ODS code. A baseline `TrustVersion` row is created. |
| Child organisations | All child orgs of RGQ and RDE are reassigned to RJL. `OrganisationTrustMembership` rows are closed for the old trusts and opened for RJL. |
| Child ODS codes | May or may not change. If the ODS reissues org codes with the new parent stem, see [Organisation succession](#organisation-succession) below. |
| ICB / NHS England region | The new trust (RJL) sits in one ICB and one region. Child orgs inherit these via new membership rows. |
| OPEN UK network / PDU | As for acquisition. |

### 3. Dissolution with split

A trust is dissolved and its child organisations are split between different
successor trusts. This is the most complex case because the child organisations
move to *different* parents and typically get *new ODS codes*.

**Example:** South London Healthcare NHS Trust (RYQ) was dissolved in 2013. Its
child organisations were split:

- Princess Royal University Hospital (RYQ30) moved to King's College Hospital
  NHS Foundation Trust (RJZ) and became **RJZ30**.
- Queen Elizabeth Hospital in Woolwich (RYQ01) moved to the new merged Lewisham
  and Greenwich NHS Trust (RJ2) and became **RJ201**.

| Element | What happens |
|---|---|
| Dissolved trust (RYQ) | Marked `active=False`. Multiple `TrustSuccession` rows are created: RYQ → RJZ (type=split) and RYQ → RJ2 (type=split). One predecessor, multiple successors. |
| Successor trusts (RJZ, RJ2) | May already exist (RJZ) or be newly created (RJ2). If new, a `Trust` row + baseline `TrustVersion` is created. |
| Child organisations | Each child is reassigned to its specific successor trust. `OrganisationTrustMembership` rows are closed for RYQ and opened for the relevant successor. |
| Child ODS codes | **Change.** The child gets a new ODS code reflecting the new parent stem (RYQ30 → RJZ30, RYQ01 → RJ201). This is an organisation-level succession — see below. |
| ICB / NHS England region | May differ between the successor trusts. Each child inherits its new parent's ICB and region. |
| OPEN UK network / PDU | As for acquisition. |

## Organisation succession

In the acquisition and full-merger cases, child organisations usually **retain
their ODS code** — only the parent trust changes. This is handled cleanly by
`OrganisationTrustMembership`: close the old row, open a new one pointing to the
successor trust. The `Organisation` row is unchanged.

In the split case (and sometimes in the other cases), the child organisation
gets a **new ODS code** because its parent stem has changed (RYQ30 → RJZ30).
The ODS treats this as a new organisation: the old code ceases to exist and a
new code is created. But from an audit perspective, RJZ30 in 2014 is the *same
physical hospital* as RYQ30 in 2012 — the audit data needs to trace that chain.

This is recorded by the `OrganisationSuccession` table, which links a
predecessor organisation to its successor with a date and a type. The
`code_change` type covers the case where an organisation's ODS code changes but
it remains under the same parent trust (a pure rename/recode by ODS).

When an organisation succession occurs:

1. The old `Organisation` row (e.g. RYQ30) is marked `active=False`.
2. A new `Organisation` row (e.g. RJZ30) is created with the new ODS code.
3. An `OrganisationSuccession` row links them.
4. The new organisation inherits the old one's relationships (ICB, region, OPEN
   UK network, PDU, London borough, LAD, LSOA) via new baseline membership rows.
5. The new organisation's `OrganisationTrustMembership` points to the successor
   trust (RJZ), not the dissolved one (RYQ).

## Cross-boundary mergers

Most mergers happen within a single ICB and NHS England region, in which case
the child organisations' ICB and region memberships simply follow the successor
trust. A merger that crosses an ICB or region boundary is more nuanced.

**Example:** In 2020, University Hospitals Bristol NHS Foundation Trust acquired
Weston Area Health NHS Trust. UH Bristol was based within the Bristol, North
Somerset and South Gloucestershire (BNSSG) ICB footprint; Weston General
Hospital was part of Somerset ICB. After the merger, the combined trust
(University Hospitals Bristol and Weston, UHBW, RA7) sat within BNSSG as its
**host ICB**, but Somerset ICB retained commissioning responsibilities for
Weston General Hospital as an **associate ICB**.

The current schema models a single ICB per trust via
`TrustIntegratedCareBoardMembership` (and a single ICB per organisation via
`OrganisationIntegratedCareBoardMembership`). This is sufficient for the common
case and keeps reporting simple: every trust and every organisation reports to
exactly one ICB at any point in time.

The host/associate distinction is **not** modelled. If it becomes necessary for
commissioner reporting in future, it would be added as a separate concept (for
example a `role` field on the membership, or a dedicated associate-ICB table)
rather than by allowing two current ICB memberships per trust. For now, the
convention is:

- The merged trust's `TrustIntegratedCareBoardMembership` points to the **host**
  ICB (BNSSG in the example).
- Each child organisation's `OrganisationIntegratedCareBoardMembership` points
  to the ICB that commissions *that organisation*. So Weston General Hospital
  would point to Somerset, while the rest of UHBW's sites would point to BNSSG.

This keeps the trust-level membership unambiguous (one host ICB) while allowing
per-organisation commissioning accuracy, which is what audit reports need. The
host/associate distinction at trust level is deferred until there is a concrete
reporting requirement.

## Other relationship changes during a merger

When a trust merger occurs, the child organisations' other relationships may
also change. The table below summarises which membership tables are involved:

| Relationship | When it changes during a merger | Membership table |
|---|---|---|
| Trust / LHB | Always (the point of the merger) | `OrganisationTrustMembership` / `OrganisationLocalHealthBoardMembership` |
| ICB | If the successor trust is in a different ICB | `OrganisationIntegratedCareBoardMembership` |
| NHS England region | If the successor trust is in a different region | `OrganisationNHSEnglandRegionMembership` |
| Trust → ICB | If the successor trust is in a different ICB | `TrustIntegratedCareBoardMembership` |
| Trust → NHS England region | If the successor trust is in a different region | `TrustNHSEnglandRegionMembership` |
| OPEN UK network | If the successor trust is allocated to a different network | `OrganisationOPENUKNetworkMembership` |
| PDU | Rarely, but possible if the diabetes service is reorganised | `OrganisationPaediatricDiabetesUnitMembership` |
| London borough / LAD / LSOA | Never (these are geographic, not organisational) | — |

The geographic relationships (London borough, LAD, LSOA) do not change during a
trust merger because they are determined by the organisation's physical
location, which does not move.

## Rename and closure

Two non-merger cases that the succession tables also handle:

### Rename

A trust changes its name but retains its ODS code. This is **not** a succession —
it is an attribute change, handled by `TrustVersion` (close the old version, open
a new one with the new name). No `TrustSuccession` row is created.

An organisation can also be renamed (new name, same ODS code). Handled by
`OrganisationVersion`.

### Closure

A trust closes with no successor. The trust is marked `active=False` and a
`TrustSuccession` row is created with `succession_type="closure"` and
`successor=None`, recording *why* the trust closed (e.g. "closed through poor
quality of care") in the `notes` field. Its child organisations are either
closed too or reassigned to other trusts (which would be recorded as a split if
they go to multiple successors).

In the admin, use the **Deactivate…** action on the trust change page. It
performs both writes in one transaction (Layer 1 version row with
`active=False`, Layer 3 closure succession row) and requires a confirmation
checkbox plus a free-text reason, because once inactive the trust is hidden
from default lists. If a closed trust's children are redistributed, each
redistribution is recorded as a separate split succession with the relevant
successor.

## Using the management commands

Two commands are involved in mergers:

- `reconcile_ods` detects structural drift against ODS (successions,
  re-parentings, superseded codes, parallel active codes, roster additions,
  status changes) and stages it in the `PendingOdsChange` admin review queue.
  It **supersedes** the old `cron --service organisations` sync. See
  [ods-sync.md](ods-sync.md) for the full engine reference and
  [ods-change-detection.md](ods-change-detection.md) for the monthly Azure job.
- `mergers` creates or deletes `Organisation` rows from the Spine. It is
  unchanged by the temporal rework — it still creates baseline temporal rows
  (`OrganisationVersion` plus the relevant membership rows) so a new
  organisation has history from creation day forward.

### Detecting changes from ODS

The `reconcile_ods` engine replaces `cron` as the single entry point for
detecting ODS drift across the organisation, trust, Local Health Board, and
ICB levels. It compares the live ODS API against the database and emits a
categorised report. Run with `--dry-run` to see what ODS has published before
anything is written:

```bash
python manage.py reconcile_ods --mode incremental --dry-run
```

Structural changes (successions, re-parenting, roster-adds, retirements,
parallel codes) are **only ever queued** for human review, never
auto-applied. Attribute-only changes with no succession in the window are
the one class that `--apply` writes automatically:

```bash
python manage.py reconcile_ods --mode incremental --apply
```

To fill the admin review queue without writing any temporal rows (the
monthly job's mode):

```bash
python manage.py reconcile_ods --mode incremental --dry-run --queue
```

Each detected structural delta lands as one `PendingOdsChange` row, unique
on `(level, ods_code, change_class, effective_date)` so a monthly re-run
never re-queues an already-pending or already-applied change. ODS does not
surface succession relationships unambiguously, so the queue is for review
only — applying a merger is a human-confirmed step from the admin (see
[User steps for implementing mergers](#user-steps-for-implementing-mergers)).

### One-off backfill (full history re-scan)

To catch up on mergers and changes that were published before the temporal
layer was installed, run a full-history re-scan. `--mode backfill`
deep-fetches every held entity's full ODS record (the
`/organisations/{ods_code}` endpoint, which is not subject to the 185-day
limit) rather than the `/sync` window:

```bash
python manage.py reconcile_ods --mode backfill --dry-run --report-file ods_backfill_changes.md
```

Review the report to identify which trusts have merged, been renamed, or
closed, then apply attribute drift and queue structural changes:

```bash
python manage.py reconcile_ods --mode backfill --apply
```

> **Note:** `reconcile_ods` records *forward-looking* changes and only ever
> **queues** structural changes — it never reconstructs multi-interval
> history. To reconstruct the complete `[valid_from, valid_to)` history from
> the ODS `Rels`/`Succs` blocks, use the `backfill_*` commands (see
> [database_maintenance.md](database_maintenance.md)). On a fresh database
> you need the history first, so run the backfills before you start relying
> on `reconcile_ods`.

For mergers older than the temporal floor (1 December 2020), the ODS
`/sync` endpoint cannot help. Source the dates from the NPDA's own records,
from the ODS Trac bulk data files (see
[NHS Digital ODS data downloads](https://digital.nhs.uk/services/organisation-data-service/data-downloads)),
or from the issues pages of the NPDA and Epilepsy12 projects. The period
from 2023 onwards is the priority for audit reporting.

### Ongoing sync schedule

After the one-off backfill, the ongoing reconciliation only needs the
self-adjusting incremental window and runs monthly. The GitHub Action is
scheduled monthly (07:00 UTC on the 1st) and runs
`reconcile_ods --mode incremental --dry-run --queue --upload-blob` against
production, filling the review queue and opening a GitHub issue if changes
are detected (see [ods-change-detection.md](ods-change-detection.md)). A
manual pass can be run on demand:

```bash
python manage.py reconcile_ods --mode incremental --dry-run --queue
```

### Creating organisations from a merger

When a merger produces a new organisation (either a new child under an existing
trust, or a new child under a newly created successor trust), create it from the
Spine:

```bash
python manage.py mergers --organisations RJZ30 RJ201 --create
```

This looks up each ODS code on the Spine, creates the `Organisation` row, and
creates baseline temporal rows (`OrganisationVersion` plus the relevant
`OrganisationTrustMembership` / `OrganisationIntegratedCareBoardMembership` /
`OrganisationNHSEnglandRegionMembership` / `OrganisationOPENUKNetworkMembership`
/ `OrganisationPaediatricDiabetesUnitMembership`) so the new organisation has
history from creation day forward. Use `--dry-run` first to preview:

```bash
python manage.py mergers --organisations RJZ30 RJ201 --create --dry-run
```

### Recording the succession links

The `mergers` command creates the organisation rows and their baseline
memberships, but the succession links themselves (`TrustSuccession`,
`OrganisationSuccession`, `PaediatricDiabetesUnitSuccession`) are recorded
through the admin — either by approving a queued `succession` change from
`reconcile_ods`, or by using the merger wizards on the entity's change page
(see [User steps for implementing mergers](#user-steps-for-implementing-mergers)).
ODS succession semantics are occasionally ambiguous, so a human should
confirm the predecessor → successor mapping.

> **Note:** a `superseded-code` change in the review queue *does* create the
> successor organisation when approved — it deep-fetches the successor from
> ODS and writes the baseline rows, because it follows the closed-set chain
> forward. A plain `roster-add`, by contrast, never creates an organisation
> (organisations are a closed, seeded set); use `mergers --create` for those.

### Deleting organisations

When an organisation ceases to exist (its ODS code is terminated), it can be
deleted. The command prompts for confirmation and lists the organisation's
relationships before deleting:

```bash
python manage.py mergers --organisations RYQ30 RYQ01 --delete
```

> **Caution:** deleting an organisation that is referenced by a succession row
> is prevented by `on_delete=PROTECT`. Mark the organisation `active=False`
> instead of deleting it if it is a predecessor in a succession, so that the
> audit chain remains intact.

## PDU mergers

Paediatric Diabetes Units (PDUs) can merge in the same ways trusts do: one
PDU can acquire another, two PDUs can merge into a new PZ code, or a PDU can
be split. PDU mergers are recorded with `PaediatricDiabetesUnitSuccession`
and the child organisations' PDU membership is updated via
`OrganisationPaediatricDiabetesUnitMembership`.

Unlike trust mergers, PDU mergers do **not** change the child organisation's
ODS code — the hospital keeps its ODS code, only the PZ code it reports to
changes. So no `OrganisationSuccession` row is needed for a PDU merger; only
the PDU membership rows are closed and reopened.

### Worked example: PZ216 + PZ125 → PZ253 (January 2026)

In January 2026, PZ216 (Tunbridge Wells Hospital) and PZ125 (Maidstone
Hospital) merged to create PZ253 (Maidstone and Tunbridge Wells NHS Trust).

| Element | What happens |
|---|---|
| Predecessor PDUs (PZ216, PZ125) | Both marked `active=False`. Two `PaediatricDiabetesUnitSuccession` rows are created: PZ216 → PZ253 and PZ125 → PZ253, both type=merger. |
| Successor PDU (PZ253) | A new `PaediatricDiabetesUnit` row is created with the new PZ code. A baseline `PaediatricDiabetesUnitVersion` row is created. |
| Child organisations | The organisations previously reporting to PZ216 and PZ125 (e.g. RWFTW, RWF03) are reassigned to PZ253. `OrganisationPaediatricDiabetesUnitMembership` rows are closed for the old PDUs and opened for PZ253. The `Organisation.paediatric_diabetes_unit` FK is updated. |
| Child ODS codes | **Retained.** The hospitals keep their ODS codes; only the PDU membership changes. No `OrganisationSuccession` row is created. |
| Paediatric Diabetes Network | The successor PDU inherits a network via `PaediatricDiabetesUnitNetworkMembership`. If the predecessor PDUs were in different networks, a decision is needed on which network the successor joins; this is recorded manually. |
| Trust / ICB / region | Unchanged — a PDU merger does not move hospitals between trusts. |

### Worked example: PZ086 + PZ131 → PZ254 (April 2026)

In April 2026, PZ086 and PZ131 merged to create PZ254 (North West Anglia NHS
Foundation Trust). The same pattern applies as above: both predecessors are
marked `active=False`, two `PaediatricDiabetesUnitSuccession` rows link them
to PZ254, and the child organisations' PDU memberships are reassigned to
PZ254.

### Relationship to the hardcoded `organisations` property

The `PaediatricDiabetesUnit.organisations` property currently contains
hardcoded special cases for past mergers (PZ003, PZ216, PZ125, PZ080,
PZ141, and others). These map a PZ code to a fixed list of ODS codes
because the membership was not modelled temporally. Once PDU mergers are
recorded through the temporal layer, these hardcoded cases can be replaced
by querying `OrganisationPaediatricDiabetesUnitMembership` as of the
relevant date. The hardcoded cases should be removed as mergers are
migrated into the temporal layer, to avoid two sources of truth.

### Backfilling previous PDU mergers

The temporal layer only records changes from installation day forward. To
backfill the previous PDU mergers that are currently hardcoded in the
`organisations` property, run the `backfill_pdu_successions` management
command. This command reads the curated PDU history from
`Master_PDU_Lookup.xlsx` (the NPDA team's authoritative contact database,
committed to the constants folder) and writes the full PDU entity history
into the temporal layer: `PaediatricDiabetesUnitVersion` rows,
`PaediatricDiabetesUnitNetworkMembership` rows, lead-organisation
`OrganisationPaediatricDiabetesUnitMembership` rows, and
`PaediatricDiabetesUnitSuccession` rows. See
[`pdu-history.md`](pdu-history.md) for the full design and usage guide.

The merger dates and original establishment dates for these PDUs are not
available from the ODS — PDUs are not tracked by the ODS at all. They are
maintained manually by RCPCH. The ODS is used only for trusts, ICBs, and
organisations. The dates are sourced from the NPDA's own records, encoded
as NPDA audit years in the spreadsheet.

This backfill is a one-off project, not an ongoing pattern. Once it is
done, the monthly `reconcile_ods` pass and the manual admin workflow keep the
temporal layer up to date for future mergers.

## User steps for implementing mergers

Mergers are now handled through two complementary admin surfaces: the **ODS
review queue** (`PendingOdsChange`), which is where `reconcile_ods` lands
structural changes it has detected against ODS, and the **merger wizards** on
each entity's change page, which a human can drive directly for forward events
the engine has not (or cannot) detect. Both paths call the same temporal
helpers, so the writes are identical and idempotent.

### Driven from the ODS review queue (`reconcile_ods`)

The `reconcile_ods` engine (see [ods-sync.md](ods-sync.md)) detects succession
events, child re-pointing, superseded organisation codes, parallel active
codes, roster additions, and status changes against ODS, and lands each one as
a `PendingOdsChange` row for review. In the admin, the `PendingOdsChange`
changelist (grouped by status, level, and change class, filterable) offers two
actions:

- **Approve & apply** — drives
  `general_functions/reconcile/apply.py::apply_pending_change`, which
  dispatches to a handler per change class and calls the existing idempotent
temporal helpers in one transaction, then stamps `status=applied`,
  `applied_at`, and `reviewed_by`. Re-approving an already-applied row is a
  no-op.
- **Dismiss (with a required reason)** — for a detected delta the team decides
  not to apply (e.g. a curated ODS divergence). Stamps `status=dismissed` with
  the reason and reviewer.

The change classes and what applying each one does:

| Change class | What it is | What **Approve & apply** does |
|---|---|---|
| `attribute` | A current attribute (name, address, telephone, …) differs from ODS | Calls `update_<entity>_attributes` (closes the current version row, opens a new one). Usually auto-applied by `reconcile_ods --apply`; queued only when a succession is also in the window. |
| `relationship` | A re-parenting (organisation → trust, or trust → ICB) | Calls `reassign_organisation_trust` / `reassign_trust_integrated_care_board`. Raises `ApplyError` if the new parent is not in the database — apply the matching `roster-add` first. |
| `succession` | A merger / acquisition / split / closure where both predecessor and successor are in the database | Creates the `*Succession` row and closes the predecessor (`active=False` via `update_<entity>_attributes`). Raises `ApplyError` if the target is not in the database. |
| `superseded-code` | An organisation is closed in ODS and its own `Succs` names a successor code | Deep-fetches the successor from ODS, creates the `Organisation` row (with baseline temporal rows) if missing, links via `OrganisationSuccession` (type=`code_change`), re-points it to its current parent trust, and closes the predecessor. |
| `roster-add` | A trust / LHB / ICB is active in ODS but missing from the database | Creates the entity row. (Organisations are a closed set — they are never roster-added; use `mergers --create` or approve a `superseded-code` instead.) |
| `retire` | An entity is active in the database but closed/inactive in ODS with no successor | Calls `deactivate_<entity>` (organisation/trust) or `update_integrated_care_board_attributes(active=False)` (ICB). |
| `parallel-code` | An organisation is closed in ODS but has no own successor, and its parent trust was succeeded — the site likely re-opened under a parallel code beneath the successor trust (the North Middlesex pattern) | Flags the old code `diverged_from_ods` and, when the reviewer supplies it, records `ods_replacement_code`. Does **not** auto-pick the successor site. |

When a handler needs an operator decision it raises `ApplyError` with
guidance rather than guessing — for example, a `succession` whose target is
not yet in the database tells you to apply the matching `roster-add` first,
then re-approve. The failed row stays `pending` so it can be re-tried once the
blocker is cleared.

### Parallel active codes

Some sites legitimately carry **two active-looking codes** at once, and ODS
cannot always disambiguate them automatically. The engine handles both
patterns:

- **Resolvable by end date (the North Middlesex pattern).** One code has a past
  end date and the other is open. The closed code's parent trust was
  succeeded, so the engine emits a `parallel-code` review item carrying the
  parent-trust bridge (`predecessor_trust` → `successor_trust`) plus a
  `candidate_successors` list — active sites at the closed code's postcode
  that are already parented on the successor trust **and** were open before
  the closed code ended (a name-free "pre-existing parallel" test that
  isolates the moved site from the departmental codes ODS mints on the merger
  date). The list is for review only — it is never auto-picked, since a
  postcode is not a unique key. The reviewer confirms the surviving code and,
  if they want the audit to remap, supplies the `ods_replacement_code` when
  approving; applying flags the old code `diverged_from_ods`.
- **Not resolvable by end date (the Wythenshawe pattern).** Both codes are
  open (no end date, both `Status=Active`) — a genuine, persistent
  divergence. The end-date discriminator correctly leaves these **alone**
  (they are not flagged closed). Such known-good divergences are curated in
  `constants/ods_divergent_codes.py` and carried on the `Organisation` row
  as `diverged_from_ods` so the engine never re-flags them.

See [ods-sync.md § Parallel active codes and curated
divergences](ods-sync.md#parallel-active-codes-and-curated-divergences) for
the full detection detail.

### Merger wizards (forward events, on the entity change page)

For a merger or acquisition happening now or in the future — whether or not
`reconcile_ods` has detected it — use the wizards on the entity's change page.
Each wizard performs all the temporal writes for its case in one transaction.

| Wizard | Where | What it does in one transaction |
|---|---|---|
| **Acquire another trust…** | Trust change page | A absorbs B: `TrustSuccession` (type=acquisition), close B's version row + flip `B.active=False`, reassign every active child org of B to A, optionally rename A (records a separate rename succession row). Does **not** call `deactivate_trust` on B — the acquisition succession row is the audit record, so a second closure row is not written. |
| **Acquire another PDU…** | PDU change page | Same pattern for PDUs, plus sets the acquirer's `lead_organisation` and `name_source`. Warns if the predecessor PZ code still has a hardcoded case in `PaediatricDiabetesUnit.organisations` / `primary_organisation`. |
| **Merge into a new PDU…** | PDU change page | A + B dissolve into a new C: create C (`PaediatricDiabetesUnit` + baseline `PaediatricDiabetesUnitVersion`), open a `PaediatricDiabetesUnitNetworkMembership` for C, two `PaediatricDiabetesUnitSuccession` rows (A → C, B → C, type=merger), close + deactivate both predecessors, reassign all children of A and B to C, set C's `lead_organisation`. PDUs are not tracked by ODS, so PZ code, name, and network are manual entry. |
| **Backfill merger…** | Trust change page | For a *historical* trust merger/acquisition/split that happened before the temporal layer was installed: creates the predecessor `Trust` row if it is missing (with `active=False` + baseline version rows), backfills the predecessor's historical name and closure, and creates the `TrustSuccession` row. Does **not** backfill child organisation memberships — use the **Backfill trust membership…** action on each organisation afterwards. A "Validate ODS code" button fetches the predecessor's ODS record to pre-fill the name and dates (informational only — the operator is the source of truth for the historical name). |

### Other admin actions on the entity change page

The change page also carries the actions that support the surrounding
workflow. Each is signposted by a banner at the top of the form that explains
when to use it instead of editing the row directly:

- **Edit attributes as of…** — a forward attribute change (address, telephone,
  website, …). Closes the current version row and opens a new one dated to
  the change. `active` is intentionally excluded — deactivation is a business
  event with audit implications and belongs to the Deactivate… action.
- **Rename…** (Trust, PDU) — a name change with the same ODS code. Performs a
  version update **and** writes a `*Succession` row (type=`rename`), so the
  rename is in the audit trail, not just the version history.
- **Deactivate…** — a closure with no successor. Writes a version row with
  `active=False` **and** a `*Succession` row (type=`closure`,
  `successor=None`), recording *why* the entity closed in the `notes` field.
  Requires a confirmation checkbox and a free-text reason. This is the only
  sanctioned way to flip `active` to False. (For a predecessor being absorbed
  in a merger, use the acquisition wizard instead — the acquisition
  succession row is the audit record, so a second closure row is not
  written.)
- **Backfill attributes…** — a historical state with an explicit
  `[valid_from, valid_to)` interval (for recovering state overwritten before
  the temporal layer was installed).
- **Backfill trust membership…** (Organisation only) — a historical trust
  affiliation with an explicit interval.
- **Reassign to a new trust** (Organisation changelist action) — reassigns
  the selected organisations to a new trust, closing the old
  `OrganisationTrustMembership` row and opening a new one. For a full merger,
  filter the changelist by the predecessor trust, select all its children,
  and apply the action. (The acquisition wizard does this automatically for
  every child of the acquired trust.)

### Succession admin pages (historical backfill and ambiguous cases)

The `TrustSuccession`, `OrganisationSuccession`, `PaediatricDiabetesUnitSuccession`,
and `IntegratedCareBoardSuccession` admin pages have full create/edit forms
(predecessor dropdown, successor dropdown, date picker, type dropdown, notes
field). A banner on each changelist signposts users to the wizards for forward
events, and reserves direct row creation for **historical backfill** (events
before the temporal layer was installed) or **ambiguous cases the wizards
cannot handle** (e.g. a split where children move to different successors —
there is no single-wizard split action yet).

### View history

Each entity's change page shows read-only history inlines: the `*Version`
timeline (attribute history) and the `*Membership` timeline (relationship
history), plus Predecessors / Successor inlines for the succession rows. The
succession inlines are hidden when empty, so an active trust formed by a
merger shows its predecessors but not an empty "Successor" section.

### PDU merger workflow

To record a PDU merger (e.g. PZ216 + PZ125 → PZ253), use the **Merge into a
new PDU…** wizard on one of the predecessor PDUs' change pages. It performs
steps 1–5 below in one transaction; step 6 is a follow-up code change:

1. **Create the successor PDU** with a baseline `PaediatricDiabetesUnitVersion`
   row.
2. **Open the `PaediatricDiabetesUnitNetworkMembership`** for the successor.
3. **Create the two `PaediatricDiabetesUnitSuccession` rows** (one per
   predecessor, type=merger).
4. **Close + deactivate both predecessors** (`active=False`).
5. **Reassign all child organisations** of both predecessors to the successor,
   and set the successor's `lead_organisation`.
6. **Remove any hardcoded special case** for the predecessor PZ codes in the
   `PaediatricDiabetesUnit.organisations` / `primary_organisation` properties,
   since the temporal layer now holds the membership history. (The wizard
   warns you if either predecessor PZ code is in the hardcoded list.)

For a PDU acquisition (one PDU absorbs another, no new PZ code), use the
**Acquire another PDU…** wizard on the acquirer's change page instead.

## Worked example: South London Healthcare NHS Trust (RYQ) dissolution

This is the most complex case and is worth walking through in full to validate
the design.

**Starting state (before 2013):**

- RYQ (South London Healthcare NHS Trust) is active.
- RYQ30 (Princess Royal University Hospital) is a child of RYQ.
- RYQ01 (Queen Elizabeth Hospital, Woolwich) is a child of RYQ.
- Both have `OrganisationTrustMembership` rows: org → RYQ, valid_to=NULL.

**The dissolution:**

- RYQ is dissolved. Its children are split:
  - RYQ30 → moves to RJZ (King's College Hospital), becomes RJZ30.
  - RYQ01 → moves to RJ2 (Lewisham and Greenwich), becomes RJ201.

**What the temporal layer records:**

1. `TrustSuccession`: RYQ → RJZ, type=split, date=2013.
2. `TrustSuccession`: RYQ → RJ2, type=split, date=2013.
3. `Trust` (RYQ): `active` set to False. `TrustVersion` row closed, new one
   opened with `active=False`.
4. `Organisation` (RYQ30): `active` set to False. `OrganisationVersion` row
   closed.
5. `Organisation` (RJZ30): new row created. Baseline `OrganisationVersion`
   created.
6. `OrganisationSuccession`: RYQ30 → RJZ30, type=split, date=2013.
7. `OrganisationTrustMembership`: RYQ30's row (→ RYQ) closed. RJZ30's new row
   (→ RJZ) opened.
8. Steps 4–7 repeated for RYQ01 → RJ201, with RJ2 as the successor trust.

**What an audit query returns:**

- "Which trust was Princess Royal University Hospital under in 2012?"
  → Query `OrganisationSuccession` to find RJZ30's predecessor (RYQ30).
  → Query `OrganisationTrustMembership` for RYQ30 as of 2012.
  → Returns RYQ (South London Healthcare NHS Trust).

- "Which trust was Princess Royal University Hospital under in 2014?"
  → Query `OrganisationTrustMembership` for RJZ30 as of 2014.
  → Returns RJZ (King's College Hospital NHS Foundation Trust).

This is the chain-walking that the audit reports need, and it requires
`OrganisationSuccession` to work.
