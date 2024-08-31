# Generated by Django 4.2.11 on 2024-08-31 18:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("hospitals", "0005_alter_country_bng_e_alter_country_bng_n_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaediatricDiabetesNetwork",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "pn_code",
                    models.CharField(
                        max_length=5,
                        unique=True,
                        verbose_name="Paediatric Diabetes Network PN Number",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=255, verbose_name="Paediatric Diabetes Network Name"
                    ),
                ),
            ],
            options={
                "verbose_name": "Paediatric Diabetes Network",
                "verbose_name_plural": "Paediatric Diabetes Networks",
                "ordering": ("pn_code",),
            },
        ),
        migrations.AddField(
            model_name="paediatricdiabetesunit",
            name="paediatric_diabetes_network",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="paediatric_diabetes_units",
                to="hospitals.paediatricdiabetesnetwork",
                verbose_name="Paediatric Diabetes Network",
            ),
        ),
    ]
