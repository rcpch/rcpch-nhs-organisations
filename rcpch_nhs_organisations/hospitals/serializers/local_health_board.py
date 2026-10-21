from django.apps import apps
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample


from ..models import LocalHealthBoard


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/local_health_board/1/",
            value={
                "ods_code": "",
                "publication_date": "",
                "boundary_identifier": "",
                "name": "",
                "welsh_name": "",
                "bng_e": "",
                "bng_n": "",
                "long": "",
                "lat": "",
                "predecessors": [],
                "successors": [],
            },
            response_only=True,
        )
    ]
)
class LocalHealthBoardSerializer(serializers.ModelSerializer):
    # returns local health boards and boundary data
    #
    # LocalHealthBoard has no succession table (Welsh LHB reorganisations are
    # not modelled in Layer 3), so predecessors / successors are always empty.
    # The fields are included for API consistency with the other entity detail
    # endpoints.
    predecessors = serializers.SerializerMethodField()
    successors = serializers.SerializerMethodField()

    class Meta:
        model = LocalHealthBoard
        fields = [
            "ods_code",
            "publication_date",
            "boundary_identifier",
            "name",
            "welsh_name",
            "bng_e",
            "bng_n",
            "long",
            "lat",
            "predecessors",
            "successors",
        ]

    def get_predecessors(self, obj):
        return []

    def get_successors(self, obj):
        return []


class LocalHealthBoardGeoJSONSerializer(GeoFeatureModelSerializer):
    # returns local health boards with only ods_code and boundary data
    class Meta:
        model = LocalHealthBoard
        geo_field = "geom"
        fields = [
            "ods_code",
            "name",
            "welsh_name",
            "bng_e",
            "bng_n",
            "long",
            "lat",
            "boundary_identifier",
            "geom",
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/local_health_board/1/limited",
            value={
                "ods_code": "",
                "boundary_identifier": "",
                "name": "",
            },
            response_only=True,
        )
    ]
)
class LocalHealthBoardLimitedSerializer(serializers.ModelSerializer):
    # returns local health boards with only ods_code and name
    class Meta:
        model = LocalHealthBoard
        # depth = 1
        fields = [
            "ods_code",
            "boundary_identifier",
            "name",
        ]
