---
title: Maintaining the RCPCH NHS Organisations service
author: Dr Simon Chapman
---

The main reason to have the RCPCH NHS Organisations service is to maintain current lists of active organisations, as well as their relationships with paediatric networks and other health regions. As political decisions are made, so the health geography mapping can change, so periodic maintenance of the lists becomes necessary.

## The ODS (Organisation Dataservice) ORD (Organisation Reference Data) API

This service is the national standard and provided by [NHS Digital](https://digital.nhs.uk/developer/api-catalogue/organisation-data-service-ord)

It is used to maintain the lists in the RCPCH NHS Organisations API up to date. In particular, the endpoint `/sync?LastChangeDate=` returns a large list of updates to organisational data.

Functions in the `ods_update` file in `general_functions` can make periodic calls to this endpoint and update any records in the Trust and Organisation tables if any have been published.

**NOTE**: This only updates Trusts and Organisations. Any changes in paediatric network membership (eg Paediatric Diabetes Units) have to be done manually. This is best done on the command line using a growing list of functions.

## Merger

The command line can be invoked in the docker instance with:

```console
docker compose exec -it django bash
python manage.py merger .....
```

This accepts the attributes:
`--organisations`: this is mandatory and represents a list of ODS codes of organisations. Note this will not work for trusts. A minimum of 1 organisation must be provided.
`--create` or `--delete`: one of these must be provided. 
*Create*: This looks up the ODS code provided against the ORD API and persists the details in the Organisation table. It creates a relationship between the new organisation and a parent Trust/Local Health Board and if in England, an NHS Region and Integrated Care Board also. It also looks up against lists in `constants` for any matching membership of Paediatric Diabetes Units, OPEN UK Networks. If there is no relationship, it will prompt the user to confirm that they want to continue with organisation creation. It should be possible to add this relationship at a later date, but this is currently not supported
*Delete*: Since the Organisation does not have referential integrity with its parent or related regions, the user is asked to confirm that they want to continue with deletion. A summary of the organisation's membership is logged to the console. Note that if the organisation is the only one associated with a paediatric diabetes unit record or openuk network record, that will leave that association broken. If the organisation is added back, that relationship is recreated.
