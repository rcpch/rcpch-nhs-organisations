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
  - Northern Island
  - Jersey
  - Isle of Man

Each one of these is associated with GIS shapes data loaded in from .csv in the `shape_files` folder. This goes through a LayerMapping step beforehand. We don't have a shape file for the Isle of Man yet.

Subsequent seeding happens then from the command line and adds:

- Organisations
- Trusts
- Local Health Boards (Wales)
- Paediatric Diabetes Units
- OPENUK Networks

To run this after initial migration therefore from the command line within the docker instance it is necessary to:
To run this after initial migration therefore from the command line it is necessary to:

```console
python manage.py seed --level all
```

If only individual models need seeding the `--model` attribute accepts these parameters:
`abstraction_levels` (this adds ODS codes to the existing ICBs, London Boroughs, NHS England regions, as well as ONS GSS codes to the Countries)
`trusts`
`organisations`
`pdus`
`all`  - Adds all the above as well

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
`general_functions/membership.py`) or when a new organisation is created (via
the `mergers --create` command).
