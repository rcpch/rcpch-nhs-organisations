---
title: How trust mergers are handled
author: Dr Simon Chapman
---

# How trust mergers are handled

This document describes the different types of trust merger that occur in the NHS,
what happens to the trusts and their child organisations in each case, and how each
case is handled by the temporal history layer. It should be read alongside
[temporal-history.md](temporal-history.md), which describes the schema.

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
| Child ODS codes | Usually **retained** (Barnet keeps its org code; only the parent stem changes). If the ODS code does change, see Organisation succession below. |
| ICB / NHS England region | May change if the acquiring trust is in a different ICB or region. If so, the relevant membership rows are closed and new ones opened. |
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
| Child ODS codes | May or may not change. If the ODS reissues org codes with the new parent stem, see Organisation succession below. |
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

## Organisation succession — a gap in the current design

In the acquisition and full-merger cases, child organisations usually **retain
their ODS code** — only the parent trust changes. This is handled cleanly by
`OrganisationTrustMembership`: close the old row, open a new one pointing to the
successor trust. The `Organisation` row is unchanged.

In the split case (and sometimes in the other cases), the child organisation
gets a **new ODS code** because its parent stem has changed (RYQ30 → RJZ30).
The ODS treats this as a new organisation: the old code ceases to exist and a
new code is created. But from an audit perspective, RJZ30 in 2014 is the *same
physical hospital* as RYQ30 in 2012 — the audit data needs to trace that chain.

The current design has `TrustSuccession` and `PaediatricDiabetesUnitSuccession`
but **no `OrganisationSuccession`**. Without it, there is no way to record that
RYQ30 and RJZ30 are the same hospital, and longitudinal audit data cannot follow
a hospital across an ODS code change.

### Recommendation: add `OrganisationSuccession`

This should be added before the admin interface is built, since the admin needs
to create these rows when handling a split. The model mirrors
`TrustSuccession`:

```python
class OrganisationSuccession(TimeStampAbstractBaseClass):
    predecessor = models.ForeignKey(
        to=Organisation,
        on_delete=models.PROTECT,
        related_name="succession_predecessor_links",
    )
    successor = models.ForeignKey(
        to=Organisation,
        on_delete=models.PROTECT,
        related_name="succession_successor_links",
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
            ("code_change", "ODS code change"),
        ],
    )
    notes = models.TextField(blank=True, default="")
```

The `code_change` type covers the case where an organisation's ODS code changes
but it remains under the same parent trust (a pure rename/recode by ODS).

When an organisation succession occurs:

1. The old `Organisation` row (e.g. RYQ30) is marked `active=False`.
2. A new `Organisation` row (e.g. RJZ30) is created with the new ODS code.
3. An `OrganisationSuccession` row links them.
4. The new organisation inherits the old one's relationships (ICB, region, OPEN
   UK network, PDU, London borough, LAD, LSOA) via new baseline membership rows.
5. The new organisation's `OrganisationTrustMembership` points to the successor
   trust (RJZ), not the dissolved one (RYQ).

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

> **Note:** the current `TrustSuccession` schema requires a non-null `successor`
> FK, so a pure closure with no successor cannot be recorded as a succession
> row. This is intentional — a closure is simply the trust being marked
> inactive. If a closed trust's children are redistributed, each redistribution
> is recorded as a split succession with the relevant successor.

## Admin actions needed

Based on the three merger types, the admin needs these actions:

### For trusts

1. **Record trust acquisition.** A form with: predecessor trust, successor
   trust, effective date. On submit: mark predecessor `active=False`, create
   `TrustSuccession` (type=acquisition), and bulk-reassign all predecessor's
   child organisations to the successor trust (close old
   `OrganisationTrustMembership`, open new). Optionally also reassign ICB /
   region / OPEN UK network if the successor is in different geographies.

2. **Record full merger.** A form with: two or more predecessor trusts, a new
   successor trust (created if it doesn't exist), effective date. On submit:
   mark all predecessors `active=False`, create the successor trust + baseline
   `TrustVersion`, create `TrustSuccession` rows for each predecessor →
   successor, and bulk-reassign all child organisations.

3. **Record trust split.** A form with: predecessor trust, and a list of
   (child organisation, successor trust, new ODS code) tuples. On submit: mark
   predecessor `active=False`, create `TrustSuccession` rows for each successor,
   and for each child organisation either reassign (if ODS code retained) or
   create an organisation succession (if ODS code changed).

### For organisations

4. **Reassign organisation trust.** A simple form with: new trust, effective
   date. For the case where an org keeps its ODS code but changes parent. Closes
   the old `OrganisationTrustMembership`, opens a new one, updates the FK.

5. **Record organisation succession.** A form with: predecessor organisation,
   new ODS code, successor trust, effective date. For the case where an org gets
   a new ODS code. Creates the new `Organisation` row, marks the old one
   `active=False`, creates `OrganisationSuccession`, and transfers relationships.

### For PDUs

6. **Record PDU merger / succession.** Analogous to trust succession. A form
   with: predecessor PDU, successor PDU, effective date, type. On submit: mark
   predecessor `active=False`, create `PaediatricDiabetesUnitSuccession`, and
   bulk-reassign all child organisations' PDU memberships.

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
