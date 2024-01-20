from rest_framework import serializers

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from ..models import Country


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/country/1/",
            value={
                "boundary_identifier": "E92000001",
                "name": "England",
                "welsh_name": "Lloegr",
                "bng_e": "394883",
                "bng_n": "370883",
                "long": "-2.07811",
                "lat": "53.235",
                "globalid": "f6b76559-3626-49b8-b50b-bd15efcb0505",
                "geom": "",
            },
            response_only=True,
        )
    ]
)
class CountrySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Country
        fields = [
            "boundary_identifier",
            "name",
            "welsh_name",
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
            "/country/1/limited",
            value={
                "boundary_identifier": "E92000001",
                "name": "England",
            },
            response_only=True,
        )
    ]
)
class CountryLimitedSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Country
        fields = [
            "boundary_identifier",
            "name",
        ]
