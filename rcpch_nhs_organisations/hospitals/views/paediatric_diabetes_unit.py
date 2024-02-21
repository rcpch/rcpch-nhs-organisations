from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
)
from rest_framework.decorators import api_view
from rest_framework.views import APIView, Response
from rest_framework.exceptions import ParseError
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
    PolymorphicProxySerializer,
)
from drf_spectacular.types import OpenApiTypes

from ..models import PaediatricDiabetesUnit
from ..serializers import (
    PaediatricDiabetesUnitSerializer,
    PaediatricDiabetesUnitWithNestedOrganisationSerializer,
)


@extend_schema(
    request=PaediatricDiabetesUnitSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/paediatric_diabetes_units/1/",
                    external_value="external value",
                    value={
                        "pz_code": "E54000054",
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of Paediatric Diabetes Units from England and Wales, or an individual PDU by PZ code.",
)
class PaediatricDiabetesUnitViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of Paediatric Diabetes Units from England and Wales, or an individual PDU by PZ code.

    Filter Parameters:

    `pz_code`

    If none are passed, a list is returned.

    """

    queryset = PaediatricDiabetesUnit.objects.all().order_by("pz_code")
    serializer_class = PaediatricDiabetesUnitSerializer
    lookup_field = "pz_code"
    filterset_fields = [
        "pz_code",
    ]
    filter_backends = (DjangoFilterBackend,)


@extend_schema(
    request=PaediatricDiabetesUnitWithNestedOrganisationSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/paediatric_diabetes_units/1/organisations",
                    external_value="external value",
                    value={
                        "pz_code": "PZ002",
                        "organisations": [{"name": "Name", "ods_code": ""}],
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of Paediatric Diabetes Units from England and Wales, or an individual PDU by PZ code, with nested parent organisations.",
)
class PaediatricDiabetesUnitWithNestedOrganisationsViewSet(
    viewsets.ReadOnlyModelViewSet
):
    """
    This endpoint returns a list of Paediatric Diabetes Units from England and Wales, or an individual PDU by PZ code, with nested parent organisations.

    Filter Parameters:

    `pz_code`

    If none are passed, a list is returned.

    """

    queryset = PaediatricDiabetesUnit.objects.all().order_by("pz_code")
    serializer_class = PaediatricDiabetesUnitWithNestedOrganisationSerializer
    lookup_field = "pz_code"
    filterset_fields = [
        "pz_code",
    ]
    filter_backends = (DjangoFilterBackend,)
