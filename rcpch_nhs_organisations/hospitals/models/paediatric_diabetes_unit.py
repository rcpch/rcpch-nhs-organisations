# python imports

# django imports
from django.contrib.gis.db import models
from django.db.models import CharField

from .paediatric_diabetes_network import PaediatricDiabetesNetwork


class PaediatricDiabetesUnit(models.Model):
    pz_code = CharField("Paediatric Diabetes Unit PZ Number", max_length=5, unique=True)

    class Meta:
        verbose_name = "Paediatric Diabetes Unit"
        verbose_name_plural = "Paediatric Diabetes Units"
        ordering = ("pz_code",)

    def __str__(self) -> str:
        return f"{self.pz_code}"

    paediatric_diabetes_network = models.ForeignKey(  # it is possible for a PaediatricDiabetesUnit to not be associated with a PaediatricDiabetesNetwork (eg RCPCH has a PZ code but no PN code)
        to=PaediatricDiabetesNetwork,
        on_delete=models.CASCADE,
        verbose_name="Paediatric Diabetes Network",
        related_name="paediatric_diabetes_units",
        blank=True,
        null=True,
    )
