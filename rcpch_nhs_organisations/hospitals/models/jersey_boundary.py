# This is an auto-generated Django model module created by ogrinspect.
from django.contrib.gis.db import models


class JerseyBoundaries(models.Model):
    objectid = models.IntegerField()
    id = models.CharField(max_length=18)
    area_ha = models.FloatField()
    remark = models.CharField(max_length=20)
    code_06 = models.CharField(max_length=3)
    shape_leng = models.FloatField()
    shape_area = models.FloatField()
    geom = models.MultiPolygonField(srid=4326)


# Auto-generated `LayerMapping` dictionary for JerseyBoundaries model
jerseyboundaries_mapping = {
    "objectid": "OBJECTID",
    "id": "ID",
    "area_ha": "Area_Ha",
    "remark": "Remark",
    "code_06": "CODE_06",
    "shape_leng": "Shape_Leng",
    "shape_area": "Shape_Area",
    "geom": "MULTIPOLYGON",
}
