# NHS ODS API reference

This document summarises the NHS Organisation Data Service (ODS) REST API as
used by this project — the endpoints we call, the parameters we pass, the
response fields we extract, and the semantics of the `Rels` and `Succs` blocks
that record relationships and succession (mergers, acquisitions, splits).

It is a reference for developers working on the ODS sync, the merger command,
and the temporal history layer. It is not a complete API specification — see
the [NHS ODS documentation](https://digital.nhs.uk/services/organisation-data-service)
for the full picture.

## Base URL

```
https://directory.spineservices.nhs.uk/ORD/2-0-0
```

Configured via the `NHS_ODS_API_URL` environment variable
(see `envs/example.env`). No authentication required.

## Endpoints used by this project

### 1. `/sync` — list of organisations changed since a date

Used by the `cron` management command and the GitHub Action for ODS change
detection.

```
GET /sync?LastChangeDate={YYYY-MM-DD}
```

| Parameter | Required | Description |
|---|---|---|
| `LastChangeDate` | Yes | Returns organisations that changed on or after this date. The API has a **hard limit of 185 days** into the past — requests older than that return an error. |

**Response:**

```json
{
  "Organisations": [
    {"OrgLink": "https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations/06KAA"},
    {"OrgLink": "https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations/RM3"},
    ...
  ]
}
```

> **The `/sync` list item contains only `OrgLink`.** It does **not** include
> `LastChangeDate`, `Name`, `Status`, or any other field. To get the full
> record (including `LastChangeDate`), follow the `OrgLink` to the
> `/organisations/{ods_code}` endpoint. This was a bug in an earlier version
> of the sync, which tried to read `LastChangeDate` from the `/sync` list
> item and got `unknown` for every organisation.

**Code:** `fetch_updated_organisations(time_frame)` in
`general_functions/ods_update.py`. The `time_frame` parameter (days, max 185)
is converted to a `LastChangeDate` query parameter.

### 2. `/organisations/{ods_code}` — full organisation record

Used by the sync (via `get_organisation`), the merger command, and the
`fetch_organisation_by_ods_code` helper.

```
GET /organisations/{ods_code}
```

| Parameter | Required | Description |
|---|---|---|
| `ods_code` (path) | Yes | The ODS code (e.g. `RM3`, `RAA01`). |

**Response:** a single `Organisation` object — see the full structure below.

**Code:** `get_organisation(org_link)` in `general_functions/ods_update.py`,
`fetch_organisation_by_ods_code(ods_code)` in
`general_functions/organisation_from_ods_code.py`.

### 3. `/organisations?PrimaryRoleId={role_id}` — list by role

Used by the seeding commands to fetch all trusts, all trust sites, etc.

```
GET /organisations?PrimaryRoleId={role_id}&Limit={limit}
```

| Parameter | Required | Description |
|---|---|---|
| `PrimaryRoleId` | No | Filter by primary role (e.g. `RO197` for NHS trusts). |
| `Limit` | No | Maximum number of results (default 100, max 500). |

**Response:** a list of organisation summary objects (not the full record):

```json
{
  "Organisations": [
    {
      "Name": "HERTFORDSHIRE PARTNERSHIP UNIVERSITY NHS FOUNDATION TRUST",
      "OrgId": "RWR",
      "Status": "Active",
      "OrgRecordClass": "RC1",
      "PostCode": "AL10 8YE",
      "LastChangeDate": "2020-04-06",
      "PrimaryRoleId": "RO197",
      "PrimaryRoleDescription": "NHS TRUST",
      "OrgLink": "https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations/RWR"
    },
    ...
  ]
}
```

Note: this endpoint **does** include `LastChangeDate` in the summary object,
unlike `/sync`. But we don't use this endpoint for change detection — we use
`/sync` — because `/organisations` returns the full population, not just the
changed ones.

**Code:** `all_nhs_hospitals_list()` in `general_functions/ods_calls.py`.

## Primary role IDs

Organisations are categorised by `PrimaryRoleId`. The ones we use:

| Role ID | Description | Used for |
|---|---|---|
| `RO197` | NHS Trust | Seeding trusts |
| `RO198` | NHS Trust Site | Seeding trust sites (organisations) |
| `RO142` | Welsh Local Health Board | Seeding LHBs |
| `RO144` | Welsh Local Health Board Site | Seeding LHB sites |
| `RO261` | Integrated Care Board | ICB relationships (in `Rels` targets) |
| `RO210` | Clinical Commissioning Group (historic) | Historic relationships |
| `RO132` | (historic) | Historic relationships |

## Full organisation record structure

Returned by `/organisations/{ods_code}`. The fields we extract or care about
are marked.

```json
{
  "Organisation": {
    "Name": "NORTHERN CARE ALLIANCE NHS FOUNDATION TRUST",
    "Date": [
      {"Type": "Operational", "Start": "2001-04-01"},
      {"Type": "Legal", "Start": "2001-04-01", "End": "2021-09-30"}
    ],
    "OrgId": {
      "root": "2.16.840.1.113883.2.1.3.2.4.18.48",
      "assigningAuthorityName": "HSCIC",
      "extension": "RM3"                    // ← the ODS code
    },
    "Status": "Active",                       // ← "Active" or "Inactive"
    "LastChangeDate": "2021-10-15",           // ← date of the last ODS change
    "orgRecordClass": "RC1",
    "GeoLoc": {
      "Location": {
        "AddrLn1": "...",                     // ← address line 1
        "AddrLn2": "...",                     // ← address line 2
        "AddrLn3": "...",                     // ← address line 3
        "Town": "...",                        // ← city / town
        "County": "...",
        "PostCode": "...",                    // ← postcode
        "Country": "ENGLAND",
        "UPRN": 10007553984
      }
    },
    "Contacts": {
      "Contact": [
        {"type": "tel", "value": "..."},      // ← telephone
        {"type": "http", "value": "..."}      // ← website
      ]
    },
    "Roles": {
      "Role": [
        {
          "id": "RO197",
          "uniqueRoleId": 102782,
          "primaryRole": true,
          "Date": [{"Type": "Operational", "Start": "2001-04-01"}],
          "Status": "Active"
        }
      ]
    },
    "Rels": {                                // ← operational/managed relationships
      "Rel": [
        {
          "Date": [
            {"Type": "Operational", "Start": "2020-04-01", "End": null},
            {"Type": "Legal", "Start": "2020-04-01", "End": "2021-09-30"}
          ],
          "Status": "Active",
          "Target": {
            "OrgId": {"extension": "QOP"},    // ← target ODS code
            "PrimaryRoleId": {"id": "RO261"}  // ← target role (ICB)
          },
          "id": "RE5",                         // ← relationship type (see below)
          "uniqueRelId": 696688
        }
      ]
    },
    "Succs": {                               // ← legal succession (mergers etc.)
      "Succ": [
        {
          "uniqueSuccId": 38096,
          "Date": [{"Type": "Legal", "Start": "2021-10-01"}],
          "Type": "Successor",                // ← "Successor" or "Predecessor"
          "Target": {
            "OrgId": {"extension": "RM3"},    // ← successor/predecessor ODS code
            "PrimaryRoleId": {"id": "RO197"}
          }
        }
      ]
    }
  }
}
```

### Fields we extract

The sync (`_extract_ord_fields` in `ods_update.py`) extracts:

| ODS field | Model field (Organisation) | Model field (Trust) |
|---|---|---|
| `Name` | `name` | `name` |
| `GeoLoc.Location.AddrLn1` | `address1` | `address_line_1` |
| `GeoLoc.Location.AddrLn2` | `address2` | `address_line_2` |
| `GeoLoc.Location.AddrLn3` | `address3` | — |
| `GeoLoc.Location.Town` | `city` | `town` |
| `GeoLoc.Location.County` | `county` | — |
| `GeoLoc.Location.PostCode` | `postcode` | `postcode` |
| `Contacts.Contact[type=tel]` | `telephone` | `telephone` |
| `Contacts.Contact[type=http]` | `website` | `website` |
| `LastChangeDate` | (report only, not stored) | (report only, not stored) |
| `Status` | (not extracted — `active` is managed via the merger/closure workflow) | (same) |

The sync does **not** extract `Status` (Active/Inactive) into the `active`
field. Deactivation is a business event handled by the merger/closure workflow
(see `temporal-history.md` and `merger-handling.md`), not by the sync.

## `Rels` — operational and managed relationships

The `Rels` block records **operational and managed relationships** — e.g.
which ICB a trust reports to, which trust a site belongs to. These are
distinct from `Succs` (legal succession).

Each `Rel` has:

| Field | Description |
|---|---|
| `id` | Relationship type code (see below). |
| `Status` | `"Active"` or `"Inactive"`. |
| `Date` | List of `{Type, Start, End}` — `Type` is `"Operational"` or `"Legal"`. |
| `Target.OrgId.extension` | The target organisation's ODS code. |
| `Target.PrimaryRoleId.id` | The target organisation's role (e.g. `RO261` for ICB). |
| `uniqueRelId` | ODS internal ID for this relationship instance. |

### Relationship type codes we see

| Code | Meaning | Example |
|---|---|---|
| `RE5` | Managed by / reports to | A trust (`RO197`) reporting to an ICB (`RO261`) |
| `RE8` | Operates / is operated by | A trust operating under an ICB |

`RE5` and `RE8` are the only `Rel` types we've observed on trust records.
Both point to ICBs (`RO261`) in current data; historically they pointed to
CCGs (`RO210`) and earlier commissioning bodies (`RO132`).

> **We do not auto-populate membership tables from `Rels`.** The `Rels` block
> records operational relationships, which can be ambiguous and can change
> independently of the legal succession. Membership table updates go through
> the admin actions or the `reassign_*` helpers. The `Rels` block is useful
> for understanding what ODS thinks the current relationship is, but it is
> not the sanctioned write path.

## `Succs` — legal succession (mergers, acquisitions, splits)

The `Succs` block records **legal succession** — the corporate-law
relationship between entities when a merger, acquisition, split, or
closure occurs. This is the block that tells you "this trust was absorbed
into that trust on this date."

Each `Succ` has:

| Field | Description |
|---|---|
| `Type` | `"Successor"` or `"Predecessor"` (see below). |
| `Date` | List of `{Type, Start}` — `Type` is `"Legal"`. The `Start` is the legal succession date. |
| `Target.OrgId.extension` | The target organisation's ODS code. |
| `Target.PrimaryRoleId.id` | The target organisation's role. |
| `uniqueSuccId` | ODS internal ID for this succession event. |
| `forwardSuccession` | (optional) `true` if this is a forward reference from a predecessor. |

### `Type` semantics

| Type | Meaning | Example |
|---|---|---|
| `"Successor"` | **This** organisation was absorbed into / replaced by the target. | Pennine Acute (`RW6`) has `Type: "Successor"` → `RM3` (Northern Care Alliance) and → `R0A` (Manchester University). Pennine Acute ceased to exist; its children moved to the successors. |
| `"Predecessor"` | **This** organisation absorbed / replaced the target. | Northern Care Alliance (`RM3`) has `Type: "Predecessor"` → `RMK` (a historic trust that was absorbed into Salford Royal, which later became NCA). |

The `Type` is from the perspective of the organisation whose record you're
reading. A merger between A and B producing C will appear as:
- On A's record: `Type: "Successor"` → C
- On B's record: `Type: "Successor"` → C
- On C's record: `Type: "Predecessor"` → A, and `Type: "Predecessor"` → B

### Worked example: Pennine Acute (`RW6`)

Pennine Acute Hospitals NHS Trust (`RW6`) was dissolved on 1 October 2021.
Its `Succs` block:

```json
"Succs": {"Succ": [
  {
    "Type": "Successor",
    "Date": [{"Type": "Legal", "Start": "2021-10-01"}],
    "Target": {"OrgId": {"extension": "RM3"}}   // → Northern Care Alliance
  },
  {
    "Type": "Successor",
    "Date": [{"Type": "Legal", "Start": "2021-10-01"}],
    "Target": {"OrgId": {"extension": "R0A"}}   // → Manchester University
  },
  {
    "Type": "Predecessor",
    "Date": [{"Type": "Legal", "Start": "2002-04-01"}],
    "Target": {"OrgId": {"extension": "RMK"}},  // ← a trust absorbed in 2002
    "forwardSuccession": true
  }
]}
```

This tells us:
- `RW6` was absorbed into **two** successors (`RM3` and `R0A`) on
  2021-10-01 — a split, not a simple acquisition.
- `RW6` itself absorbed `RMK` (and others) on 2002-04-01 when it was created.

### Why we do not auto-populate succession tables from `Succs`

The succession tables (`TrustSuccession`, `OrganisationSuccession`,
`PaediatricDiabetesUnitSuccession`) are populated **manually via the admin**,
not automatically from the `Succs` block. The reasons:

1. **Ambiguity.** A single trust can have multiple `Successor` entries
   (Pennine Acute has two: `RM3` and `R0A`). ODS does not tell us which
   children went to which successor — that requires a decision.
2. **`Rels` vs `Succs`.** The `Rels` block (operational relationships) is
   distinct from `Succs` (legal succession). A child organisation's `Rels`
   may show a different parent than its `Succs` would suggest, because
   operational and legal changes can happen on different dates.
3. **Semantic mapping.** ODS does not distinguish between "merger",
   "acquisition", "rename", "closure", and "split" — it only records
   `Successor` / `Predecessor` links. Mapping these to our
   `succession_type` choices requires human judgement.

The dry-run report **surfaces** the `Succs` block (see `backfill-plan.md`
Step 2) so operators can see whether a change is the consequence of a
merger and record it manually. The `backfill_*` helpers
(see `backfill-plan.md` Part 2) are the sanctioned write path for
historical succession events.

## The 185-day limit

The `/sync` endpoint has a **hard limit of 185 days** into the past. A
request with `LastChangeDate` older than 185 days returns an error:

```
ODS API error: changes to organisations greater than 185 days ago cannot be
retrieved from the NHS ODS API.
```

This is enforced in `fetch_updated_organisations` and in the `cron`
management command's `--time-frame` validation (1-185).

For changes older than 185 days, the ODS API cannot help. The historical
state must be researched manually (e.g. from the `Succs` block of the
current record, which records historic predecessor links, or from ODS Trac
bulk dumps) and inserted via the `backfill_*` helpers — see
`backfill-plan.md` Part 2.

## Other APIs (not used for ODS sync)

The `ods_calls.py` docstring also references `https://api.nhs.uk/service-search`,
a separate API that requires an API key and returns a different structure
(with `ODSCode`, `OrganisationName`, `Latitude`, `Longitude`, etc.). This
is used by some seeding functions but not by the ODS sync or the temporal
history layer. It is out of scope for this document.

## Code reference

| Function | File | Endpoint |
|---|---|---|
| `fetch_updated_organisations` | `general_functions/ods_update.py` | `/sync` |
| `get_organisation` | `general_functions/ods_update.py` | `/organisations/{ods_code}` |
| `fetch_organisation_by_ods_code` | `general_functions/organisation_from_ods_code.py` | `/organisations/{ods_code}` |
| `all_nhs_hospitals_list` | `general_functions/ods_calls.py` | `/organisations?PrimaryRoleId=...` |
| `_extract_ord_fields` | `general_functions/ods_update.py` | (parses the full record) |
| `_extract_succession_info` | `general_functions/ods_update.py` | (parses the `Succs` block) |
| `update_organisation_model_with_ORD_changes` | `general_functions/ods_update.py` | (orchestrates the sync) |
