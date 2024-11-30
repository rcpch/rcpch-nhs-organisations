# python imports
import logging

# Django imports
from django.db import migrations

logger = logging.getLogger(__name__)


def refactor_jersey_boundary_identifier(apps, schema_editor):
    """
    Refactor the Jersey Boundary Identifier from JEY to E92000003
    """
    logger.info("Refactoring Jersey Boundary Identifier from JEY to E92000003")
    Country = apps.get_model("hospitals", "Country")
    try:
        Country.objects.filter(name="Jersey").update(boundary_identifier="E92000003")
        logger.info("Jersey General Hospital created and all relationships added....")
    except Exception as e:
        logger.error(f"Error refactoring Jersey Boundary Identifier: {e}")
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0009_add_jersey_boundaries_remap_identifier"),
    ]

    operations = [
        migrations.RunPython(refactor_jersey_boundary_identifier),
    ]
