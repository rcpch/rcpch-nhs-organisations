---
title: Maintaining the RCPCH NHS Organisations service
author: Dr Simon Chapman
---

The main reason to have the RCPCH NHS Organisations service is to maintain current lists of active organisations, as well as their relationships with paediatric networks and other health regions. As political decisions are made, so the health geography mapping can change, so periodic maintenance of the lists becomes necessary.

## What to run, and when

There are two distinct jobs, and it is important not to confuse them:

1. **First use (one-off, per database):** reconstruct the full historical
   temporal layer from ODS. This is the **backfill** suite. These commands
   **write by default** and must be run **in a fixed order** (each depends on
   entities the previous one created). You run these **once** on a fresh
   database (and again only if you add a brand-new entity type). See
   [First-use setup](#first-use-setup-run-once).
2. **Regular maintenance (ongoing):** detect and review drift against live
   ODS after the baseline is in place. This is `reconcile_ods`, which
   **defaults to dry-run** and stages structural changes in an admin review
   queue rather than writing them. See
   [Regular maintenance](#regular-maintenance-ongoing).

!!! warning "Opposite write semantics"
    The `backfill_*` commands **write by default** (pass `--dry-run` to
    preview). `reconcile_ods` **does the opposite** — it writes nothing
    unless you pass `--queue` or `--apply`. Running `reconcile_ods --mode
    backfill` on its own only *reports*; it does not populate the temporal
    layer. Use the `backfill_*` commands for that.

!!! note "`reconcile_ods` does not replace the backfills"
    `reconcile_ods` records *forward-looking* changes (close the current row,
    open a new one) and only ever **queues** structural changes for manual
    admin review — it never auto-applies them and never reconstructs multi-
    interval history. The `backfill_*` commands reconstruct the complete
    `[valid_from, valid_to)` history from the ODS `Rels`/`Succs` blocks. On a
    fresh database you need the history first, so run the backfills before you
    start relying on `reconcile_ods`.

## The ODS (Organisation Dataservice) ORD (Organisation Reference Data) API

This service is the national standard and provided by [NHS Digital](https://digital.nhs.uk/developer/api-catalogue/organisation-data-service-ord).

It is the source of truth the RCPCH NHS Organisations API reconciles against.
There are two ODS endpoints in play:

- `/organisations/{ods_code}` — returns an entity's **full** `Rels` and
  `Succs` history regardless of age. The backfills and `reconcile_ods`'s
  attribute scan read this (it is not subject to the 185-day limit).
- `/sync?LastChangeDate=` — returns entities that **changed** in a window
  (capped at 185 days). `reconcile_ods --mode incremental` uses this for its
  self-adjusting monthly window.

All writes are routed through the temporal helpers
(`update_organisation_attributes` / `update_trust_attributes` / …) so the
previous state is recorded in the `*Version` tables before being overwritten.
See [temporal-history.md](temporal-history.md) for the design.

!!! note "One command detects drift: `reconcile_ods`"
    `reconcile_ods` is the single entry point for detecting ODS drift across
    the organisation, trust, Local Health Board, and ICB levels (attributes,
    relationships, successions, roster and status). It replaced the old
    `cron --service organisations` sync and the `ods_change_report` job, which
    have been removed. For day-to-day use jump to
    [Regular maintenance](#regular-maintenance-ongoing); everything below
    about dry-runs and the monthly job is covered there.

    NHS England Regions and Paediatric Diabetes Units are **not** reconciled
    from ODS — regions are static and PDUs are not tracked by ODS. They are
    maintained via the backfill commands (below) or manually via the admin.

## Backfill commands

The ODS sync only captures recent changes (within the last 185 days). To
recover historical state that was overwritten before the temporal layer was
installed, use the backfill commands. These read the full ODS record via
`/organisations/{ods_code}` (which is not subject to the 185-day limit) or,
for PDUs, from the curated `Master_PDU_Lookup.xlsx` spreadsheet.

| Command | What it recovers | Source |
|---|---|---|
| `backfill_successions --entity trust` | `TrustSuccession` rows (mergers, acquisitions, splits) | ODS `Succs` block |
| `backfill_successions --entity organisation` | `OrganisationSuccession` rows (ODS code changes) | ODS `Succs` block |
| `backfill_successions --entity icb` | `IntegratedCareBoardSuccession` rows + missing successor ICBs | ODS `Succs` block |
| `backfill_trust_memberships` | `OrganisationTrustMembership` rows (org → trust history) | ODS `Rels` block (`RE6`) |
| `backfill_icb_memberships` | `TrustIntegratedCareBoardMembership` rows (trust → ICB history) | ODS `Rels` block (`RE5`/`RE8` → `RO261`) |
| `backfill_pdu_lead_organisations` | `lead_organisation` FK + `name_source` on PDUs | Hardcoded PZ-code lists |
| `backfill_pdu_successions` | `PaediatricDiabetesUnitVersion`, network memberships, lead-org memberships, `PaediatricDiabetesUnitSuccession` rows | `Master_PDU_Lookup.xlsx` (via generated constants) |

All commands support `--dry-run` (report without writing) and `--yes`
(auto-apply without prompts). They are idempotent — safe to re-run.

!!! warning "ICB successions must run before ICB memberships"
    `backfill_icb_memberships` points trust → ICB memberships at ICB rows
    that must already exist. The 2026 ICB reorganisation created six new
    ICBs (`T6Y0W`, `D7T5G`, `S0E4D`, `S1Y5D`, `S9B9J`, `Z9B2Z`) that are
    *successor* ICBs in the ODS `Succs` block. `backfill_successions
    --entity icb` is what creates those rows (via its `_create_missing_icb`
    step) — **but only in a real run, not `--dry-run`**. If you run
    `backfill_icb_memberships` before them, you get
    `RE5/RE8 → T6Y0W … ICB not in database, skipping. Run
    backfill_successions --entity icb first.` The fix is to run
    `backfill_successions --entity icb` (without `--dry-run`) first, then
    re-run `backfill_icb_memberships`.

See [backfill.md](backfill.md) for the trust/organisation backfill design,
[icb-history.md](icb-history.md) for the ICB backfill, and
[pdu-history.md](pdu-history.md) for the PDU backfill.

### First-use setup (run once)

On a fresh database, run the backfills **in this order** (each command
depends on the previous having created the entities it references). Run them
for real — `--dry-run` previews but writes nothing, and for ICB successions
`--dry-run` will *not* create the missing ICBs:

```console
# 1. Seed the current-state rows
python manage.py seed --level all

# 2. Set lead_organisation FKs on PDUs
python manage.py backfill_pdu_lead_organisations --yes

# 3. Backfill trust successions (creates predecessor trust rows)
python manage.py backfill_successions --entity trust --yes

# 4. Backfill organisation successions
python manage.py backfill_successions --entity organisation --yes

# 5. Backfill ICB successions (creates missing successor ICB rows) —
#    MUST run before step 7
python manage.py backfill_successions --entity icb --yes

# 6. Backfill org → trust membership history
python manage.py backfill_trust_memberships --yes

# 7. Backfill trust → ICB membership history (needs step 5's ICB rows)
python manage.py backfill_icb_memberships --yes

# 8. Backfill PDU history (creates missing PDU rows, successions, memberships)
python manage.py backfill_pdu_successions --yes

# 9. Reconcile current attributes against live ODS (see note below)
python manage.py reconcile_ods --mode backfill --apply
```

Prefix each with `docker compose exec -T django ` when running against the
container. To preview the whole sequence first, add `--dry-run` to each
command — but remember to run the real sequence afterwards, and that the ICB
membership step will still report skips in a dry-run because the dry-run ICB
succession step does not create the ICBs.

#### Step 9: the initial `reconcile_ods` pass

The `backfill_*` commands reconstruct relationship and succession **history**
(Layer 2/3) plus known-acquisition name changes, but they do **not** sync the
current **attributes** (telephone, website, county, address, current name)
against live ODS. Run `reconcile_ods --mode backfill --apply` as the final
initialisation step to:

- auto-apply the attribute-only drift (writing the version rows the backfills
  don't),
- queue the structural changes (successions, re-parenting, roster-adds) into
  the `PendingOdsChange` admin review queue,
- **promote the baseline** version and membership rows for every held entity
  to `max(legal_start, floor)` (see [Baseline promotion](#baseline-promotion)
  below), and
- anchor the `OdsSyncRun` baseline so the monthly incremental window
  (see [Regular maintenance](#regular-maintenance-ongoing)) is self-adjusting
  from this point.

It **must** run after the backfills — especially `backfill_icb_memberships`
— so the ~200 trust → ICB `none → X` relationship deltas collapse instead of
flooding the queue.

!!! note "Do not pass `--since` on the initial backfill pass"
    In `--mode backfill`, `--since` does **not** limit the attribute scan
    (that always deep-fetches every held entity); it only **raises the
    temporal floor** (default `2020-12-01`), narrowing how far back
    successions are considered. Passing a later date would shrink succession
    scope and risk dropping older history. Leave it off for the full scan.
    `--since` is for incremental mode (overriding the `/sync` window start),
    not first-use backfill.

    To eyeball the changes before writing, run a plain
    `reconcile_ods --mode backfill --dry-run --report-file ods_initial.md`
    first (writes nothing), then re-run with `--apply`. Review the queued
    structural changes in the Django admin afterwards — note the six new 2026
    ICBs are legitimate roster-adds, and any trust → ICB relationship cannot
    be applied until its target ICB exists (created by
    `backfill_successions --entity icb` in step 5).

### Baseline promotion

The baseline migration (`0024_baseline_version_backfill.py`) created one
`*Version` row per entity with `valid_from = date.today()` (the day the
migration ran). For a **stable** entity — one that has had no attribute or
relationship change since the temporal floor (`2020-12-01`) — that row should
reach back to `max(legal_start, floor)`, not installation day. Without this,
the snapshot endpoint (`/organisations/{ods_code}/snapshot/?date=…`) returns
404 for any date in `[floor, installation_day)`, even though the entity was
unambiguously in force.

The `0024` migration also created **version rows only** — no membership rows
(Layer 2). The `backfill_trust_memberships` and `backfill_pdu_successions`
commands fill the trust and PDU membership gaps from ODS `Rels` and constants
respectively, but ICB, NHS England region, OPENUK, and LHB memberships at the
organisation level are never backfilled by any command.

`reconcile_ods --mode backfill --apply` closes both gaps via `_promote_baseline`:

- **Existing baseline** (the `0024` migration ran on a populated DB): promotes
  the earliest version row's `valid_from` to `max(legal_start, floor)`, and
  promotes the earliest membership rows' `valid_from` to the floor. Trust and
  PDU membership rows already dated by the backfill commands are left alone.
- **Fresh DB** (the `0024` migration ran before `seed`, so no version or
  membership rows exist): creates a baseline version row at
  `max(legal_start, floor)` snapshotting the current entity attributes, and
  creates baseline membership rows at the floor for each non-null denormalised
  FK on the `Organisation` model.

This is idempotent — a re-run is a no-op once the baselines are correct — so
it is safe to re-run the full backfill sequence at any time. It runs as the
final step (`reconcile_ods --mode backfill --apply`, step 9) after `seed` and
the `backfill_*` commands, so the ODS record is already in hand for
`legal_start`.

This does **not** reconstruct pre-floor history. An entity whose code changed
before the floor (e.g. Princess Royal University Hospital was `RYQ30` under
South London Healthcare NHS Trust before 2013, then `RJZ30` under King's
College Hospital) is only reconstructable from the `OrganisationSuccession`
chain, and only if the predecessor entity is in the database. Pre-floor
organisation-level successions are out of scope — the floor stays at
`2020-12-01`. See [temporal-history.md](temporal-history.md) for the design.

### Regular maintenance (ongoing)

Once the baseline history is in place, use `reconcile_ods` to detect drift
against live ODS. It **defaults to dry-run** and stages structural changes in
the `PendingOdsChange` admin review queue — it does not write the temporal
layer directly.

```console
# Detect only (writes nothing)
python manage.py reconcile_ods --mode incremental --dry-run

# Detect and fill the admin review queue (no temporal writes)
python manage.py reconcile_ods --mode incremental --dry-run --queue

# Auto-apply attribute-only changes and queue structural ones for review
python manage.py reconcile_ods --mode incremental --apply
```

Structural changes (successions, re-parenting, roster-adds, retirements,
parallel codes) are **only ever queued**, never auto-applied — review and
apply them from the Django admin. Attribute-only changes with no succession
in the window are the only class that `--apply` writes automatically.

The monthly GitHub Action runs
`reconcile_ods --mode incremental --dry-run --queue --upload-blob` against
production (see [ods-change-detection.md](ods-change-detection.md)), so the
review queue is kept current without manual intervention. Use `--mode
backfill` for an occasional full-history re-scan (e.g. after adding a new
entity) rather than the self-adjusting incremental window.

## Merger

The command line can be invoked in the docker instance with:

```console
docker compose exec -it django bash
python manage.py mergers .....
```

This accepts the attributes:
`--organisations`: this is mandatory and represents a list of ODS codes of organisations. Note this will not work for trusts. A minimum of 1 organisation must be provided.
`--create` or `--delete`: one of these must be provided.
`--dry-run`: optional. Reports what would change without writing to the database.
*Create*: This looks up the ODS code provided against the ORD API and persists the details in the Organisation table. It creates a relationship between the new organisation and a parent Trust/Local Health Board and if in England, an NHS Region and Integrated Care Board also. It also looks up against lists in `constants` for any matching membership of Paediatric Diabetes Units, OPEN UK Networks. If there is no relationship, it will prompt the user to confirm that they want to continue with organisation creation. It should be possible to add this relationship at a later date, but this is currently not supported. If there is no PDU in the database, an organisation will not be created. Since the temporal history layer was added, creating an organisation also creates baseline temporal rows (`OrganisationVersion` plus the relevant membership rows) so the new organisation has history from creation day forward.
*Delete*: Since the Organisation does not have referential integrity with its parent or related regions, the user is asked to confirm that they want to continue with deletion. A summary of the organisation's membership is logged to the console. Note that if the organisation is the only one associated with a paediatric diabetes unit record or openuk network record, that will leave that association broken. If the organisation is added back, that relationship is recreated.

### Adding a missing organisation

The `mergers --create` command is also the way to add an organisation that
the consuming software (e.g. E12) references but that is not in the RCPCH
seed list. This is **not** a merger — the site isn't new, it's just missing
from the database.

The roster scan in `reconcile_ods` surfaces a brand-new organisation in ODS
as a *roster-add* in its report, but it does **not** create the organisation
row — organisations are a closed, seeded set. (The old `cron` sync could
never discover them either: `/sync` returns only organisations that *changed*
and already exist in the database.) So an organisation that was never seeded
has to be added explicitly with `mergers --create`, no matter how many sync
or reconcile passes you run.

To add a missing organisation, fetch it directly from the ODS
`/organisations/{ods_code}` endpoint using `mergers --create`:

```bash
python manage.py mergers --organisations RDR08 RDRC7 R0A07 --create
```

This looks up each ODS code on the Spine, creates the `Organisation` row
with its parent trust, ICB, NHS England region, country and OPENUK network
(inherited from a sibling organisation under the same trust), and writes
baseline temporal rows (`OrganisationVersion` plus the relevant membership
rows) so the new organisation has history from creation day forward.

If the organisation has no Paediatric Diabetes Unit or OPENUK network in
the `constants` lists, the command prompts to confirm whether to continue
without it. Answer `y` to create the organisation anyway — the relationship
can be added later via the admin or by adding the code to `PZ_CODES` /
`OPEN_UK_NETWORKS_TRUSTS` and re-running. Answering `n` skips just that
organisation and continues to the next one in the list.

The baseline membership rows created by `mergers --create` are dated today,
not the ODS operational start date. To recover the full historical trust
membership (e.g. from 1992 to today), run `backfill_trust_memberships --all`
afterwards — it will write the historical `OrganisationTrustMembership`
row from the ODS `RE6` rel's operational start date. The baseline version
and membership rows are also promoted to `max(legal_start, floor)` by
`reconcile_ods --mode backfill --apply` (see
[Baseline promotion](#baseline-promotion)).

For recording mergers (acquisitions, full mergers, splits, PDU mergers, ICB
successions), see [merger-handling.md](merger-handling.md) and
[icb-history.md](icb-history.md).

### Completing half-applied parallel-code successions

Some organisation code changes (where ODS closed a site's code and issued a
new one under a successor trust) were half-applied before the
`inherit_organisation_state` fix: the successor `Organisation` row was
created and its trust reparented, but the baseline `OrganisationVersion` and
non-trust membership rows (ICB, NHS England region, OPEN UK network, PDU)
were never created, and the predecessor's memberships were never closed.
This left successors like RW155, RW1YH, and RBN52 with null ICB / region /
OPEN UK / PDU on the direct endpoint and on the snapshot, while the trusts
endpoint listed them (it reads the denormalised `trust` FK), masking the
gap.

The curated `KNOWN_PARALLEL_ORGANISATIONS` constant (in
`constants/known_parallel_organisations.py`) lists every such mapping. The
`apply_parallel_successions` command sweeps that list and completes each
half-applied succession in one pass:

```bash
# Dry-run to see what would be done
python manage.py apply_parallel_successions --dry-run

# Apply all
python manage.py apply_parallel_successions --yes

# Apply one entry
python manage.py apply_parallel_successions --predecessor RVY02 --yes

# Override the effective date (derived from the TrustSuccession otherwise)
python manage.py apply_parallel_successions --effective-date 2023-07-01 --yes
```

For each entry the command takes one of three paths, depending on what
is in the database:

1. **Both predecessor and successor absent** — the entry is skipped. The
   successor must be created first (e.g. via `mergers --organisations <code>
   --create`), then re-run.
2. **Predecessor present** (the normal case) — the command:
   1. creates the successor `Organisation` if missing (deep-fetched from ODS);
   2. ensures the successor has a trust membership (reassign to the successor
      trust);
   3. creates the `OrganisationSuccession` link if missing (predecessor →
      successor, type `code_change`);
   4. inherits the predecessor's non-trust state (baseline version +
      memberships, closes the predecessor's open memberships) via
      `inherit_organisation_state`;
   5. flags the predecessor `diverged_from_ods` with `ods_replacement_code`.
3. **Predecessor absent, successor present** (e.g. RBN52, where the
   predecessor RYV02 was removed from the seed) — the command cannot call
   `inherit_organisation_state` (no predecessor to read from), so it derives
   the successor's geography from the **successor trust's** memberships
   instead:
   - ICB and NHS England region from the trust's current
     `TrustIntegratedCareBoardMembership` / `TrustNHSEnglandRegionMembership`;
   - OPEN UK network from the `OPEN_UK_NETWORKS_TRUSTS` constant for the
     trust;
   - country by looking up the `Country` row matching the trust's `country`
     string (`Trust.country` is a `CharField`, not a `ForeignKey`);
   - a baseline `OrganisationVersion` for the successor if missing.

   This path does **not** create an `OrganisationSuccession` link (there is
   no predecessor row to link from) and does **not** flag any predecessor as
   diverged. If the predecessor is later added (e.g. via `mergers --create`),
   the succession link and divergence flag would need to be created
   separately.

   This is less precise than inheriting from the predecessor (the trust's
   host ICB may differ from the site's commissioning ICB in a cross-boundary
   merger), but it is the best available source when the predecessor is gone.

PDU is inherited from the predecessor in the normal path (via
`inherit_organisation_state`); the trust-derived path does **not** set a PDU,
because PDU is a site-specific relationship, not a trust-level one. If the
successor needs a PDU and the predecessor is absent, set it manually via the
admin (see [Merger](#merger) above) after running the command.

### Auditing organisations for missing memberships

The snapshot endpoint reads parent relationships from the **membership tables**
(`OrganisationTrustMembership`, `OrganisationIntegratedCareBoardMembership`,
`OrganisationNHSEnglandRegionMembership`, `OrganisationOPENUKNetworkMembership`),
not the denormalised FKs on the `Organisation` row. An organisation with a
denormalised `trust` FK but no `OrganisationTrustMembership` row appears
under its trust in the trusts endpoint but returns null trust (and null ICB /
region / OPEN UK) on the snapshot.

The `audit_organisation_relationships` command scans every active
`Organisation` and flags those missing current membership rows or a baseline
`OrganisationVersion`:

```bash
# Audit all active organisations
python manage.py audit_organisation_relationships

# Also audit inactive organisations (predecessors etc.)
python manage.py audit_organisation_relationships --include-inactive

# Filter to one country
python manage.py audit_organisation_relationships --country England

# Only report organisations missing a specific relationship
python manage.py audit_organisation_relationships --missing trust
python manage.py audit_organisation_relationships --missing icb
python manage.py audit_organisation_relationships --missing version
```

It checks for each active `Organisation`:

- a baseline `OrganisationVersion` (valid_to IS NULL) — needed by the snapshot walk;
- a current `OrganisationTrustMembership`;
- a current `OrganisationIntegratedCareBoardMembership`;
- a current `OrganisationNHSEnglandRegionMembership`;
- a current `OrganisationOPENUKNetworkMembership`.

PDU is **not** audited because not every site has a PDU. Use the snapshot
endpoint or the PDU constants for that check.
