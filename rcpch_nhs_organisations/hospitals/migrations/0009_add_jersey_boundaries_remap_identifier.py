# python imports
import os

# django imports
from django.db import migrations

# from django.apps import apps as django_apps
from django.apps import apps as django_apps
from django.contrib.gis.utils import LayerMapping

Country = django_apps.get_model("hospitals", "Country")

# Auto-generated `LayerMapping` dictionary for JerseyBoundary model
jerseyboundary_mapping = {
    "boundary_identifier": "GID_0",
    "name": "COUNTRY",
    "geom": "MULTIPOLYGON",
}

# Get the path to the shape file
app_config = django_apps.get_app_config("hospitals")
app_path = app_config.path
jersey_shp_file_path = os.path.join(
    app_path, "shape_files", "gadm41_JEY_shp", "gadm41_JEY_0.shp"
)


def load_jersey_shape_file_mapping(apps, schema_editor):
    """
    Load the Jersey shape file mapping into the database

    This will create a new country object in the database with the boundaries of Jersey, using the unique identifier of JEY.
    The boundaries are loaded from the shape file located at the path jersey_shp_file_path.
    The JEY identifier needs later refactoring to E92000003
    """

    # Load the Jersey shape file mapping into the database
    lm = LayerMapping(
        Country,
        jersey_shp_file_path,
        jerseyboundary_mapping,
        transform=True,
        source_srs=4326,
        encoding="utf-8",
    )
    # Note that the target srs is 27700 so that the boundaries are in the same projection as the rest of the boundaries
    # in the database. By setting the SRID here of the source_srs to 4326, the LayerMapping will automatically transform
    # the boundaries to the target srs of 27700.

    lm.save(strict=True, verbose=True)


class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0008_alter_country_lat_alter_country_long"),
    ]

    operations = [
        migrations.RunPython(load_jersey_shape_file_mapping),
    ]
