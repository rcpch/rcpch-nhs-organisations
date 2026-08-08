---
title: Seeding the RCPCH NHS Organisations service
author: Dr Simon Chapman
---

Seeding the database happens on initial migration (`002_seed_abstraction_levels`). This creates models for:

- London Boroughs
- Integrated Care Boards
- NHS England Regions
- Countries
  - England
  - Wales
  - Scotland
  - Northern Ireland
  - Jersey
  - Isle of Man

Each one of these is associated with GIS shapes data loaded in from .csv in the `shape_files` folder. This goes through a LayerMapping step beforehand. We don't have a shape file for the Isle of Man yet.

Subsequent seeding happens from the command line and adds:

- Organisations
- Trusts
- Local Health Boards (Wales)
- Paediatric Diabetes Units
- OPENUK Networks

To run this after initial migration from the command line:

```console
python manage.py seed --level all
```

If only individual models need seeding the `--level` attribute accepts these parameters:
`abstraction_levels` (this adds ODS codes to the existing ICBs, London Boroughs, NHS England regions, as well as ONS GSS codes to the Countries)
`trusts`
`organisations`
`pdus`
`all`  - Adds all the above

### Temporal history baseline

Migration `0024_baseline_version_backfill` runs automatically after the entity
version tables are created. It creates a baseline `*Version` row for every
existing entity (Organisation, Trust, LocalHealthBoard, IntegratedCareBoard,
NHSEnglandRegion, PaediatricDiabetesUnit, PaediatricDiabetesNetwork), with
`valid_from = today` and `valid_to = NULL`. This snapshots the current state
as the baseline so that every change from install day forward is captured.

See [temporal-history.md](temporal-history.md) for the full design. Note that
the baseline backfill does **not** create relationship membership rows —
those are created on demand when a relationship changes (via the helpers in
`general_functions/membership.py`), when a new organisation is created (via
the `mergers --create` command), or by the backfill commands that recover
historical memberships from the ODS API (see
[backfill.md](backfill.md),
[icb-history.md](icb-history.md), and
[pdu-history.md](pdu-history.md)).

### ICB boundary fields

The `IntegratedCareBoardBoundaries` abstract base class has boundary geometry
fields (`bng_e`, `bng_n`, `long`, `lat`, `globalid`, `geom`) that are now
**nullable**. The existing 42 ICBs have geometry loaded from ONS shapefiles
(`Integrated_Care_Boards_April_2023_EN_BSC` in the `shape_files` folder).
New ICBs created by the backfill (e.g. the 6 new ICBs from the 2026
reorganisation) do not have boundary data — the fields are left as `None`.
The long-term intention is to deprecate the geometry fields from this
project entirely and leave all boundary data to the
[RCPCH Census Platform](https://github.com/rcpch/rcpch-census-platform).
See [icb-history.md](icb-history.md) for details.

The `IntegratedCareBoard` model also has an `active` boolean field
(defaulting to `True`), mirroring the trust and PDU pattern. This allows
the closure workflow to set `active=False` on dissolved ICBs.
