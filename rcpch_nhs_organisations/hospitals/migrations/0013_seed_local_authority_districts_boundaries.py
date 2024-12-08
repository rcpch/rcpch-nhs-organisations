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
