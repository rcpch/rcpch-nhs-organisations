from django.apps import apps as django_apps

import os
from django.contrib.gis.utils import LayerMapping

app_config = django_apps.get_app_config("hospitals")
app_path = app_config.path

Jersey_Boundary_File = os.path.join(app_path, "shape_files", "Jersey", "CLC06_UK.shp")


def load_jersey_boundaries():
    JerseyBoundaries = django_apps.get_model("hospitals", "JerseyBoundaries")
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


def create_jersey_country():
    """
    Create Jersey country object
    Note that the geom field is not populated
    """
    Country = django_apps.get_model("hospitals", "Country")
    jersey = Country(
        boundary_identifier="E92000003",
        name="Jersey",
        welsh_name="",
        bng_e=None,
        bng_n=None,
        long=2.1313,
        lat=49.2144,
        globalid="",
        geom=None,
    )
    jersey.save()
    return jersey
