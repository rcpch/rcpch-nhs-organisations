# Auto-generated `LayerMapping` dictionary for LowerLayerSuperOutputArea model
# lowerlayersuperoutputarea_mapping = {
#     'lsoa11cd': 'LSOA11CD',
#     'lsoa11nm': 'LSOA11NM',
#     'lsoa11nmw': 'LSOA11NMW',
#     'bng_e': 'BNG_E',
#     'bng_n': 'BNG_N',
#     'long': 'LONG',
#     'lat': 'LAT',
#     'globalid': 'GlobalID',
#     'geom': 'MULTIPOLYGON',
# }

from django.contrib.gis.db import models
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass


class LowerLayerSuperOutputArea2011Boundaries(TimeStampAbstractBaseClass):
    lsoa11cd = models.CharField(max_length=9)
    lsoa11nm = models.CharField(max_length=50)
    lsoa11nmw = models.CharField(max_length=50, null=True, blank=True)
    bng_e = models.BigIntegerField()
    bng_n = models.BigIntegerField()
    long = models.FloatField()
    lat = models.FloatField()
    globalid = models.CharField(max_length=38)
    geom = models.MultiPolygonField(srid=27700)

    class Meta:
        abstract = True


class LowerLayerSuperOutputArea(LowerLayerSuperOutputArea2011Boundaries):

    publication_date = models.DateField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["lsoa11cd"])]
        verbose_name = "Local Authority District"
        verbose_name_plural = "Local Authority Districts"
        ordering = ("lsoa11nm",)

    def __str__(self) -> str:
        return self.lsoa11nm

    def get_publication_date(self) -> str:
        return self.publication_date


# When we come to map the 2021, we will need to create new fields for the lsoa21cd, lsoa21nm, lsoa21nmw and map those to the new fields in the 2021 shapefile. The LSOA model will need a conditional to return the correct name based on the publication date.
