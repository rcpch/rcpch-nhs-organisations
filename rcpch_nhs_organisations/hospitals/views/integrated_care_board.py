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

from ..models import IntegratedCareBoard
from ..serializers import (
    IntegratedCareBoardSerializer,
    IntegratedCareBoardWithNestedOrganisationsSerializer,
)


@extend_schema(
    request=IntegratedCareBoardSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/integrated_care_boards/1/",
                    external_value="external value",
                    value={
                        "boundary_identifier": "E54000054",
                        "name": "NHS West Yorkshire Integrated Care Board",
                        "bng_e": 419321,
                        "bng_n": 443326,
                        "long": -1.70754,
                        "lat": 53.8858,
                        "globalid": "a00a4766-d3af-4580-88bf-9c8f2cbf1bb4",
                        "geom": "SRID=27700;MULTIPOLYGON (((387209 483538.094000001, 388888.5 481430.594000001 ... ",
                        "ods_code": "QWO",
                        "publication_date": "2023-03-15",
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of Integrated Care Boards from England and Wales, or an individual ICB by ODS code, with boundary information.",
)
class IntegratedCareBoardViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of Integrated Care Boards from England and Wales, or an individual ICB by ODS code, with boundary information.

    Filter Parameters:

    `boundary_identifier, `
    `name, `
    `bng_e, `
    `bng_n, `
    `long, `
    `lat, `
    `globalid, `
    `ods_code, `
    `publication_date, `

    If none are passed, a list is returned.

    """

    queryset = IntegratedCareBoard.objects.all().order_by("name")
    serializer_class = IntegratedCareBoardSerializer
    lookup_field = "ods_code"
    filterset_fields = [
        "boundary_identifier",
        "name",
        "ods_code",
        "publication_date",
    ]
    filter_backends = (DjangoFilterBackend,)


@extend_schema(
    request=IntegratedCareBoardWithNestedOrganisationsSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/integrated_care_boards/1/",
                    external_value="external value",
                    value={
                        "boundary_identifier": "E54000054",
                        "name": "NHS West Yorkshire Integrated Care Board",
                        "ods_code": "QWO",
                        "publication_date": "2023-03-15",
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a simple list of Integrated Care Boards from England and Wales, or an individual ICB by ODS code, with associated organisations nested in.",
)
class IntegratedCareBoardOrganisationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a simple list of Integrated Care Boards from England and Wales, or an individual ICB by ODS code, with associated organisations nested in.

    Filter Parameters:

    `boundary_identifier, `
    `name, `
    `ods_code, `
    `publication_date, `

    If none are passed, a list is returned.

    """

    queryset = IntegratedCareBoard.objects.all().order_by("name")
    serializer_class = IntegratedCareBoardWithNestedOrganisationsSerializer
    lookup_field = "ods_code"
    filterset_fields = [
        "boundary_identifier",
        "name",
        "ods_code",
        "publication_date",
    ]
    filter_backends = (DjangoFilterBackend,)
