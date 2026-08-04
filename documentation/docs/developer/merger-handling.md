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

A trust closes with no successor. The trust is marked `active=False`. No
`TrustSuccession` row is created (there is no successor to link to). Its child
organisations are either closed too or reassigned to other trusts (which would
be recorded as a split if they go to multiple successors).

> **Note:** the `TrustSuccession` schema requires a non-null `successor` FK, so
> a pure closure with no successor cannot be recorded as a succession row. This
> is intentional — a closure is simply the trust being marked inactive. If a
> closed trust's children are redistributed, each redistribution is recorded as a
> split succession with the relevant successor.

## Using the ODS management command

Mergers are applied through the `mergers` management command, which looks up
organisations on the NHS Spine and creates or updates them locally. The command
supports `--create` and `--delete` and a `--dry-run` flag that reports what
would change without writing to the database.

### Detecting changes from ODS

The `cron` management command calls the ODS `/sync` endpoint for changes in the
last 30 days (or up to 185 days for a one-off backfill). Run with `--dry-run` to
see what ODS has published before applying it:

```bash
python manage.py cron --service organisations --dry-run
```

This writes a markdown report to stdout listing, per affected entity, the field,
old value, new value, and effective date. The same report is generated
automatically by the scheduled GitHub Action for ODS change detection (see
[temporal-history.md](temporal-history.md)). ODS does not surface succession
relationships unambiguously, so the report is for review only — applying a
merger is a manual step.

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
manually via the admin, because ODS succession semantics are occasionally
ambiguous and a human should confirm the predecessor → successor mapping. See
[User steps for implementing mergers](#user-steps-for-implementing-mergers)
below.

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
`organisations` property, a one-off data migration or management command
would need to:

1. **Create the predecessor PDU rows** if they don't already exist (PZ216,
   PZ125, PZ080, PZ141, PZ003, etc.), marked `active=False`.
2. **Create baseline `PaediatricDiabetesUnitVersion` rows** for each
   predecessor, with `valid_from` set to the date the PDU was originally
   established and `valid_to` set to the merger date.
3. **Create `PaediatricDiabetesUnitSuccession` rows** linking each
   predecessor to its successor, with the merger date and type=merger.
4. **Create `OrganisationPaediatricDiabetesUnitMembership` rows** for each
   child organisation, with `valid_from` set to the date the org joined the
   predecessor PDU and `valid_to` set to the merger date. Then create new
   rows pointing to the successor PDU with `valid_from` = merger date and
   `valid_to = NULL`.
5. **Remove the hardcoded case** from the `organisations` property once the
   temporal rows are in place.

The merger dates and original establishment dates for these PDUs are not
always readily available from ODS (the ODS `/sync` endpoint only surfaces
the last 185 days). They would need to be sourced from the NPDA's own
records, from the ODS Trac bulk dumps, or from the hardcoded comments in
the `organisations` property itself (which include dates for some mergers).

This backfill is a one-off project, not an ongoing pattern. Once it is
done, the 30-day cron and the manual admin workflow keep the temporal layer
up to date for future mergers.

## User steps for implementing mergers

> This section is a placeholder. Step-by-step instructions for using the admin
> interface to record each merger type (acquisition, full merger, split,
> organisation succession, PDU succession) will be added once the admin actions
> are implemented.

### PDU merger workflow

To record a PDU merger (e.g. PZ216 + PZ125 → PZ253):

1. **Create the successor PDU** if it does not already exist, via the admin or
   the `mergers` command. A baseline `PaediatricDiabetesUnitVersion` row is
   created automatically.
2. **Create the `PaediatricDiabetesUnitSuccession` rows** via the admin: one
   row per predecessor PDU, all pointing to the successor PDU, with the
   merger date and type=merger.
3. **Mark the predecessor PDUs `active=False`** via the admin. A new
   `PaediatricDiabetesUnitVersion` row is opened for each, snapshotting
   `active=False`.
4. **Reassign the child organisations' PDU memberships** to the successor PDU
   via the admin reassignment action (or the `reassign_organisation_paediatric_diabetes_unit`
   helper). This closes the old `OrganisationPaediatricDiabetesUnitMembership`
   rows and opens new ones pointing to the successor PDU, with the merger date
   as `valid_from`.
5. **Set the successor PDU's network** via the admin (or the
   `reassign_paediatric_diabetes_unit_network` helper), recording it in
   `PaediatricDiabetesUnitNetworkMembership`.
6. **Remove any hardcoded special case** for the predecessor PZ codes in the
   `PaediatricDiabetesUnit.organisations` property, since the temporal layer
   now holds the membership history.

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
