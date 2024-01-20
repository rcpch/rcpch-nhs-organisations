from django.apps import apps
from rest_framework import serializers

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample


from ..models import OPENUKNetwork


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/openUK_network/1/",
            value={
                "name": "",
                "boundary_identifier": "",
                "country": "",
                "publication_date": "",
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
