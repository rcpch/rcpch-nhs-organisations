from rest_framework import serializers

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from ..models import GeneralPractice


class GeneralPracticeSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = GeneralPractice
        fields = [
            "ods_code",
            "name",
            "website",
            "address1",
            "address2",
            "address3",
            "telephone",
            "city",
            "county",
            "latitude",
            "longitude",
            "postcode",
            "geocode_coordinates",
            "active",
            "published_at",
        ]
