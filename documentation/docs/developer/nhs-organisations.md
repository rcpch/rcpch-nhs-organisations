---
title: NHS Organisational Structure
author: Dr Simon Chapman
---

The NHS has had several doses of reorganisation since its creation on 5th July 1948.

## The devolved nations

The 4 devolved nations have slightly different implementations of the NHS.

### England

[NHS England](https://www.england.nhs.uk/) receives and distributes funding for health care in England ([£168.8 billion in 2023/4](https://www.england.nhs.uk/)).

Public Health England was dissolved on 18th August 2020, and replaced by the [UK Health Security Agency](https://www.gov.uk/government/organisations/uk-health-security-agency) and the [Office for Health Improvement and Disparities](https://www.gov.uk/government/organisations/office-for-health-improvement-and-disparities), the latter part of the [Department of Health and Social Care](https://www.gov.uk/government/organisations/department-of-health-and-social-care).

NHS England is responsible for commissioning GP, dental, pharmacy and some ophthalmology services. It also allocates resources to 42 Integrated Care Boards (ICBs) which commission services across primary and secondary care within their region. ICBs came into being on 1st July 2022 and replaced a system of Clinical Care Groups (CCGs).

The ICBs fit neatly inside a smaller number of larger NHS England regions.

### Wales

[NHS Wales](https://www.nhs.wales/) receives money from UK Central Government and distributes it across the 7 Health Boards and 3 NHS Trusts (the Welsh Ambulance Services Trust, Velindre University NHS Trust, Public Health Wales)

### Scotland

[NHS Scotland](https://www.scot.nhs.uk/) also receives a money from UK Central Government and distributes it across 14 Health Boards, each of which are responsible for the acute and primary care services in their regions.

### Northern Ireland

[The Department for Health, Social Services and Public Safety for Northern Ireland](https://www.health-ni.gov.uk/) receives money from the UK Treasury and has responsibility for health and social care, public health and public safety. Through its health and social care board, it administers 5 commissioning groups which commmission health and social care services across 5 health and social care trusts with the same boundaries. The Northern Ireland Ambulance Service is national and provides emergency ambulance services to the whole country.

## Implications for RCPCH NHS Organisations

The RCPCH services rely on accurate and up to date lists of organisations that serve the needs of children. There are lists of NHS organisations in different formats, particularly from NHS digital which hosts 2 APIs:

1. **[Organisation Data Service](https://digital.nhs.uk/developer/api-catalogue/organisation-data-service-ord)** known as the 'ODS'. Each organisation has an ODS code. The ODS API is not authenticated. Any updates in organisations, for example as a consequence of mergers, are also published here and this endpoint is polled on a scheduled basis,
2. **[NHS Digital APIs](https://digital.nhs.uk/developer/getting-started)**: a wide range of APIs with some overlap with the ODS. It requires an API key.

Lists of organisations that care for children are important for the RCPCH and have been curated by pulling from these APIs. In themselves, though, this is not enough, as RCPCH reports also need to draw reference the NHS and ONS regions (Trusts/ICBs etc) within which the organisations sit.

This information is available mostly from the [Office of National Statistics](https://www.ons.gov.uk). This has its own standardised identifiers for regions but also provides boundary data for mapping.

Finally, RCPCH also maintains memberships of several clinical networks, such as the OPEN UK networks for childhood epilepsy and the paediatric diabetes national and regional networks.
