---
title: Ordnance Survey and Boundaries
author: Dr Simon Chapman
---

## Boundaries

Healthcare often reports outcomes according to health geographies - for example at the level of Integrated Care Boards (ICBs) in England, but many like to have their data in administrative contexts also. Deprivation index, for example, which has a large impact on health, is not measured across health geographies, but across administrative ones.

### Lower Layer Super Output Areas (LSOA)

The index of multiple deprivation [for which RCPCH has another repository](https://github.com/rcpch/rcpch-census-platform) relies on census data to summarize different societal and population features to rank geographical units in order of most deprived to least deprived - the higher the score, the better off the region is. IMD uses Lower Layer Super Output Areas (LSOA) whose boundaries were last defined in 2011. These boundaries don't change much, but were updated last in 2021. They are not meant to change to allow longitudinal data to be gathered and be meaningful. LSOAs are chosen to be the way they are as they have population numbers as their common feature (1500 individuals or 650 households) - geographically distributed LSOAs cover a larger area, but in cities they are small as population numbers per unit area are larger.

The last index of multiple of deprivation data for England was published in 2019 and used the 2011 LSOAs, since those were the latest boundaries. Since then, there has been the census of 2021, with the LSOA boundaries updated the same year. The decision on which boundaries will be included in the next iteration of IMD will be decided bythe Office for National Statistics (ONS) and the Ministry of Housing, Communities & Local Government (MHCLG) (now the Department for Levelling Up, Housing and Communities).

### Local Authorities

These are administrative geography boundaries. LSOAs conveniently fit neatly inside LAs but the LA boundaries change more frequently.

**Local Authority Districts (LADs)** are a unit of local administration and statistical geography, and their structure varies across the country. Depending on the region, LADs can take different forms:

#### Two-Tier Systems

In some areas, LADs correspond to district councils, which operate alongside a county council that provides upper-tier services (e.g., Hertfordshire has multiple district councils, such as Watford Borough Council, each of which is an LAD).

#### Unitary Authorities

In other areas, LADs correspond to unitary authorities, which combine the responsibilities of both district and county councils into a single authority.

#### Metropolitan Boroughs

In metropolitan areas, LADs correspond to metropolitan boroughs (e.g., Manchester Metropolitan Borough), which provide local services. These boroughs are part of a wider metropolitan county (e.g., Greater Manchester) that handles strategic functions like transport and policing.

##### London

London is unique, with 32 London Boroughs serving as LADs, plus the City of London, which is its own LAD. The Greater London Authority (GLA) oversees strategic citywide functions but is not an LAD

LAD boundaries change quite frequently. Each LAD has its own unique identifier and the boundaries and membership of LADs, which LSOAs they comprise, are updated by the ONS and published in the form of [look up tables](https://geoportal.statistics.gov.uk/documents/ons::local-authority-districts-counties-and-unitary-authorities-april-2023-map-in-the-uk/about?path=)

## Implications for RCPCH NHS Organisations

Although local authorities are not health geographies, local government has an interest in the health of the local population, and a responsibility for all functions of government that influence health (from housing, to green space, to transport etc), so RCPCH stores the relationship between the organisations that care for children and their local authority district.
