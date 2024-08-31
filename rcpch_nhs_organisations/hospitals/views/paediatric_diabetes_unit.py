from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
)
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiResponse,
)

# from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes


from ..models import PaediatricDiabetesUnit, Organisation
from ..serializers import (
    PaediatricDiabetesUnitSerializer,
    PaediatricDiabetesUnitWithNestedOrganisationSerializer,
    PaediatricDiabetesUnitWithNestedOrganisationAndParentSerializer,
    PaediatricDiabetesUnitWithNestedParentSerializer,
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
    pagination_class = None


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
    pagination_class = None


@extend_schema(
    request=PaediatricDiabetesUnitWithNestedOrganisationAndParentSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "paediatric_diabetes_units/sibling-organisations/RGT01/",
                    external_value="external value",
                    value={
                        "ods_code": "RGT01",
                    },
                    response_only="true",
                ),
            ],
        ),
    },
    parameters=[
        OpenApiParameter(
            name="ods_code",
            description="ODS Code of the Organisation",
            required=True,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
        ),
    ],
    summary="This endpoint returns a list of sibling NHS Organisations (Acute or Community Hospitals) within a Paediatric Diabetes Unit (with their parent), against an ODS code.",
)
class PaediatricDiabetesUnitForOrganisationWithParentViewSet(viewsets.ViewSet):

    def list(self, request, ods_code=None):
        queryset = PaediatricDiabetesUnit.objects.filter(
            paediatric_diabetes_unit_organisations__ods_code=ods_code
        )
        serializer = PaediatricDiabetesUnitWithNestedOrganisationAndParentSerializer(
            queryset, many=True
        )
        return Response(serializer.data)


@extend_schema(
    request=PaediatricDiabetesUnitWithNestedParentSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "paediatric_diabetes_units/trust/RGT/",
                    external_value="external value",
                    value={
                        "pz_code": "PZ215",
                    },
                    response_only="true",
                ),
            ],
        ),
    },
    parameters=[
        OpenApiParameter(
            name="pz_code",
            description="PZ Code of the Paediatric Diabetes Unit",
            required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
    ],
    summary="This endpoint returns the parent NHS Trust or Local Health Board for a given Paediatric Diabetes Unit (with their primary organisation and Paediatric Diabetes Network), against a PZ code. If no code is provide, a list is returned.",
)
class PaediatricDiabetesUnitForParentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PaediatricDiabetesUnit.objects.all()
    serializer_class = PaediatricDiabetesUnitWithNestedParentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        pz_code = self.request.query_params.get("pz_code", None)
        if pz_code is not None:
            queryset = queryset.filter(pz_code=pz_code)
        return queryset
