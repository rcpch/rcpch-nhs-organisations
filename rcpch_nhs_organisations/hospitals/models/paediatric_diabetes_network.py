# python imports

# django imports
from django.contrib.gis.db import models
from django.db.models import CharField


class PaediatricDiabetesNetwork(models.Model):
    pn_code = CharField(
        "Paediatric Diabetes Network PN Number", max_length=5, unique=True
    )

    name = CharField("Paediatric Diabetes Network Name", max_length=255)

    class Meta:
        verbose_name = "Paediatric Diabetes Network"
        verbose_name_plural = "Paediatric Diabetes Networks"
        ordering = ("pn_code",)

    def __str__(self) -> str:
        return f"{self.pn_code} - {self.name}"
