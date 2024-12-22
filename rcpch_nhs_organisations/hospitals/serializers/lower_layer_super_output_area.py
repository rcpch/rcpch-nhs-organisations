# Django imports
from django.apps import apps
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

# Third party imports
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

# RCCPCH NHS Organisations imports
from ..models import LowerLayerSuperOutputArea


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/lower_layer_super_output_area/2011/1/extended",
            value={
                "lsoa11cd": "",
                "lsoa11nm": "",
                "lsoa11nmw": "",
                "bng_e": "",
                "bng_n": "",
                "long": "",
                "lat": "",
                "globalid": "",
                "geom": "",
            },
            response_only=True,
        )
    ]
)
class LowerLayerSuperOutputAreaGeoJSONSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = LowerLayerSuperOutputArea
        # depth = 1
        fields = [
            "lsoa11cd",
            "lsoa11nm",
            "lsoa11nmw",
            "bng_e",
            "bng_n",
            "long",
            "lat",
            "globalid",
            "geom",
        ]


class LowerLayerSuperOutputAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = LowerLayerSuperOutputArea
        # depth = 1
        fields = [
            "lsoa11cd",
            "lsoa11nm",
            "lsoa11nmw",
            "bng_e",
            "bng_n",
            "long",
            "lat",
        ]
