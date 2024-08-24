---
title: Models in the RCPCH NHS Organisations service
author: Dr Simon Chapman
---

## Models and Database Schema

Health geographies are complicated and changing. The structures in England are not quite the same as Wales, different again from Scotland and Northern Ireland. Also territories such as Jersey and Guernsey have related structures.

### Organisation

This model sits at the centre of the API structure and all relationships with the organisational layers are with this. The organisation refers either to an acute or community hospital. It does not refer to GP services, pharmacies, ambulance trusts or other health organisations. All the organisations represented have some involvement in the care of children. The model has the following attributes:

```python
ods_code
name
website
address1
address2
address3
telephone
city
county
latitude
longitude
postcode
geocode_coordinates
active
published_at
```

RCPCH-NHS-Organisations uses postgis and therefore can store fields such as `Point`. This is because one aim of the API is to be able to return GeoJSON for mapping health boundaries to provide context to the child health organisations. In the seeding process, the database stores not only the names and relationships with these organisational structures, but also `.shp` files related to each. 

The unique identifier for the Organisation is the `ods_code` which usually comprises as its stem letter the 3 or 4 letter `ods_code` of its parent, followed by further numbers or letters.

The attributes in the Organisation model do not match exactly to NHS Digital fields so some mapping occurs in `update_organisation_model_with_ORD_changes()`, a function that can periodically call the ORD and update records if any changes have been published.

## Relationships

### Trust or Local Health Board

These are analagous and are seen as the parents of the Organisation. One Trust (England) or Local Health Board (Wales) can oversee many organisations. The parent Trust or Local Health Board also uses `ods_code` as its unique identifier, which tends to be shorter (only 3 letters usually). Address and contact number of these parents are stored in the model. For more detail on these, the ORD API returns information from the ODS code.

### Integrate Care Board

These govern only English organisations and each of the 42 also has its own `ods_cod`. Only name and code are stored in relation to ICBs and these are used largely to identify lists of Organisations or Trusts associated with them for national audit purposes. Shape boundaries are included here for mapping.

### NHS England Regions

These sit above the ICBs. They do not have `ods_codes` as they are regions, not statutory bodies. They have nationally recognised identifiers which are stored along with their names. As with ICBs, these are largely used for generating lists of organisations or trusts for audits. Shape boundaries are included here for mapping.

### Country

Only name and region codes are stored.  Shape boundaries are included here for mapping.

### Professional Networks

This continues to evolve but it is expected that as this project develops, more paediatric networks will be included. Currently only diabetes and epilepsy national networks are included. Currently only the names and unique identifiers are stored, but in time if needed it is expected that the names/contacts of network leads and any other relevant network information might be stored.

- OPENUK Networks: These are regional networks for Paediatric Epilepsy. Although members are meant to pay to contribute to their maintenance, not all do, so some organisations that care for children with Epilepsy are allocated to a network but may not formally be paid-up members. These each have a unique identifier.
- Paediatric Diabetes Networks: These are important particuarly for the diabetes audit, since any centres that look after children with diabetes are expected to participate in network governance and activity. These do not have a formal identifier but have been allocated one for the purposes of this project.
  