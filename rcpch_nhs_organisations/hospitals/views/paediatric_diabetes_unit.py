from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
)
from rest_framework.response import Response
from rest_framework.decorators import action
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
    OrganisationWithLSOAAndLADSerializer,
)


@extend_schema(
    tags=["Child Health Geographies"],
    request=PaediatricDiabetesUnitSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/paediatric_diabetes_units/PZ215/parent/",
                    external_value="external value",
                    value={
                        "pz_code": "PZ215",
                        "paediatric_diabetes_network": "PN05",
                        "parent": {
                            "ods_code": "RJZ",
                            "name": "KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST",
                            "address_line_1": "DENMARK HILL",
                            "address_line_2": "",
                            "town": "LONDON",
                            "postcode": "SE5 9RS",
                            "country": "ENGLAND",
                            "telephone": None,
                            "website": None,
                            "active": True,
                            "published_at": None,
                        },
                        "primary_organisation": {
                            "ods_code": "RJZ01",
                            "name": "KING'S COLLEGE HOSPITAL (DENMARK HILL)",
                        },
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of Paediatric Diabetes Units from England and Wales, or an individual PDU by PZ code, with each organisation's associated lower layer super output area and local authority district.",
)
class PaediatricDiabetesUnitViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of Paediatric Diabetes Units from England and Wales, or an individual PDU by PZ code, with each organisation's associated lower layer super output area and local authority district.

    Filter Parameters:

    `pz_code`

    If none are passed, a list is returned.

    """

    queryset = PaediatricDiabetesUnit.objects.order_by("pz_code")
    serializer_class = PaediatricDiabetesUnitWithNestedOrganisationSerializer
    lookup_field = "pz_code"
    filterset_fields = [
        "pz_code",
    ]
    filter_backends = (DjangoFilterBackend,)
    pagination_class = None

    def get_serializer_class(self):
        if self.action in ["list_parents", "retrieve_parent"]:
            return PaediatricDiabetesUnitWithNestedParentSerializer
        return super().get_serializer_class()

    @extend_schema(
        description="This endpoint returns a list of Paediatric Diabetes Units from England and Wales with each organisation's associated lower layer super output area and local authority district.",
    )
    def list(self, request, *args, **kwargs):
        """
        This endpoint returns a list of Paediatric Diabetes Units from England and Wales with each organisation's associated lower layer super output area and local authority district.
        """
        return super().list(request, *args, **kwargs)

    @extend_schema(
        description="This endpoint returns an individual PDU by PZ code, with each organisation's associated lower layer super output area and local authority district.",
    )
    def retrieve(self, request, *args, **kwargs):
        """
        This endpoint returns an individual PDU by PZ code, with each organisation's associated lower layer super output area and local authority district.
        """
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns the parent NHS Trust or Local Health Board for a given Paediatric Diabetes Unit (with their primary organisation and Paediatric Diabetes Network), against a PZ code. If no code is provide, a list is returned.",
        description="This endpoint returns the parent NHS Trust or Local Health Board for a given Paediatric Diabetes Unit (with their primary organisation and Paediatric Diabetes Network), against a PZ code. If no code is provide, a list is returned.",
        operation_id="list_parents",
    )
    @action(detail=False, methods=["get"], url_path="parent", url_name="parent")
    def list_parents(self, request, pz_code=None):
        """
        This endpoint returns a list of Paediatric Diabetes Units from England and Wales with each organisation's associated lower layer super output area and local authority district.
        """
        return super().list(
            request,
        )

    @extend_schema(
        description="This endpoint returns the parent NHS Trust or Local Health Board for a given Paediatric Diabetes Unit (with their primary organisation and Paediatric Diabetes Network), against a PZ code. If no code is provide, a list is returned.",
        summary="This endpoint returns the parent NHS Trust or Local Health Board for a given Paediatric Diabetes Unit (with their primary organisation and Paediatric Diabetes Network), against a PZ code. If no code is provide, a list is returned.",
        operation_id="retrieve_parent",
    )
    @action(detail=True, methods=["get"], url_path="parent", url_name="parent")
    def retrieve_parent(self, request, pz_code=None):
        """
        This endpoint returns an individual PDU by PZ code, with each organisation's associated lower layer super output area and local authority district.
        """
        return super().retrieve(request, pz_code)


@extend_schema(
    tags=["Child Health Geographies"],
    request=PaediatricDiabetesUnitWithNestedOrganisationAndParentSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "paediatric_diabetes_units/sibling-organisations/RGT01/",
                    external_value="external value",
                    value=[
                        {
                            "pz_code": "PZ215",
                            "organisations": [
                                {
                                    "ods_code": "RJZ01",
                                    "name": "KING'S COLLEGE HOSPITAL (DENMARK HILL)",
                                    "parent": {
                                        "ods_code": "RJZ",
                                        "name": "KING'S COLLEGE HOSPITAL NHS FOUNDATION TRUST",
                                        "address_line_1": "DENMARK HILL",
                                        "address_line_2": "",
                                        "town": "LONDON",
                                        "postcode": "SE5 9RS",
                                        "country": "ENGLAND",
                                        "telephone": None,
                                        "website": None,
                                        "active": True,
                                        "published_at": None,
                                    },
                                }
                            ],
                        }
                    ],
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
