from django.apps import apps
from rest_framework import serializers

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from ..models import NHSEnglandRegion


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/nhs_england_regions/1/",
            value={
                "region_code": "",
                "publication_date": "",
                "boundary_identifier": "E54000030",
                "name": "NHS England Region",
                "bng_e": "541305",
                "bng_n": "168583",
                "long": "0.029892",
                "lat": "51.3987",
                "globalid": "39c8c149-5e5f-4bfa-87ae-9b5daf7f9e08",
                "geom": "",
                "ods_code": "QKK",
                "publication_date": "15/03/2023",
            },
            response_only=True,
        )
    ]
)
class NHSEnglandRegionSerializer(serializers.ModelSerializer):
    # returns NHS England regions and boundaries
    class Meta:
        model = NHSEnglandRegion
        # depth = 1
        fields = [
            "region_code",
            "publication_date",
            "boundary_identifier",
            "name",
            "bng_e",
            "bng_n",
            "long",
            "lat",
            "globalid",
            "geom",
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/nhs_england_regions/1/limited",
            value={
                "region_code": "",
                "publication_date": "",
                "boundary_identifier": "E54000030",
                "name": "NHS England Region",
                "publication_date": "15/03/2023",
            },
            response_only=True,
        )
    ]
)
class NHSEnglandRegionLimitedSerializer(serializers.ModelSerializer):
    # returns NHS England Regions without boundary data
    class Meta:
        model = NHSEnglandRegion
        # depth = 1
        fields = [
            "region_code",
            "publication_date",
            "boundary_identifier",
            "name",
        ]
