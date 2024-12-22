# Python imports

# Django imports
from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
)
from rest_framework.decorators import action

# Third-party imports
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes

# RCPCH NHS Organisations imports
from ..models import Trust
from ..serializers import (
    TrustSerializer,
    TrustWithNestedOrganisationsSerializer,
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
    serializer_class = TrustSerializer
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

    def get_serializer_class(self):
        if self.action in ["list_trust_organisations", "retrieve_trust_organisations"]:
            return TrustWithNestedOrganisationsSerializer
        return super().get_serializer_class()

    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Valid Response",
                examples=[
                    OpenApiExample(
                        "/trust/RBS/",
                        external_value="external value",
                        value={
                            "ods_code": "RBS",
                            "name": "ALDER HEY CHILDREN'S NHS FOUNDATION TRUST",
                            "address_line_1": "ALDER HEY HOSPITAL",
                            "address_line_2": "EATON ROAD",
                            "town": "LIVERPOOL",
                            "postcode": "L12 2AP",
                            "country": "ENGLAND",
                            "telephone": "",
                            "website": "",
                            "active": True,
                            "published_at": "",
                        },
                        response_only=True,
                    ),
                ],
            ),
        },
        summary="This endpoint returns an NHS Trust from England.",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Valid Response",
                examples=[
                    OpenApiExample(
                        "/trust/1/",
                        external_value="external value",
                        value=[
                            {
                                "ods_code": "RCF",
                                "name": "AIREDALE NHS FOUNDATION TRUST",
                                "address_line_1": "AIREDALE GENERAL HOSPITAL",
                                "address_line_2": "SKIPTON ROAD",
                                "town": "KEIGHLEY",
                                "postcode": "BD20 6TD",
                                "country": "ENGLAND",
                                "telephone": "",
                                "website": "",
                                "active": True,
                                "published_at": "",
                            },
                            {
                                "ods_code": "RBS",
                                "name": "ALDER HEY CHILDREN'S NHS FOUNDATION TRUST",
                                "address_line_1": "ALDER HEY HOSPITAL",
                                "address_line_2": "EATON ROAD",
                                "town": "LIVERPOOL",
                                "postcode": "L12 2AP",
                                "country": "ENGLAND",
                                "telephone": "",
                                "website": "",
                                "active": True,
                                "published_at": "",
                            },
                        ],
                        response_only=True,
                    ),
                ],
            ),
        },
        summary="This endpoint returns a list of NHS Trusts from England.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns a list of NHS Trusts from England and Local Health Boards in Wales, with all child organisations nested.",
        operation_id="list_trust_organisations",
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="organisations",
        url_name="organisations",
    )
    def list_trust_organisations(self, request):
        return super().list(request)

    @extend_schema(
        summary="This endpoint returns an individual NHS Trust from England with all child organisations nested.",
        operation_id="retrieve_trust_organisations",
    )
    @action(
        detail=True, methods=["get"], url_path="organisations", url_name="organisations"
    )
    def retrieve_trust_organisations(self, request):
        return super().retrieve(request)
