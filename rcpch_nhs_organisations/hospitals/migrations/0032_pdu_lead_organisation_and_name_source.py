# Generated for: add lead_organisation FK and name_source to
# PaediatricDiabetesUnit and PaediatricDiabetesUnitVersion, replacing the
# hardcoded PZ-code lists in PaediatricDiabetesUnit.primary_organisation and
# .name. The lead organisation is modelled as a denormalised FK on the PDU
# (current state) with a snapshot on the version table (temporal history),
# matching the pattern used for paediatric_diabetes_network. See
# documentation/docs/developer/merger-handling.md.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0031_ods_divergent_organisations"),
    ]

    operations = [
        migrations.AddField(
            model_name="paediatricdiabetesunit",
            name="name_source",
            field=models.CharField(
                max_length=30,
                choices=[
                    ("lead_organisation", "Lead organisation"),
                    ("trust", "Parent trust"),
                    ("local_health_board", "Parent local health board"),
                ],
                default="lead_organisation",
                verbose_name="Name source",
                help_text=(
                    "How the PDU's display name is derived when unit_name is "
                    "not set. 'Lead organisation' (default) uses the lead "
                    "organisation's name; 'Parent trust' uses the lead "
                    "organisation's parent trust name (for multi-site PDUs "
                    "that identify by trust); 'Parent local health board' "
                    "uses the LHB name (for Welsh PDUs)."
                ),
            ),
        ),
        migrations.AddField(
            model_name="paediatricdiabetesunit",
            name="lead_organisation",
            field=models.ForeignKey(
                to="hospitals.organisation",
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                default=None,
                related_name="lead_pdu_set",
                verbose_name="Lead organisation",
                help_text=(
                    "The lead/primary organisation for this PDU. Exposed via "
                    "the /paediatric_diabetes_units/{pz_code}/parent/ "
                    "endpoint as primary_organisation."
                ),
            ),
        ),
        migrations.AddField(
            model_name="paediatricdiabetesunitversion",
            name="name_source",
            field=models.CharField(
                max_length=30,
                choices=[
                    ("lead_organisation", "Lead organisation"),
                    ("trust", "Parent trust"),
                    ("local_health_board", "Parent local health board"),
                ],
                default="lead_organisation",
                verbose_name="Name source (snapshot)",
                help_text=(
                    "How the PDU's display name was derived at valid_from. "
                    "See PaediatricDiabetesUnit.name_source."
                ),
            ),
        ),
        migrations.AddField(
            model_name="paediatricdiabetesunitversion",
            name="lead_organisation",
            field=models.ForeignKey(
                to="hospitals.organisation",
                on_delete=models.SET_NULL,
                related_name="pdu_versions_as_lead",
                null=True,
                blank=True,
                default=None,
                verbose_name="Lead organisation (snapshot)",
                help_text=(
                    "The lead organisation for this PDU at valid_from. See "
                    "PaediatricDiabetesUnit.lead_organisation."
                ),
            ),
        ),
    ]