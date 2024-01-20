from django.apps import apps
from rest_framework import serializers

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from ..models import LondonBorough


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/london_borough/1/extended",
            value={
                "name": "",
                "gss_code": "",
                "hectares": "",
                "nonld_area": "",
                "ons_inner": "",
                "sub_2009": "",
                "sub_2006": "",
                "geom": "",
            },
            response_only=True,
        )
    ]
)
class LondonBoroughSerializer(serializers.ModelSerializer):
    class Meta:
        model = LondonBorough
        # depth = 1
        fields = [
            "name",
            "gss_code",
            "hectares",
            "nonld_area",
            "ons_inner",
            "sub_2009",
            "sub_2006",
            "geom",
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/london_borough/1/limited",
            value={
                "name": "",
                "gss_code": "",
            },
            response_only=True,
        )
    ]
)
class LondonBoroughLimitedSerializer(serializers.ModelSerializer):
    class Meta:
        model = LondonBorough
        fields = [
            "name",
            "gss_code",
        ]
