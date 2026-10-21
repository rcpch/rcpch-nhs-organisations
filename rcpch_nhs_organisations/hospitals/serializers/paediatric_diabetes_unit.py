from rest_framework import serializers

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from ..models import PaediatricDiabetesUnit

from .paediatric_diabetes_network import PaediatricDiabetesNetworkSerializer
from .succession import SuccessionLinkSerializer

from django.apps import apps

PaediatricDiabetesUnitSuccession = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitSuccession"
)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/paediatric_diabetes_unit/1/",
            value={
                "pz_code": "",
                "paediatric_diabetes_network": {"pn_code": "", "name": ""},
                "predecessors": [],
                "successors": [],
            },
            response_only=True,
        )
    ]
)
class PaediatricDiabetesUnitSerializer(serializers.ModelSerializer):

    predecessors = serializers.SerializerMethodField()
    successors = serializers.SerializerMethodField()

    class Meta:
        model = PaediatricDiabetesUnit
        # depth = 1
        fields = [
            "pz_code",
            "updated_at",
            "active",
            "name",
            "predecessors",
            "successors",
        ]

    def get_predecessors(self, obj):
        links = obj.succession_successor_links.select_related(
            "predecessor"
        ).order_by("succession_date")
        return SuccessionLinkSerializer(
            links, many=True, code_field="pz_code", related_attr="predecessor"
        ).data

    def get_successors(self, obj):
        links = obj.succession_predecessor_links.filter(
            successor__isnull=False
        ).select_related("successor").order_by("succession_date")
        return SuccessionLinkSerializer(
            links, many=True, code_field="pz_code", related_attr="successor"
        ).data


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/paediatric_diabetes_units/",
            value={
                "pz_code": "",
                "paediatric_diabetes_network": {"pn_code": "", "name": ""},
            },
            response_only=True,
        )
    ]
)
class PaediatricDiabetesUnitWIthNestedPaediatricDiabetesNetworkSerializer(
    serializers.ModelSerializer
):
    paediatric_diabetes_network = serializers.SerializerMethodField()

    class Meta:
        model = PaediatricDiabetesUnit
        # depth = 1
        fields = ["pz_code", "paediatric_diabetes_network", "active", "updated_at", "name"]

    def get_paediatric_diabetes_network(self, obj):
        network = obj.paediatric_diabetes_network
        if network:
            return PaediatricDiabetesNetworkSerializer(network).data
        return None
