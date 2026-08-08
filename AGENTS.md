# AGENTS.md

Guidance for AI coding agents (and human contributors) working on this
project. Read this first before making changes.

## Project overview

**rcpch-nhs-organisations** is a Django + Django REST Framework API that
serves the organisational geography of the NHS — trusts, organisations
(hospital sites), Integrated Care Boards, Local Health Boards, NHS
England regions, Paediatric Diabetes Units (PDUs), and their boundary
shapes. It is consumed by national clinical audits (e.g. NPDA) that
report longitudinal data against the organisational geography in force
at the time the data was collected.

The project uses PostGIS for boundary geometry and is deployed via Docker
Compose (Caddy + Django + PostGIS + MkDocs).

## Key documentation

All developer documentation lives in `documentation/docs/developer/` and
is served by MkDocs. The most important docs:

| Doc | What it covers |
|---|---|
| `temporal-history.md` | The temporal layer schema (Layer 1 version tables, Layer 2 membership tables, Layer 3 succession tables), write/read paths, admin interface, and the GitHub Action. |
| `merger-handling.md` | Trust and PDU merger types (acquisition, full merger, split, closure), the forward-looking admin workflow, and the `mergers` command. |
| `backfill.md` | ODS-driven trust backfill (`backfill_successions`, `backfill_trust_memberships`), the `backfill_*` helpers, and `KNOWN_ACQUISITIONS`. |
| `pdu-history.md` | PDU history backfill from `Master_PDU_Lookup.xlsx` (`backfill_pdu_successions`). |
| `icb-history.md` | ICB succession backfill from the ODS API (`backfill_successions --entity icb`). |
| `ods-api.md` | The NHS ODS REST API reference — endpoints, `Rels`/`Succs` block semantics, the 185-day limit. |
| `models.md` | Overview of the models and relationships. |
| `seeding.md` | How to seed the database (`seed --level all`). |
| `testing.md` | Test coverage summary and how to run tests. |

## Models

All models live in `rcpch_nhs_organisations/hospitals/models/`. The
`Organisation` model sits at the centre — all other entities are parents
or networks of it.

### Current-state models (Layer 0)

| Model | Key fields | Notes |
|---|---|---|
| `Organisation` | `ods_code` (unique), `name`, `address`, `active`, `trust` FK, `paediatric_diabetes_unit` FK, `integrated_care_board` FK, `local_health_board` FK, `nhs_england_region` FK, `openuk_network` FK | A hospital site. The denormalised FKs are current state; the temporal layer tracks their history. |
| `Trust` | `ods_code` (unique), `name`, `address`, `active` | An NHS trust (England). |
| `LocalHealthBoard` | `ods_code` (unique), `name`, `active` | Welsh equivalent of a trust. |
| `IntegratedCareBoard` | `ods_code` (unique), `name`, `active`, boundary fields (nullable) | 42 ICBs (England). Boundary geometry is being deprecated in favour of the RCPCH Census Platform. |
| `NHSEnglandRegion` | `region_code`, `name`, boundary fields | 7 regions above ICBs. |
| `PaediatricDiabetesUnit` | `pz_code` (unique), `unit_name`, `active`, `lead_organisation` FK, `paediatric_diabetes_network` FK, `name_source` | A PDU. Not tracked by ODS — maintained manually from `Master_PDU_Lookup.xlsx`. |
| `PaediatricDiabetesNetwork` | `pn_code` (unique), `name` | 12 regional diabetes networks. |
| `OPENUKNetwork` | `name` | Epilepsy networks. |
| `Country` | `name`, region codes | UK countries + crown dependencies. |

### Temporal layer

The temporal layer is additive — it sits on top of the current-state
models without changing them. It has three layers:

**Layer 1 — Entity version tables** (append-only snapshots of mutable
attributes with `[valid_from, valid_to)` intervals):
`OrganisationVersion`, `TrustVersion`, `LocalHealthBoardVersion`,
`IntegratedCareBoardVersion`, `NHSEnglandRegionVersion`,
`PaediatricDiabetesUnitVersion`, `PaediatricDiabetesNetworkVersion`.

**Layer 2 — Relationship membership tables** (append-only snapshots of
FK relationships with `[valid_from, valid_to)` intervals):
`OrganisationTrustMembership`, `OrganisationLocalHealthBoardMembership`,
`OrganisationIntegratedCareBoardMembership`,
`OrganisationNHSEnglandRegionMembership`,
`OrganisationOPENUKNetworkMembership`,
`OrganisationPaediatricDiabetesUnitMembership`,
`PaediatricDiabetesUnitNetworkMembership`,
`OrganisationLondonBoroughMembership`,
`OrganisationLocalAuthorityDistrictMembership`,
`OrganisationLowerLayerSuperOutputAreaMembership`,
`TrustIntegratedCareBoardMembership`, `TrustNHSEnglandRegionMembership`.

**Layer 3 — Succession tables** (merger/acquisition/split/closure
metadata linking predecessor → successor):
`TrustSuccession`, `OrganisationSuccession`,
`PaediatricDiabetesUnitSuccession`, `IntegratedCareBoardSuccession`.

### Helper functions

All temporal writes go through helpers in
`rcpch_nhs_organisations/hospitals/general_functions/membership.py`:

- `update_<entity>_attributes()` — forward-looking attribute change
  (closes current version row, opens new one).
- `backfill_<entity>_attributes()` — historical attribute backfill
  (inserts a version row with an explicit interval, without touching the
  current row).
- `reassign_<child>_<parent>()` — forward-looking relationship change
  (closes current membership row, opens new one, updates the FK).
- `backfill_organisation_trust_membership()` — historical membership
  backfill.

Never write directly to the temporal tables — always use the helpers.

## API

The API is a DRF router with viewsets for each entity. The base URL is
configured via `NHS_ODS_API_URL` (for ODS calls) and the app is served on
port 8003.

| Endpoint | Description |
|---|---|
| `/organisations/` | Organisation list/detail (filter by `ods_code`, `trust`, `paediatric_diabetes_unit`, etc.) |
| `/trusts/` | Trust list/detail |
| `/local_health_boards/` | LHB list/detail (Wales) |
| `/integrated_care_boards/` | ICB list/detail |
| `/nhs_england_regions/` | NHS England region list/detail |
| `/paediatric_diabetes_units/` | PDU list/detail |
| `/paediatric_diabetes_units/sibling-organisations/{ods_code}/` | PDU for a given organisation with parent |
| `/organisations/{ods_code}/snapshot/?date=YYYY-MM-DD` | Temporal snapshot of an organisation at a given date |
| `/schema/` | OpenAPI schema |
| `/swagger-ui/` | Swagger UI |

The snapshot endpoint is the read path for audit reports — it assembles
the entity version plus every relationship as of the given date.

## Management commands

All commands are in `rcpch_nhs_organisations/hospitals/management/commands/`.

| Command | Purpose |
|---|---|
| `seed --level all` | Seed the database from constants (trusts, organisations, PDUs, networks, abstraction levels). |
| `cron --service organisations [--dry-run] [--time-frame N]` | ODS sync — fetches changes from the ODS `/sync` endpoint and applies them through the temporal helpers. |
| `mergers --organisations <codes> --create/--delete [--dry-run]` | Create or delete organisations from the ODS Spine. |
| `backfill_successions --entity trust/organisation/icb [--dry-run] [--yes]` | Backfill succession rows from the ODS `Succs` block. |
| `backfill_trust_memberships [--dry-run] [--yes]` | Backfill `OrganisationTrustMembership` rows from the ODS `Rels` block. |
| `backfill_pdu_lead_organisations [--dry-run] [--yes]` | Set `lead_organisation` FK and `name_source` on PDUs. |
| `backfill_pdu_successions [--dry-run] [--yes]` | Backfill PDU history from `Master_PDU_Lookup.xlsx` (via generated constants). |

## Scripts

| Script | Purpose |
|---|---|
| `scripts/generate_pdu_history_constants.py` | Reads `Master_PDU_Lookup.xlsx` and emits `constants/pdu_history.py`. Run inside the Django container so Welsh lead-org name lookup works. Requires `openpyxl` (in `development-requirements.txt`). |

## Testing strategy

### Running tests

```bash
# Inside the project root, with containers running:
./s/test

# Or directly:
docker compose exec django pytest -v

# Run a single test file:
docker compose exec django pytest rcpch_nhs_organisations/hospitals/tests/test_backfill_successions.py -v

# Run a single test:
docker compose exec django pytest rcpch_nhs_organisations/hospitals/tests/test_backfill_successions.py::test_dry_run_reports_missing_succession -v
```

The test database is created and destroyed per test session by
pytest-django. Tests that need PostGIS create `MultiPolygon` fixtures
inline.

### Test files

All tests live in `rcpch_nhs_organisations/hospitals/tests/`. There are
~200 tests across 19 files:

| File | Covers |
|---|---|
| `test_organisation_version.py` | `OrganisationVersion` model invariants. |
| `test_entity_versions.py` | All other entity version models (parametrised). |
| `test_baseline_backfill.py` | The baseline backfill data migration. |
| `test_organisation_memberships.py` | Core relationship-membership tables (parametrised). |
| `test_trust_and_boundary_memberships.py` | Trust-level and boundary membership tables. |
| `test_successions.py` | `TrustSuccession` and `PaediatricDiabetesUnitSuccession`. |
| `test_organisation_succession.py` | `OrganisationSuccession` (South London Healthcare split). |
| `test_membership_helpers.py` | The helper functions in `membership.py`. |
| `test_ods_sync.py` | The ODS sync with `--dry-run`. |
| `test_mergers_command.py` | The `mergers` management command. |
| `test_admin.py` | Admin interface (reassign actions, history inlines, succession pages). |
| `test_snapshot_api.py` | The `GET /organisations/{ods_code}/snapshot` endpoint. |
| `test_cron_report_file.py` | The `--report-file` flag used by the GitHub Action. |
| `test_merger_workflows.py` | End-to-end integration tests for full merger workflows. |
| `test_backfill_successions.py` | `backfill_successions --entity trust/organisation`. |
| `test_backfill_trust_memberships.py` | `backfill_trust_memberships`. |
| `test_backfill_icb_successions.py` | `backfill_successions --entity icb`. |
| `test_backfill_pdu_successions.py` | `backfill_pdu_successions`. |
| `test_viewsets.py` | API viewset smoke tests. |

### ODS API mocking

No test makes a live network call to the ODS/Spine API. Tests that
exercise ODS-dependent code mock the network functions via
`unittest.mock.patch`:

- `get_organisation` — patched in the `backfill_successions` module.
- `fetch_updated_organisations` — patched in the `ods_update` module.
- `fetch_organisation_by_ods_code` — patched in the `general_functions` package.

The mock returns canned ODS records (built by helper functions like
`_ods_record` and `_succ`) so tests are deterministic and offline.

### Temporal invariants

Every entity version model and every membership model is tested against
the same invariants:

1. Baseline is current (`valid_to IS NULL`).
2. Single current row per entity.
3. Close previous on update.
4. As-of query returns the row in force on the given date.
5. Half-open interval `[valid_from, valid_to)`.
6. Pre-history returns no row.
7. `PROTECT` on delete (membership tables).

## Constants

Curated Python constants live in
`rcpch_nhs_organisations/hospitals/constants/`. These are the source of
truth for seeding and backfill:

| File | What it seeds |
|---|---|
| `paediatric_diabetes_units.py` | `PZ_CODES` — PDU → lead organisation ODS code mappings. |
| `paediatric_diabetes_networks.py` | 12 diabetes networks. |
| `integrated_care_boards.py` | 42 ICBs + ICB↔local authority mappings. |
| `known_acquisitions.py` | `KNOWN_ACQUISITIONS` — trust acquisitions with pre-merger names not in ODS. |
| `known_icb_acquisitions.py` | `KNOWN_ICB_ACQUISITIONS` — ICB acquisitions (QRL gaining territory from Frimley). |
| `pdu_history.py` | `PDU_HISTORY` / `PDU_SUCCESSIONS` — generated from `Master_PDU_Lookup.xlsx`. Do not edit by hand. |
| `ods_divergent_codes.py` | ODS-divergent organisation codes (sites ODS considers inactive but the audit still uses). |

## GitHub Actions

| Workflow | Schedule | What it does |
|---|---|---|
| `ods-change-detection.yml` | Monthly (1st of month) | Runs three dry-run checks (ODS sync, trust successions, ICB successions) and opens a GitHub issue if changes are detected. |
| `main_rcpch-nhs-organisations.yml` | On push/PR | CI — builds and tests. |
| `pr.yml` | On PR | PR checks. |

## Docker

The project runs via Docker Compose with four services:

| Service | Port | Purpose |
|---|---|---|
| `django` | 8003 | The Django/DRF API. |
| `postgis` | — | PostgreSQL with PostGIS. |
| `caddy` | 80, 443 | Reverse proxy / SSL. |
| `mkdocs` | 8004 | Documentation server. |

Common commands:

```bash
./s/dev          # start the dev stack
./s/test          # run tests
./s/logs          # tail logs
./s/django_shell  # open a Django shell
```