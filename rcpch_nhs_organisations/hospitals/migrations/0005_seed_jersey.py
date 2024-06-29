from django.db import migrations
from django.apps import apps as django_apps

import os
from django.contrib.gis.utils import LayerMapping

app_config = django_apps.get_app_config("hospitals")
app_path = app_config.path

Jersey_Boundary_File = os.path.join(app_path, "shape_files", "Jersey", "CLC06_UK.shp")


def load_jersey_boundaries(apps, schema_editor, verbose=True):
    JerseyBoundaries = apps.get_model("hospitals", "JerseyBoundaries")
    jerseyboundaries_mapping = {
        "objectid": "OBJECTID",
        "shape_id": "ID",
        "area_ha": "Area_Ha",
        "remark": "Remark",
        "code_06": "CODE_06",
        "shape_leng": "Shape_Leng",
        "shape_area": "Shape_Area",
        "geom": "MULTIPOLYGON",
    }
    lm = LayerMapping(
        JerseyBoundaries,
        Jersey_Boundary_File,
        jerseyboundaries_mapping,
        transform=False,
        encoding="iso-8859-1",
    )
    lm.save(strict=True, verbose=True)


class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0004_jerseyboundaries"),
    ]

    operations = [migrations.RunPython(load_jersey_boundaries)]
