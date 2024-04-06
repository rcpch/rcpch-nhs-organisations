from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
)
from rest_framework.decorators import api_view
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes

from ..models import Trust
from ..serializers import (
    TrustWithNestedOrganisationsSerializer,
)


@extend_schema(
    request=TrustWithNestedOrganisationsSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/trust/1/",
                    external_value="external value",
                    value={
                        "ods_code": "RCF",
                        "name": "AIREDALE NHS FOUNDATION TRUST",
                        "address_line_1": "AIREDALE GENERAL HOSPITAL",
                        "address_line_2": "SKIPTON ROAD",
                        "town": "KEIGHLEY",
                        "postcode": "BD20 6TD",
                        "country": "ENGLAND",
                        "telephone": "null",
                        "website": "null",
                        "active": "true",
                        "published_at": "null",
                        "trust_organisations": [
                            {"ods_code": "RCF22", "name": "AIREDALE GENERAL HOSPITAL"}
                        ],
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of NHS Trusts from England, or an individual Trust by ODS code, with all child organisations nested.",
)
class TrustViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of NHS Trusts from England, or an individual Trust by ODS code, with all child organisations nested.

    Filter Parameters:

    `ods_code`
    `name`
    `address_line_1`
    `address_line_2`
    `town`
    `postcode`
    `country`
    `telephone`
    `website`
    `active`
    `published_at`

    If none are passed, a list is returned.

    """

    queryset = Trust.objects.all().order_by("name")
    serializer_class = TrustWithNestedOrganisationsSerializer
    lookup_field = "ods_code"
    filterset_fields = [
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
        "ods_code",
    ]
    filter_backends = (DjangoFilterBackend,)
    pagination_class = None
