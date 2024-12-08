from django.apps import apps
from rest_framework import serializers

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

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
            "globalid",
            "geom",
        ]
