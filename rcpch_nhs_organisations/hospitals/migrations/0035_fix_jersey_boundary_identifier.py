# Generated for the Jersey boundary identifier correction.

from django.db import migrations


def fix_jersey_boundary_identifier(apps, schema_editor):
    """
    Correct Jersey's boundary_identifier from the erroneous E92000003
    (an England-prefixed GSS code that actually denotes the North East
    region of England) back to JEY — the value the GADM shape file
    (gadm41_JEY_shp) carries in its GID_0 field, and Jersey's ISO
    3166-1 alpha-3 code.

    Jersey is a Crown Dependency, not part of the UK, so it has no
    E/W/N/S-prefixed GSS code. Migration 0010 had overwritten the
    correct JEY value (loaded by 0009) with E92000003; this reverses
    that for any database that already applied 0010. Fresh installs
    are unaffected (0009 loads JEY, and this update is a no-op).
    """
    Country = apps.get_model("hospitals", "Country")
    Country.objects.filter(name="Jersey").update(boundary_identifier="JEY")


class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0034_increase_organisation_name_max_length"),
    ]

    operations = [
        migrations.RunPython(fix_jersey_boundary_identifier),
    ]
