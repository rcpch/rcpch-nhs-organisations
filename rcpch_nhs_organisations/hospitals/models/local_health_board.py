"""
# Auto-generated `LayerMapping` dictionary for LocalHealthBoardBoundaries model
localhealthboardboundaries_mapping = {
    'boundary_identifier': 'LHB22CD',
    'name': 'LHB22NM',
    'welsh_name': 'LHB22NMW',
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


class LocalHealthBoardBoundaries(TimeStampAbstractBaseClass):
    boundary_identifier = models.CharField(max_length=9)
    # ODS names (e.g. "CWM TAF MORGANNWG UNIVERSITY LOCAL HEALTH BOARD", 47
    # chars) are longer than the Welsh boundary shapefile column (LHB22NM)
    # this model was originally sized against, so use the same generous width
    # as Trust (the English equivalent of a Local Health Board).
    name = models.CharField(max_length=100)
    welsh_name = models.CharField(max_length=40)
    bng_e = models.FloatField()
    bng_n = models.FloatField()
    long = models.FloatField()
    lat = models.FloatField()
    globalid = models.CharField(max_length=38)
    geom = models.MultiPolygonField(srid=27700)

    class Meta:
        abstract = True


class LocalHealthBoard(LocalHealthBoardBoundaries):
    ods_code = models.CharField(max_length=3)
    publication_date = models.DateField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["ods_code"])]
        verbose_name = "Local Health Board"
        verbose_name_plural = "Local Health Boards"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def get_ods_code(self) -> str:
        return self.ods_code

    def get_publication_date(self) -> str:
        return self.publication_date
