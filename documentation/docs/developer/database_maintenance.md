---
title: Maintaining the RCPCH NHS Organisations service
author: Dr Simon Chapman
---

The main reason to have the RCPCH NHS Organisations service is to maintain current lists of active organisations, as well as their relationships with paediatric networks and other health regions. As political decisions are made, so the health geography mapping can change, so periodic maintenance of the lists becomes necessary.

## The ODS (Organisation Dataservice) ORD (Organisation Reference Data) API

This service is the national standard and provided by [NHS Digital](https://digital.nhs.uk/developer/api-catalogue/organisation-data-service-ord)

It is used to maintain the lists in the RCPCH NHS Organisations API up to date. In particular, the endpoint `/sync?LastChangeDate=` returns a large list of updates to organisational data.

Functions in the `ods_update` file in `general_functions` can make periodic calls to this endpoint and update any records in the Trust and Organisation tables if any have been published.

Since the temporal history layer was added, attribute changes are routed through the temporal helpers (`update_organisation_attributes` / `update_trust_attributes`) so that the previous state is recorded in the `*Version` tables before being overwritten. See [temporal-history.md](temporal-history.md) for the design.

**NOTE**: The ODS sync only updates Trusts and Organisations. ICBs, NHS England Regions, and Paediatric Diabetes Units are not synced from the ODS automatically — they are maintained via the backfill commands (see below) or manually via the admin.

### Dry-run mode

The `cron` command accepts `--dry-run`, which reports what *would* change without writing to the database. This is used by the GitHub Action for ODS change detection (see [temporal-history.md](temporal-history.md)) and is recommended before applying any sync:

```console
docker compose exec django python manage.py cron --service organisations --dry-run
```

The `--report-file` flag writes the markdown report to a file instead of stdout, which is what the GitHub Action uses:

```console
docker compose exec django python manage.py cron --service organisations --dry-run --report-file ods_changes.md
```

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

See [backfill.md](backfill.md) for the trust/organisation backfill design,
[icb-history.md](icb-history.md) for the ICB backfill, and
[pdu-history.md](pdu-history.md) for the PDU backfill.

### Running the backfills

The recommended order (each command depends on the previous having created
the entities it references):

```console
# 1. Seed the current-state rows
python manage.py seed --level all

# 2. Set lead_organisation FKs on PDUs
python manage.py backfill_pdu_lead_organisations --yes

# 3. Backfill trust successions (creates predecessor trust rows)
python manage.py backfill_successions --entity trust --yes

# 4. Backfill organisation successions
python manage.py backfill_successions --entity organisation --yes

# 5. Backfill ICB successions (creates missing successor ICB rows)
python manage.py backfill_successions --entity icb --yes

# 6. Backfill trust → trust membership history
python manage.py backfill_trust_memberships --yes

# 7. Backfill trust → ICB membership history
python manage.py backfill_icb_memberships --yes

# 8. Backfill PDU history (creates missing PDU rows, successions, memberships)
python manage.py backfill_pdu_successions --yes
```

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

The `cron` sync command cannot discover these organisations. It calls the
ODS `/sync` endpoint, which returns only organisations that *changed* in the
last 185 days, and even then it only processes organisations that are
already in the database (it matches by `ods_code` and skips anything not
found). So an organisation that was never seeded will never be picked up by
the sync, no matter how many times you run it.

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
row from the ODS `RE6` rel's operational start date.

For recording mergers (acquisitions, full mergers, splits, PDU mergers, ICB
successions), see [merger-handling.md](merger-handling.md) and
[icb-history.md](icb-history.md).
