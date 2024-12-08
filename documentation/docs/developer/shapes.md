---
title: Geojson, ONS boundary data and mapping
author: Dr Simon Chapman
---

## The UK government mapping data

Organisational geographies in the UK can be administrative, political/electoral and health. They are collected and published by the [Office for National Statistics](https://geoportal.statistics.gov.uk/)

The boundary files are published in different formats, from csv, and xml, to geojson and shp. The maps themselves come in different levels of detail. There is an excellent explainer by [David Callaghan](https://medium.com/digital-and-innovation-at-british-red-cross/generally-speaking-1647906d8edb) on behalf of the Red Cross.

1. BFE = Boundary, Full Extent
The boundary isn’t generalised and extends to the full “Extent of the Realm” (the area the UK covers at the average low tide [geography fun fact: the UK is bigger at low tide than at high tide]).

2. BFC = Boundary, Full Clipped
This boundary is also not generalised, but it is limited (clipped) to the coastline (the average area the UK covers at high tide).

3. BGC = Boundary, Generalised Clipped
The boundary is generalised to 20 metres and clipped to the coastline.

4. BSC = Boundary, Super Generalised Clipped
The boundary is generalised to 200 metres and clipped to the coastline.

5. BUC = Boundary, Ultra Generalised Clipped
The boundary is generalised to 500 metres and clipped to the coastline.

Generally, maps are used by RCPCH for data visualization purposes - they show users of the different RCPCH products how their services, or patients how they fit into the organisational geographies, and all depiction of this against societal factors such as deprivation, a well-known but poorly-understood driver of health inequality. This clearly has implications for clinicians and commissioners at all levels in a health system.

RCPCH in the main uses the most generalised views - this is because more detail means bigger files, and RCPCH is not a custodian of the boundaries, so the perspectives it is trying to illustrate are high level, and if more detail is needed, users are advised to seek it from official sources.

### Boundary to IMD

2011 LSOAs mapped to 2019 IMD data is a service fortunately already provided by [Consumer Data Research Centre](https://data.cdrc.ac.uk/dataset/index-multiple-deprivation-imd)