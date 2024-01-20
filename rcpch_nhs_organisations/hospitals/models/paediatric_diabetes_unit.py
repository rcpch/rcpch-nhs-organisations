# python imports

# django imports
from django.contrib.gis.db import models
from django.db.models import CharField


class PaediatricDiabetesUnit(models.Model):
    pz_code = CharField("Paediatric Diabetes Unit PZ Number", max_length=5)

    class Meta:
        verbose_name = "Paediatric Diabetes Unit"
        verbose_name_plural = "Paediatric Diabetes Units"
        ordering = ("pz_code",)

    def __str__(self) -> str:
        return f"{self.pz_code}"
