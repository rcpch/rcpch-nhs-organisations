# Generated for: flag ODS-divergent organisation codes (sites ODS considers
# Inactive but the RCPCH audit system still uses because the site is still
# open). See documentation/docs/developer/backfill.md "ODS-divergent
# organisation codes".
from django.db import migrations, models


def flag_divergent_organisations(apps, schema_editor):
    """Set diverged_from_ods and ods_replacement_code on the seeded
    organisation rows listed in ODS_DIVERGENT_ORGANISATIONS.

    This is a one-off data fix: the constants table is the curated source
    of truth for which codes are divergent. The flag is what the backfill,
    admin and API use to identify these codes at query time.
    """
    # Import here (not at module level) so the migration is self-contained
    # and doesn't depend on the constants module being importable at
    # migration-write time.
    from rcpch_nhs_organisations.hospitals.constants.ods_divergent_codes import (
        ODS_DIVERGENT_ORGANISATIONS,
    )

    Organisation = apps.get_model("hospitals", "Organisation")
    for entry in ODS_DIVERGENT_ORGANISATIONS:
        Organisation.objects.filter(ods_code=entry["ods_code"]).update(
            diverged_from_ods=True,
            ods_replacement_code=entry.get("ods_replacement_code"),
        )


def clear_divergent_flags(apps, schema_editor):
    """Reverse: clear the flags on the divergent organisations."""
    Organisation = apps.get_model("hospitals", "Organisation")
    Organisation.objects.filter(diverged_from_ods=True).update(
        diverged_from_ods=False,
        ods_replacement_code=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0030_fix_geocode_coordinates_srid_to_4326"),
    ]

    operations = [
        migrations.AddField(
            model_name="organisation",
            name="diverged_from_ods",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "True if ODS considers this organisation Inactive but "
                    "the RCPCH audit system still uses the code because the "
                    "site is still open and still under the same parent "
                    "trust. ODS retired the code for administrative reasons "
                    "(re-coding, issuing a parallel record, folding into a "
                    "parent site), not because the site closed. See "
                    "ODS_DIVERGENT_ORGANISATIONS constants and "
                    "documentation/docs/developer/backfill.md."
                ),
            ),
        ),
        migrations.AddField(
            model_name="organisation",
            name="ods_replacement_code",
            field=models.CharField(
                blank=True,
                default=None,
                help_text=(
                    "If diverged_from_ods, the active ODS code for the same "
                    "site, where one exists. When the consuming software is "
                    "ready to switch, the fix is to update its references "
                    "from ods_code to ods_replacement_code. Null when ODS "
                    "folded the site into a parent site record rather than "
                    "issuing a twin."
                ),
                max_length=10,
                null=True,
            ),
        ),
        migrations.RunPython(
            flag_divergent_organisations,
            reverse_code=clear_divergent_flags,
        ),
    ]
