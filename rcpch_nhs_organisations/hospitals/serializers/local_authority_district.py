from django.apps import apps
from rest_framework import serializers

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from ..models import LocalAuthorityDistrict


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/local_authority_district/2024/1/extended",
            value={
                "lad24cd": "",
                "lad24nm": "",
                "lad24nmw": "",
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
class LocalAuthorityDistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocalAuthorityDistrict
        # depth = 1
        fields = [
            "lad24cd",
            "lad24nm",
            "lad24nmw",
            "bng_e",
            "bng_n",
            "long",
            "lat",
            "globalid",
            "geom",
        ]
