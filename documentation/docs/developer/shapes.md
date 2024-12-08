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

## Importing a .shp file

1. Download the file from whichever source (using the LocalAuthorityDistrict model as an example)
2. On the command line:
    `python manage.py ogrinspect rcpch_nhs_organisations/hospitals/shape_files/Local_Authority_Districts_May_2024_Boundaries_UK_BUC/LAD_MAY_2024_UK_BUC.shp LocalAuthorityDistrict --srid 27700 --mapping --multi`
    This will generate the code for the model (don't forget to import in `__init__.py` and add to admin):

    ```python
    class LocalAuthorityDistrict(models.Model):
        lad24cd = models.CharField(max_length=9)
        lad24nm = models.CharField(max_length=36)
        lad24nmw = models.CharField(max_length=24)
        bng_e = models.BigIntegerField()
        bng_n = models.BigIntegerField()
        long = models.FloatField()
        lat = models.FloatField()
        globalid = models.CharField(max_length=38)
        geom = models.MultiPolygonField(srid=27700)
    

    # Auto-generated `LayerMapping` dictionary for LocalAuthorityDistrict model
    localauthoritydistrict_mapping = {
        'lad24cd': 'LAD24CD',
        'lad24nm': 'LAD24NM',
        'lad24nmw': 'LAD24NMW',
        'bng_e': 'BNG_E',
        'bng_n': 'BNG_N',
        'long': 'LONG',
        'lat': 'LAT',
        'globalid': 'GlobalID',
        'geom': 'MULTIPOLYGON',
    }
    ```

3. Create a migration for the new model (check previous examples, as RCPCH tend to add this as an abstract model, so this example diverges from actual practice for simplicity)
    `python manage.py makemigrations`

4. Create an empty migration
    `python manage.py makemigrations hospitals --name seed_local_authority_districts_boundaries --empty`

5. Create a custom function in the empty migration to import the .shp file geometry data using the layer map created earlier.

    ```python
    from django.db import migrations
    from django.apps import apps as django_apps

    import os
    from django.contrib.gis.utils import LayerMapping

    """
    Local Authority Districts May 2024 Boundaries UK BUC
    https://geoportal.statistics.gov.uk/search?q=BDY_LAD%202024&sort=Title%7Ctitle%7Casc
    """

    # Auto-generated `LayerMapping` dictionary for LocalAuthorityDistrict model
    localauthoritydistrict_mapping = {
        "lad24cd": "LAD24CD",
        "lad24nm": "LAD24NM",
        "lad24nmw": "LAD24NMW",
        "bng_e": "BNG_E",
        "bng_n": "BNG_N",
        "long": "LONG",
        "lat": "LAT",
        "globalid": "GlobalID",
        "geom": "MULTIPOLYGON",
    }


    # Boundary files

    app_config = django_apps.get_app_config("hospitals")
    app_path = app_config.path

    Local_Authority_Districts_May_2024_Boundaries_UK_BUC = os.path.join(
        app_path,
        "shape_files",
        "Local_Authority_Districts_May_2024_Boundaries_UK_BUC",
        "LAD_MAY_2024_UK_BUC.shp",
    )


    def load(apps, schema_editor, verbose=True):
        LocalAuthorityDistrict = apps.get_model("hospitals", "LocalAuthorityDistrict")
        lm = LayerMapping(
            LocalAuthorityDistrict,
            Local_Authority_Districts_May_2024_Boundaries_UK_BUC,
            localauthoritydistrict_mapping,
            transform=False,
            encoding="utf-8",
        )
        lm.save(strict=True, verbose=verbose)


    class Migration(migrations.Migration):
        dependencies = [
            ("hospitals", "0012_localauthoritydistrict"),
        ]

        operations = [migrations.RunPython(load)]
    ```

6. Migrate the changes
    `python manage.py migrate`
7. If successful you should see:

    ```console
    ....
    Saved: LocalAuthorityDistrict object (360)
    Saved: LocalAuthorityDistrict object (361)
    OK
    ```

8. This populates the model with the geometry files for mapping all the local authority boundaries, the names and codes. The next step is to hook this up to the other models.