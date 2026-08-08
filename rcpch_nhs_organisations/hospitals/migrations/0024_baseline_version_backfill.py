# python imports
from datetime import date

# django imports
from django.db import migrations


def _baseline_valid_from():
    """
    The valid_from date for all baseline version rows.

    Using the date the migration runs (not a fixed date) so that the baseline
    represents 'the state of the world when temporal history was switched on'.
    Any change after this date will close the baseline row and open a new one.
    """
    return date.today()


def backfill_organisation_versions(apps, schema_editor):
    """
    Create a baseline OrganisationVersion row for every existing Organisation.
    Snapshots the mutable attributes. valid_to is NULL (current).
    """
    Organisation = apps.get_model("hospitals", "Organisation")
    OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")
    valid_from = _baseline_valid_from()

    rows = []
    for org in Organisation.objects.all():
        rows.append(
            OrganisationVersion(
                organisation=org,
                valid_from=valid_from,
                valid_to=None,
                name=org.name,
                website=org.website,
                address1=org.address1,
                address2=org.address2,
                address3=org.address3,
                telephone=org.telephone,
                city=org.city,
                county=org.county,
                latitude=org.latitude,
                longitude=org.longitude,
                postcode=org.postcode,
                geocode_coordinates=org.geocode_coordinates,
                active=org.active,
                published_at=org.published_at,
            )
        )
    if rows:
        OrganisationVersion.objects.bulk_create(rows)


def backfill_trust_versions(apps, schema_editor):
    Trust = apps.get_model("hospitals", "Trust")
    TrustVersion = apps.get_model("hospitals", "TrustVersion")
    valid_from = _baseline_valid_from()

    rows = []
    for trust in Trust.objects.all():
        rows.append(
            TrustVersion(
                trust=trust,
                valid_from=valid_from,
                valid_to=None,
                name=trust.name,
                address_line_1=trust.address_line_1,
                address_line_2=trust.address_line_2,
                town=trust.town,
                postcode=trust.postcode,
                country=trust.country,
                telephone=trust.telephone,
                website=trust.website,
                active=trust.active,
                published_at=trust.published_at,
            )
        )
    if rows:
        TrustVersion.objects.bulk_create(rows)


def backfill_local_health_board_versions(apps, schema_editor):
    LocalHealthBoard = apps.get_model("hospitals", "LocalHealthBoard")
    LocalHealthBoardVersion = apps.get_model("hospitals", "LocalHealthBoardVersion")
    valid_from = _baseline_valid_from()

    rows = []
    for lhb in LocalHealthBoard.objects.all():
        rows.append(
            LocalHealthBoardVersion(
                local_health_board=lhb,
                valid_from=valid_from,
                valid_to=None,
                name=lhb.name,
                welsh_name=lhb.welsh_name,
                bng_e=lhb.bng_e,
                bng_n=lhb.bng_n,
                long=lhb.long,
                lat=lhb.lat,
                globalid=lhb.globalid,
                geom=lhb.geom,
                publication_date=lhb.publication_date,
            )
        )
    if rows:
        LocalHealthBoardVersion.objects.bulk_create(rows)


def backfill_integrated_care_board_versions(apps, schema_editor):
    IntegratedCareBoard = apps.get_model("hospitals", "IntegratedCareBoard")
    IntegratedCareBoardVersion = apps.get_model(
        "hospitals", "IntegratedCareBoardVersion"
    )
    valid_from = _baseline_valid_from()

    rows = []
    for icb in IntegratedCareBoard.objects.all():
        rows.append(
            IntegratedCareBoardVersion(
                integrated_care_board=icb,
                valid_from=valid_from,
                valid_to=None,
                name=icb.name,
                bng_e=icb.bng_e,
                bng_n=icb.bng_n,
                long=icb.long,
                lat=icb.lat,
                globalid=icb.globalid,
                geom=icb.geom,
                publication_date=icb.publication_date,
            )
        )
    if rows:
        IntegratedCareBoardVersion.objects.bulk_create(rows)


def backfill_nhs_england_region_versions(apps, schema_editor):
    NHSEnglandRegion = apps.get_model("hospitals", "NHSEnglandRegion")
    NHSEnglandRegionVersion = apps.get_model("hospitals", "NHSEnglandRegionVersion")
    valid_from = _baseline_valid_from()

    rows = []
    for region in NHSEnglandRegion.objects.all():
        rows.append(
            NHSEnglandRegionVersion(
                nhs_england_region=region,
                valid_from=valid_from,
                valid_to=None,
                name=region.name,
                bng_e=region.bng_e,
                bng_n=region.bng_n,
                long=region.long,
                lat=region.lat,
                globalid=region.globalid,
                geom=region.geom,
                publication_date=region.publication_date,
            )
        )
    if rows:
        NHSEnglandRegionVersion.objects.bulk_create(rows)


def backfill_paediatric_diabetes_unit_versions(apps, schema_editor):
    PaediatricDiabetesUnit = apps.get_model(
        "hospitals", "PaediatricDiabetesUnit"
    )
    PaediatricDiabetesUnitVersion = apps.get_model(
        "hospitals", "PaediatricDiabetesUnitVersion"
    )
    valid_from = _baseline_valid_from()

    rows = []
    for pdu in PaediatricDiabetesUnit.objects.all():
        rows.append(
            PaediatricDiabetesUnitVersion(
                paediatric_diabetes_unit=pdu,
                valid_from=valid_from,
                valid_to=None,
                unit_name=getattr(pdu, "unit_name", None),
                active=pdu.active,
                paediatric_diabetes_network_id_id=pdu.paediatric_diabetes_network_id,
            )
        )
    if rows:
        PaediatricDiabetesUnitVersion.objects.bulk_create(rows)


def backfill_paediatric_diabetes_network_versions(apps, schema_editor):
    PaediatricDiabetesNetwork = apps.get_model(
        "hospitals", "PaediatricDiabetesNetwork"
    )
    PaediatricDiabetesNetworkVersion = apps.get_model(
        "hospitals", "PaediatricDiabetesNetworkVersion"
    )
    valid_from = _baseline_valid_from()

    rows = []
    for network in PaediatricDiabetesNetwork.objects.all():
        rows.append(
            PaediatricDiabetesNetworkVersion(
                paediatric_diabetes_network=network,
                valid_from=valid_from,
                valid_to=None,
                name=network.name,
            )
        )
    if rows:
        PaediatricDiabetesNetworkVersion.objects.bulk_create(rows)


# Reverse operations: delete all baseline rows. This is only safe to run
# immediately after the forward migration; once real history has accumulated
# it should not be reversed. Django will refuse to reverse a data migration
# that has subsequent migrations depending on it, which provides a guard.


def remove_organisation_versions(apps, schema_editor):
    OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")
    OrganisationVersion.objects.filter(valid_to__isnull=True).delete()


def remove_trust_versions(apps, schema_editor):
    TrustVersion = apps.get_model("hospitals", "TrustVersion")
    TrustVersion.objects.filter(valid_to__isnull=True).delete()


def remove_local_health_board_versions(apps, schema_editor):
    LocalHealthBoardVersion = apps.get_model("hospitals", "LocalHealthBoardVersion")
    LocalHealthBoardVersion.objects.filter(valid_to__isnull=True).delete()


def remove_integrated_care_board_versions(apps, schema_editor):
    IntegratedCareBoardVersion = apps.get_model(
        "hospitals", "IntegratedCareBoardVersion"
    )
    IntegratedCareBoardVersion.objects.filter(valid_to__isnull=True).delete()


def remove_nhs_england_region_versions(apps, schema_editor):
    NHSEnglandRegionVersion = apps.get_model("hospitals", "NHSEnglandRegionVersion")
    NHSEnglandRegionVersion.objects.filter(valid_to__isnull=True).delete()


def remove_paediatric_diabetes_unit_versions(apps, schema_editor):
    PaediatricDiabetesUnitVersion = apps.get_model(
        "hospitals", "PaediatricDiabetesUnitVersion"
    )
    PaediatricDiabetesUnitVersion.objects.filter(valid_to__isnull=True).delete()


def remove_paediatric_diabetes_network_versions(apps, schema_editor):
    PaediatricDiabetesNetworkVersion = apps.get_model(
        "hospitals", "PaediatricDiabetesNetworkVersion"
    )
    PaediatricDiabetesNetworkVersion.objects.filter(valid_to__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0023_entity_version_models"),
    ]

    operations = [
        migrations.RunPython(
            backfill_organisation_versions,
            reverse_code=remove_organisation_versions,
        ),
        migrations.RunPython(
            backfill_trust_versions,
            reverse_code=remove_trust_versions,
        ),
        migrations.RunPython(
            backfill_local_health_board_versions,
            reverse_code=remove_local_health_board_versions,
        ),
        migrations.RunPython(
            backfill_integrated_care_board_versions,
            reverse_code=remove_integrated_care_board_versions,
        ),
        migrations.RunPython(
            backfill_nhs_england_region_versions,
            reverse_code=remove_nhs_england_region_versions,
        ),
        migrations.RunPython(
            backfill_paediatric_diabetes_unit_versions,
            reverse_code=remove_paediatric_diabetes_unit_versions,
        ),
        migrations.RunPython(
            backfill_paediatric_diabetes_network_versions,
            reverse_code=remove_paediatric_diabetes_network_versions,
        ),
    ]
