---
title: Testing the temporal history layer
author: Dr Simon Chapman
---

# Testing the temporal history layer

This document summarises the test coverage for the temporal history layer
described in [temporal-history.md](temporal-history.md) and
[merger-handling.md](merger-handling.md). It is intended to help reviewers and
future maintainers understand what is tested and how.

## Test files

All tests live in `rcpch_nhs_organisations/hospitals/tests/` and are run with
`./s/test` (which runs `pytest -v` inside the Django container).

| File | Covers | Tests |
|---|---|---|
| `test_organisation_version.py` | `OrganisationVersion` model — the entity-attribute layer for organisations | 6 |
| `test_entity_versions.py` | The remaining 6 entity version models (Trust, LHB, ICB, NHS England region, PDU, PDN), parametrised | 30 |
| `test_baseline_backfill.py` | The baseline backfill data migration (0024) | 9 |
| `test_organisation_memberships.py` | The 7 core relationship-membership tables (org→trust, org→LHB, org→ICB, org→region, org→OPEN UK, org→PDU, PDU→network), parametrised | 42 |
| `test_trust_and_boundary_memberships.py` | The 5 trust-level and boundary membership tables (trust→ICB, trust→region, org→London borough, org→LAD, org→LSOA), parametrised | 30 |
| `test_successions.py` | `TrustSuccession` and `PaediatricDiabetesUnitSuccession` | 9 |
| `test_organisation_succession.py` | `OrganisationSuccession`, including the South London Healthcare split scenario | 6 |
| `test_membership_helpers.py` | The helper functions in `general_functions/membership.py` — the sanctioned write path | 14 |
| `test_ods_sync.py` | The refactored ODS sync with `--dry-run` | 8 |
| `test_mergers_command.py` | The `mergers` management command with `--dry-run` and baseline temporal row creation | 5 |
| `test_admin.py` | The admin interface (reassign trust action, history inlines, succession admin pages) | 11 |
| `test_snapshot_api.py` | The `GET /organisations/{ods_code}/snapshot?date=` endpoint | 8 |
| `test_cron_report_file.py` | The `--report-file` flag used by the GitHub Action | 2 |
| `test_merger_workflows.py` | End-to-end integration tests for the full merger workflows | 4 |

**Total: 184 tests** (including the 2 pre-existing viewset tests).

## Temporal invariants tested

Every entity version model and every membership model is tested against the
same six invariants:

1. **Baseline is current.** A freshly created row with `valid_to IS NULL` is
   the current one.
2. **Single current row.** At most one row with `valid_to IS NULL` per entity
   (or per child in the case of membership tables).
3. **Close previous.** Creating a new current row closes the previous one
   (`valid_to` set to the effective date).
4. **As-of query.** The as-of query returns the row in force on the given date.
5. **Change date.** On the exact change date, the new row is in force
   (half-open interval `[valid_from, valid_to)`).
6. **Pre-history.** A date before the first `valid_from` returns no row.

Membership tables add a seventh invariant:

7. **PROTECT on delete.** Deleting a parent that has history is prevented by
   `on_delete=PROTECT`, so history cannot be lost by accident.

## ODS API mocking

No test makes a live network call to the ODS/Spine API. The three test files
that exercise ODS-dependent code mock the network functions via
`monkeypatch.setattr`:

| Test file | What is mocked | How |
|---|---|---|
| `test_ods_sync.py` | `fetch_updated_organisations`, `get_organisation` | Patched in `ods_update` module |
| `test_cron_report_file.py` | Same as above | Same pattern |
| `test_mergers_command.py` | `fetch_organisation_by_ods_code`, `fetch_by_postcode`, `builtins.input` | Patched in the `general_functions` package (where the names are imported into) |

The argument-validation tests in `test_mergers_command.py`
(`test_create_and_delete_rejected_together`, `test_no_create_or_delete_rejected`,
`test_no_organisations_rejected`) don't mock ODS because they're rejected at
the argument-validation stage before any network call is made.

## Integration tests

`test_merger_workflows.py` exercises the full merger workflows end-to-end
through the helper functions, using the worked examples from
[merger-handling.md](merger-handling.md):

1. **Trust acquisition** — Barnet & Chase Farm (RVL) acquired by Royal Free
   (RAL), 2014. Verifies the audit query returns RVL before the merger and RAL
   after.
2. **Full merger** — Ipswich (RGQ) + Colchester (RDE) → RJL, 2018. Verifies
   both predecessors are marked inactive and the child orgs are reassigned to
   RJL.
3. **Dissolution with split** — South London Healthcare (RYQ) dissolved 2013,
   Princess Royal (RYQ30 → RJZ30) and Queen Elizabeth Woolwich (RYQ01 → RJ201)
   split between King's College (RJZ) and Lewisham & Greenwich (RJ2). Verifies
   the snapshot endpoint walks the `OrganisationSuccession` chain to return
   the predecessor's state when queried at a date before the successor existed.
4. **PDU merger** — PZ216 + PZ125 → PZ253, January 2026. Verifies the child
   organisations' PDU membership is reassigned to the successor PDU.

## Running the tests

```bash
# Inside the project root, with containers running:
./s/test

# Or directly:
docker compose exec django pytest -v

# Run a single test file:
docker compose exec django pytest rcpch_nhs_organisations/hospitals/tests/test_merger_workflows.py -v
```

The test database is created and destroyed per test session by pytest-django.
Tests that need PostGIS (anything involving boundary geometries) create
`MultiPolygon` fixtures inline.
