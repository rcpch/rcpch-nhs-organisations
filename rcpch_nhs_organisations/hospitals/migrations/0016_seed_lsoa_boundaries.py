from django.db import migrations
from django.apps import apps as django_apps

import os
from django.contrib.gis.utils import LayerMapping

"""
Local Authority Districts May 2024 Boundaries UK BUC
https://geoportal.statistics.gov.uk/search?q=BDY_LAD%202024&sort=Title%7Ctitle%7Casc
"""

# Auto-generated `LayerMapping` dictionary for LowerLayerSuperOutputArea model
lowerlayersuperoutputarea_mapping = {
    "lsoa11cd": "LSOA11CD",
    "lsoa11nm": "LSOA11NM",
    "lsoa11nmw": "LSOA11NMW",
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

LSOA_2011_Boundaries_Super_Generalised_Clipped_BSC_EW_V4 = os.path.join(
    app_path,
    "shape_files",
    "LSOA_2011_Boundaries_Super_Generalised_Clipped_BSC_EW_V4",
    "LSOA_2011_EW_BSC_V4.shp",
)


def load(apps, schema_editor, verbose=True):
    LowerLayerSuperOutputArea = apps.get_model("hospitals", "LowerLayerSuperOutputArea")
    lm = LayerMapping(
        LowerLayerSuperOutputArea,
        LSOA_2011_Boundaries_Super_Generalised_Clipped_BSC_EW_V4,
        lowerlayersuperoutputarea_mapping,
        transform=False,
        encoding="utf-8",
    )
    lm.save(strict=True, verbose=verbose)


class Migration(migrations.Migration):
    dependencies = [
        ("hospitals", "0015_lowerlayersuperoutputarea"),
    ]

    operations = [migrations.RunPython(load)]
