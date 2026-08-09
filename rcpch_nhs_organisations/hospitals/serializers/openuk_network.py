from django.apps import apps
from rest_framework import serializers

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample


from ..models import OPENUKNetwork


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/openuk_networks/E38000001/",
            value={
                "name": "North Thames Paediatric Epilepsy Network",
                "boundary_identifier": "E38000001",
                "country": "England",
                "publication_date": "2023-04-01",
            },
            response_only=True,
        )
    ]
)
class OPENUKNetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = OPENUKNetwork
        # depth = 1
        fields = [
            "name",
            "boundary_identifier",
            "country",
            "publication_date",
        ]
