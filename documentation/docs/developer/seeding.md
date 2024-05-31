---
title: Seeding the RCPCH NHS Organisations service
author: Dr Simon Chapman
---

Seeding the database happens on initial migration (`002_seed_abstraction_levels`). This creates models for:

- London Boroughs
- Integrated Care Boards
- NHS England Regions
- Countries

Each one of these is associated with GIS shapes data loaded in from .csv in the `shape_files` folder. This goes through a LayerMapping step beforehand.

Subsequent seeding happens then from the command line and adds:

- Organisations
- Trusts
- Local Health Boards (Wales)
- Paediatric Diabetes Units
- OPENUK Networks

To run this after initial migration therefore from the command line within the docker instance it is necessary to:

```console
python manage.py seed --model all
```

If only individual models need seeding the `--model` attribute accepts these parameters:
`abstraction_levels` (this adds ODS codes to the existing ICBs, London Boroughs, NHS England regions, as well as ONS GSS codes to the Countries)
`trusts`
`organisations`
`pdus`
`all`
