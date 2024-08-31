from rest_framework import serializers

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from ..models import PaediatricDiabetesUnit

from .paediatric_diabetes_network import PaediatricDiabetesNetworkSerializer


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/paediatric_diabetes_unit/1/",
            value={
                "pz_code": "",
                "paediatric_diabetes_network": {"pn_code": "", "name": ""},
            },
            response_only=True,
        )
    ]
)
class PaediatricDiabetesUnitSerializer(serializers.ModelSerializer):

    class Meta:
        model = PaediatricDiabetesUnit
        # depth = 1
        fields = [
            "pz_code",
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/paediatric_diabetes_unit/1/",
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
        fields = [
            "pz_code",
            "paediatric_diabetes_network",
        ]

    def get_paediatric_diabetes_network(self, obj):
        network = obj.paediatric_diabetes_network
        if network:
            return PaediatricDiabetesNetworkSerializer(network).data
        return None
