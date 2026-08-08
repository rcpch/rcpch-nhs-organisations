"""
# Auto-generated `LayerMapping` dictionary for IntegratedCareBoardBoundaries model
integratedcareboardboundaries_mapping = {
    'icb23cd': 'ICB23CD',
    'name': 'ICB23NM',
    'bng_e': 'BNG_E',
    'bng_n': 'BNG_N',
    'long': 'LONG',
    'lat': 'LAT',
    'globalid': 'GlobalID',
    'geom': 'MULTIPOLYGON',
}
"""
from django.contrib.gis.db import models


class IntegratedCareBoardBoundaries(models.Model):
    boundary_identifier = models.CharField(max_length=9)
    name = models.CharField(max_length=77)
    bng_e = models.BigIntegerField(null=True, blank=True, default=None)
    bng_n = models.BigIntegerField(null=True, blank=True, default=None)
    long = models.FloatField(null=True, blank=True, default=None)
    lat = models.FloatField(null=True, blank=True, default=None)
    globalid = models.CharField(max_length=38, null=True, blank=True, default=None)
    geom = models.MultiPolygonField(srid=27700, null=True, blank=True, default=None)

    class Meta:
        abstract = True


class IntegratedCareBoard(IntegratedCareBoardBoundaries):
    ods_code = models.CharField()
    publication_date = models.DateField(blank=True, null=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Integrated Care Board"
        verbose_name_plural = "Integrated Care Boards"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def get_ods_code(self) -> str:
        return self.ods_code

    def get_publication_date(self) -> str:
        return self.publication_date
