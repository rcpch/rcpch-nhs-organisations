---
title: NHS Child Health Context
author: Dr Simon Chapman
---

This service does not seek to replicate or replace datasources from which already describe the organisational structure of health care across the United Kingdom. There is however no specific resource that details the services specifically for children. By maintaining and curating lists of organisations (both official and unofficial) that look after children, as well as information about their scope of working and influence, it provides a resource for clinicians, researchers, policy makers and the executive alike to understand the organisational environment for children.

## Organisations

This is the lowest level of secondary care hierarchy currently stored. It is a curated list mostly of hospitals with direct responsibility for the care of children. The key identifier for organisations is the `ods code`. Lists of these are maintained by [NHS Digital Organisation Data Service(ODS)](https://digital.nhs.uk/services/organisation-data-service). and there is a user-friendly [website](https://www.odsdatasearchandexport.nhs.uk/). They are actively maintained with new lists updated every night at 2am. This same information can be accessed via their [Organisation Reference Data api (either FHIR or REST)](https://digital.nhs.uk/developer/api-catalogue/organisation-data-service-ord) and does not require an API key.

Information stored by RCPCH is updated against this and includes address and hospital phone numbers / emails, where available. In addition, RCPCH stores geolocation data for organisations as this allows them to be plotted on maps. 

Hospitals often have specific responsibilities for different aspects of child health. Some are regional centres for particular levels or types of treatment, and usually earn their right (and the funding) to carry out this work and be a designated centre. For many conditions (such as epilepsy and diabetes), they are part of larger regional networks to allow data gathering and dissemination of best practice. Currently RCPCH store information on:

- paediatric diabetes units: this includes their identifiers and network names
- epilepsy networks: this includes their identifiers and network names

## Trusts and Local Health Boards

There are 242 trusts or local health boards across England and Wales. These each also have an ODS code which tends to be only 3 characters in length (though some are longer) and they typically oversee the running of one or more organisations in their region. Trusts may occasionally merge or be acquired, and therefore reorganisation of these and their affilitations may often change. RCPCH returns lists of Trusts as maintained by the ORD, as well as their relationships with organisations and other health geographies.

## Health Geographies

Integrated Care Boards in England and Local Health Boards in Wales also have a commissioning role and typically cover a number of trusts in a region. These also have ODS codes. There are also boundary files for mapping provided by the [Office for National Statistics](https://www.ons.gov.uk/methodology/geography/ukgeographies/healthgeography). NHS Regions are the largest level of abstraction for health care in England and are included.

## Political Geographies

Although not directly influential on health care, local authorities have an interest in how their hospitals are run and how they support their patients in the community. Local authority district codes are therefore included in the the RCPCH API, as well Lower Level Super Output Areas (LSOAs) which are important for calculation of deprivation indices. This is important as deprivation is directly associated with a number of different health outcomes.
