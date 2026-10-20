---
title: Exposing the succession chain on the API
author: Dr Simon Chapman
---

# Exposing the succession chain on the API

## Motivation

The temporal layer (Layer 3) already records predecessor → successor links
for trusts, organisations, ICBs, and PDUs in the `*Succession` tables. The
snapshot endpoint walks the `OrganisationSuccession` chain **backwards** so
that querying a current code at a past date returns the predecessor's
state. Two gaps remain:

1. **No forward walk.** Querying a *predecessor* code (e.g. `RVY02`) at a
   date *after* the succession (e.g. today) returns 404, because the
   predecessor's last version row does not cover the queried date. The
   consumer has no way to discover that the site now lives under `RBN52`
   without maintaining their own succession map.
2. **No chain on the detail endpoints.** `/trusts/{ods_code}/`,
   `/organisations/{ods_code}/`, `/integrated_care_boards/{ods_code}/`,
   `/paediatric_diabetes_units/{pz_code}/` return only the current-state
   entity. A consumer that holds an old code has no API way to find its
   successor(s) or, conversely, to find what a current entity used to be.

This feature closes both gaps in a single PR. The two changes are
independent (disjoint write sets: snapshot view vs serializers) but ship
together because they share the same conceptual model and the same
documentation updates.

## Design

### Field semantics

Both the snapshot endpoint and the detail endpoints expose the resolved
entity's **immediate** neighbours in the succession chain. The fields are
named for the resolved entity's perspective, not for "did a walk happen":

- `predecessor_ods_code` / `predecessors` — the entity (or entities) that
  the resolved entity succeeded.
- `successor_ods_code` / `successors` — the entity (or entities) that
  succeeded the resolved entity.

A consumer detects that a walk happened by comparing `ods_code` in the
response to the code they queried. The chain fields are always the
resolved entity's neighbours, regardless of whether a walk occurred.

### Snapshot endpoint — scalar fields, forward walk

The snapshot endpoint resolves a single organisation as of `on_date`. The
chain is exposed as scalars because organisation successions are 1→1 in
practice (a site gets one new code under one new trust; a trust split
redistributes children, each child getting exactly one new parent and
one new code).

| Query | Resolved | `ods_code` | `predecessor_ods_code` | `successor_ods_code` |
|---|---|---|---|---|
| `RBN52` @ today | `RBN52` | `RBN52` | `RVY02` | `null` |
| `RBN52` @ 2022 | `RVY02` (backward walk) | `RVY02` | `null` | `RBN52` |
| `RVY02` @ 2022 | `RVY02` (no walk) | `RVY02` | `null` | `RBN52` |
| `RVY02` @ 2024 | `RBN52` (forward walk) | `RBN52` | `RVY02` | `null` |
| `RVY02` @ today | `RBN52` (forward walk) | `RBN52` | `RVY02` | `null` |

#### Forward walk rules

`_resolve_predecessor` (renamed `_resolve_as_of`) gains a forward walk
that mirrors the existing backward walk. Trigger conditions:

1. The resolved entity has no version row covering `on_date` (i.e. its
   history ended before `on_date`).
2. There is exactly one `OrganisationSuccession` link where the resolved
   entity is the predecessor and `succession_date <= on_date`.
3. The successor has a version row covering `on_date`.

If all three hold, walk to the successor and re-check. One hop is enough
— deeper chains are rare and the consumer can follow the chain manually
via the detail endpoint's `successors` array.

If condition 2 fails because there are **multiple** successor links (a
split, which should not occur for organisations in practice but is not
enforced by the model), return 404 with an error body listing the
successor codes. Walking to an arbitrary successor would silently return
the wrong site's geography.

#### Breaking change to `predecessor_ods_code`

The current `predecessor_ods_code` means "the resolved code, when it
differs from what you queried." Under the new semantics it means "the
resolved entity's predecessor." This is a breaking change for consumers
that rely on the old meaning — they should switch to comparing
`ods_code` to their queried code to detect a walk. The two existing
tests in `test_snapshot_api.py` (`test_snapshot_walks_succession_chain_to_predecessor`,
`test_snapshot_walks_parallel_code_to_predecessor`) will be updated to
assert the new semantics and to assert `successor_ods_code` on the
resolved predecessor.

### Detail endpoints — array fields, no walk

The detail endpoints return current state. They gain `predecessors` and
`successors` arrays populated from Layer 3, ordered by `succession_date`:

```json
// /trusts/RYQ/
{
  "ods_code": "RYQ",
  "name": "SOUTH LONDON HEALTHCARE NHS TRUST",
  "active": false,
  "predecessors": [],
  "successors": [
    {
      "ods_code": "RJZ",
      "name": "KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST",
      "succession_date": "2013-01-01",
      "succession_type": "split"
    },
    {
      "ods_code": "RJ2",
      "name": "LEWISHAM AND GREENWICH NHS TRUST",
      "succession_date": "2013-01-01",
      "succession_type": "split"
    }
  ]
}
```

Arrays are required because trusts, ICBs, and PDUs can split (one
predecessor, multiple successors) and can be born from full mergers
(multiple predecessors, one successor). Organisations are 1→1 in
practice but use the same array shape for API consistency.

| Endpoint | Succession table | `predecessors` / `successors` |
|---|---|---|
| `/trusts/{ods_code}/` | `TrustSuccession` | populated |
| `/organisations/{ods_code}/` | `OrganisationSuccession` | populated |
| `/integrated_care_boards/{ods_code}/` | `IntegratedCareBoardSuccession` | populated |
| `/paediatric_diabetes_units/{pz_code}/` | `PaediatricDiabetesUnitSuccession` | populated |
| `/local_health_boards/{ods_code}/` | none | `[]` always |
| `/nhs_england_regions/{region_code}/` | none (regions are static) | `[]` always |

The detail endpoints do **not** gain a `?date=` parameter. As-of
queries stay on the snapshot endpoint (organisations only). Mixing the
two concerns on the detail endpoints would duplicate the snapshot logic
across four viewsets.

## Implementation plan

Two workstreams, disjoint write sets, ship in one PR.

### Workstream A — snapshot forward walk

Touches `views/snapshot.py`, `tests/test_snapshot_api.py`, and the
snapshot sections of the docs.

1. Rename `_resolve_predecessor` → `_resolve_as_of` and add the forward
   walk. Commit with tests:
   - forward walk to successor when predecessor queried after succession
     date (`RVY02` @ today → `RBN52`);
   - forward walk to successor when predecessor queried between
     succession date and successor's last version date;
   - 404 with successor codes when predecessor has multiple successor
     links (defensive — should not occur for organisations);
   - existing backward-walk tests pass with updated assertions for the
     new `predecessor_ods_code` / `successor_ods_code` semantics.
2. Redefine `predecessor_ods_code` to mean "resolved entity's
   predecessor" and add `successor_ods_code` as "resolved entity's
   successor." Commit with tests covering every row of the table above.
3. Update `views/snapshot.py` docstring, `OrganisationSnapshotView`
   `@extend_schema` description, and the OpenAPI examples.

### Workstream B — detail endpoint chain arrays

Touches the five serializers, `tests/test_viewsets.py`, and the API
section of the docs.

1. Add a shared `SuccessionLinkSerializer` that serialises
   `{ods_code/pz_code, name, succession_date, succession_type}` from a
   succession row, resolving the related entity for the name. For
   `PaediatricDiabetesUnitSuccession` the identifier field is `pz_code`,
   not `ods_code`.
2. Add `predecessors` and `successors` `SerializerMethodField`s to:
   - `TrustSerializer`
   - `OrganisationSerializer`
   - `IntegratedCareBoardSerializer`
   - `PaediatricDiabetesUnitSerializer` (and the variants used on the
     PDU endpoints)
   - `LocalHealthBoardSerializer` (returns `[]`)
3. Commit with tests in `test_viewsets.py` covering:
   - acquisition (1→1, e.g. RVL → RAL);
   - full merger (2→1, e.g. RGQ + RDE → RJL — both predecessors list
     RJL as their successor, RJL lists both as predecessors);
   - split (1→2, e.g. RYQ → RJZ + RJ2);
   - closure (1→0, `successor=None` — `successors` is `[]`);
   - no succession table (LHB returns `[]` for both).

### Workstream C — documentation

1. Update `temporal-history.md` § Read path (L351-391) and § API
   (L575-587) to describe the forward walk and the chain fields.
2. Update `ods-sync.md` § The snapshot read path (L385-434) — the
   predecessor-walk section becomes "succession walk" and covers both
   directions.
3. Update `merger-handling.md` § Organisation succession (L80-108) to
   note that the chain is now exposed on the API.
4. Update `icb-history.md` to note the `predecessors` / `successors`
   arrays on the ICB detail endpoint.
5. Update `database_maintenance.md` § Auditing organisations for missing
   memberships (L407-447) — the snapshot section now also returns
   `successor_ods_code`.
6. Update `AGENTS.md` endpoint table to document the new fields on the
   detail endpoints and the new `successor_ods_code` field on the
   snapshot endpoint.
7. Add this doc (`succession-chain-fields.md`) to the mkdocs nav under
   Developers, between `icb-history.md` and `shapes.md`.

## Out of scope

- A `?date=` parameter on the detail endpoints. As-of queries stay on
  the snapshot endpoint.
- A forward walk for trusts, ICBs, or PDUs. They have no snapshot
  endpoint; the detail endpoint's `successors` array is the
  chain-navigation mechanism for those levels.
- Multi-hop forward walks. One hop covers the realistic cases; deeper
  chains are followed by the consumer via the detail endpoint's
  `successors` array.
- Modelling the host/associate ICB distinction (already out of scope
  per `merger-handling.md` § Cross-boundary mergers).
- Changing the `diverged_from_ods` / `ods_replacement_code` fields on
  `Organisation`. Those flag ODS-divergent codes for the consuming
  software; the succession chain is a separate concept.

## Breaking change summary

- `predecessor_ods_code` on the snapshot endpoint changes meaning from
  "the resolved code when it differs from the queried code" to "the
  resolved entity's predecessor." Consumers that detect a walk by
  checking `predecessor_ods_code is not null` should switch to checking
  `ods_code != queried_code`. The new `successor_ods_code` field is
  additive.
- The detail endpoints gain `predecessors` and `successors` arrays.
  These are additive (new fields, no existing field changes).
