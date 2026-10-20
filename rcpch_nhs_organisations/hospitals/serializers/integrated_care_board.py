from django.apps import apps
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from ..models import IntegratedCareBoard
from .succession import SuccessionLinkSerializer

IntegratedCareBoardSuccession = apps.get_model(
    "hospitals", "IntegratedCareBoardSuccession"
)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/integrated_care_board/1/geojson/",
            value={
                "boundary_identifier": "E54000030",
                "name": "NHS South East London Integrated Care Board",
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
class IntegratedCareBoardGeoJSONSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = IntegratedCareBoard
        geo_field = "geom"
        fields = [
            "boundary_identifier",
            "name",
            "bng_e",
            "bng_n",
            "long",
            "lat",
            "globalid",
            "geom",
            "ods_code",
            "publication_date",
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/integrated_care_board/1/",
            value={
                "boundary_identifier": "E54000030",
                "name": "NHS South East London Integrated Care Board",
                "bng_e": "541305",
                "bng_n": "168583",
                "long": "0.029892",
                "lat": "51.3987",
                "ods_code": "QKK",
                "publication_date": "15/03/2023",
                "predecessors": [],
                "successors": [],
            },
            response_only=True,
        )
    ]
)
class IntegratedCareBoardSerializer(serializers.ModelSerializer):
    predecessors = serializers.SerializerMethodField()
    successors = serializers.SerializerMethodField()

    class Meta:
        model = IntegratedCareBoard
        fields = [
            "boundary_identifier",
            "name",
            "bng_e",
            "bng_n",
            "long",
            "lat",
            "ods_code",
            "publication_date",
            "predecessors",
            "successors",
        ]

    def get_predecessors(self, obj):
        links = obj.succession_successor_links.select_related(
            "predecessor"
        ).order_by("succession_date")
        return SuccessionLinkSerializer(
            links, many=True, code_field="ods_code", related_attr="predecessor"
        ).data

    def get_successors(self, obj):
        links = obj.succession_predecessor_links.filter(
            successor__isnull=False
        ).select_related("successor").order_by("succession_date")
        return SuccessionLinkSerializer(
            links, many=True, code_field="ods_code", related_attr="successor"
        ).data


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/integrated_care_board/1/limited",
            value={
                "boundary_identifier": "E54000030",
                "name": "NHS South East London Integrated Care Board",
                "ods_code": "QKK",
            },
            response_only=True,
        )
    ]
)
class IntegratedCareBoardLimitedSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegratedCareBoard
        # depth = 1
        fields = [
            "boundary_identifier",
            "name",
            "ods_code",
        ]
