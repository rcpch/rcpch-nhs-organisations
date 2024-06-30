"""
# Auto-generated `LayerMapping` dictionary for CountryBoundaries model
countryboundaries_mapping = {
    'code': 'CTRY22CD',
    'name': 'CTRY22NM',
    'welsh_name': 'CTRY22NMW',
    'bng_e': 'BNG_E',
    'bng_n': 'BNG_N',
    'long': 'LONG',
    'lat': 'LAT',
    'globalid': 'GlobalID',
    'geom': 'MULTIPOLYGON',
}
"""

from django.contrib.gis.db import models


class CountryBoundaries(models.Model):
    boundary_identifier = models.CharField(max_length=9)
    name = models.CharField(max_length=16)
    welsh_name = models.CharField(max_length=17, blank=True, null=True)
    bng_e = models.BigIntegerField(blank=True, null=True)
    bng_n = models.BigIntegerField(blank=True, null=True)
    long = models.FloatField()
    lat = models.FloatField()
    globalid = models.CharField(max_length=38, blank=True, null=True)
    geom = models.MultiPolygonField(srid=27700, blank=True, null=True)

    class Meta:
        abstract = True


class Country(CountryBoundaries):
    class Meta:
        indexes = [models.Index(fields=["boundary_identifier"])]
        verbose_name = "Country"
        verbose_name_plural = "Countries"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def get_country_code(self) -> str:
        return self.boundary_identifier
