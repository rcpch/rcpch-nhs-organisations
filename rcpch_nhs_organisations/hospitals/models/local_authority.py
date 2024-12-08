"""
# Auto-generated `LayerMapping` dictionary for LocalAuthorityDistrict model
localauthoritydistrict_mapping = {
    'lad24cd': 'LAD24CD',
    'lad24nm': 'LAD24NM',
    'lad24nmw': 'LAD24NMW',
    'bng_e': 'BNG_E',
    'bng_n': 'BNG_N',
    'long': 'LONG',
    'lat': 'LAT',
    'globalid': 'GlobalID',
    'geom': 'MULTIPOLYGON',
}
"""

from django.contrib.gis.db import models
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass


class LocalAuthorityDistrictBoundaries(TimeStampAbstractBaseClass):
    lad24cd = models.CharField(max_length=9)
    lad24nm = models.CharField(max_length=36)
    lad24nmw = models.CharField(max_length=24, null=True, blank=True)
    bng_e = models.BigIntegerField()
    bng_n = models.BigIntegerField()
    long = models.FloatField()
    lat = models.FloatField()
    globalid = models.CharField(max_length=38)
    geom = models.MultiPolygonField(srid=27700)

    class Meta:
        abstract = True


class LocalAuthorityDistrict(LocalAuthorityDistrictBoundaries):

    publication_date = models.DateField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["lad24cd"])]
        verbose_name = "Local Authority District"
        verbose_name_plural = "Local Authority Districts"
        ordering = ("lad24nm",)

    def __str__(self) -> str:
        return self.lad24nm

    def get_publication_date(self) -> str:
        return self.publication_date
