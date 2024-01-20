"""
Auto-generated `LayerMapping` dictionary for NHSEnglandRegionBoundaries model
nhsenglandregionboundaries_mapping = {
    "boundary_identifier": "NHSER22CD",
    "name": "NHSER22NM",
    "bng_e": "BNG_E",
    "bng_n": "BNG_N",
    "long": "LONG",
    "lat": "LAT",
    "globalid": "GlobalID",
    "geom": "MULTIPOLYGON",
}
"""
from django.contrib.gis.db import models
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass


class NHSEnglandRegionBoundaries(TimeStampAbstractBaseClass):
    boundary_identifier = models.CharField(max_length=9)
    name = models.CharField(max_length=24)
    bng_e = models.BigIntegerField()
    bng_n = models.BigIntegerField()
    long = models.FloatField()
    lat = models.FloatField()
    globalid = models.CharField(max_length=38)
    geom = models.MultiPolygonField(srid=27700)

    class Meta:
        abstract = True


class NHSEnglandRegion(NHSEnglandRegionBoundaries):
    region_code = models.CharField(unique=True, blank=True, null=True)
    publication_date = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = "NHS England Region"
        verbose_name_plural = "NHS England Regions"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def get_publication_date(self) -> str:
        return self.publication_date

    def get_region_code(self) -> str:
        return self.region_code
