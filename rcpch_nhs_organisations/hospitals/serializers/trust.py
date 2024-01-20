from rest_framework import serializers

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from ..models import Trust


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/trust/1/",
            value={
                "ods_code": "",
                "name": "",
                "address_line_1": "",
                "address_line_2": "",
                "town": "",
                "postcode": "",
                "country": "",
                "telephone": "",
                "website": "",
                "active": "",
                "published_at": "",
            },
            response_only=True,
        )
    ]
)
class TrustSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trust
        # depth = 1
        fields = [
            "ods_code",
            "name",
            "address_line_1",
            "address_line_2",
            "town",
            "postcode",
            "country",
            "telephone",
            "website",
            "active",
            "published_at",
        ]
