from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
)
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiResponse,
)
from rest_framework.response import Response
from drf_spectacular.types import OpenApiTypes
from rest_framework.decorators import action

from ..models import LocalHealthBoard
from ..serializers import (
    LocalHealthBoardSerializer,
    LocalHealthBoardGeoJSONSerializer,
    LocalHealthBoardOrganisationsSerializer,
)


@extend_schema(tags=["Local Health Boards"])
class LocalHealthBoardViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of Local Health Boards (Wales), or an individual LHB by ods_code.
    If geojson is required, use the `/geojson` endpoint.

    Filter Parameters:

    `ods_code`,
    `publication_date`,
    `boundary_identifier`,
    `name`,
    `welsh_name`,

    If none are passed, a list is returned.

    """

    queryset = LocalHealthBoard.objects.all().order_by("-name")
    serializer_class = LocalHealthBoardSerializer
    lookup_field = "ods_code"
    filterset_fields = [
        "ods_code",
        "publication_date",
        "boundary_identifier",
        "name",
        "welsh_name",
    ]
    filter_backends = (DjangoFilterBackend,)

    def get_serializer_class(self):
        if self.action in ["list_geojson", "retrieve_geojson"]:
            return LocalHealthBoardGeoJSONSerializer
        return super().get_serializer_class()

    @extend_schema(
        summary="This endpoint returns a list of Local Health Boards (Wales).",
        examples=[
            OpenApiExample(
                "/local_health_boards/",
                value=[
                    {
                        "ods_code": "7A3",
                        "publication_date": "2022-04-14",
                        "boundary_identifier": "W11000031",
                        "name": "Swansea Bay University Health Board",
                        "welsh_name": "Bwrdd Iechyd Prifysgol Bae Abertawe",
                        "bng_e": 266283,
                        "bng_n": 198175,
                        "long": -3.93489,
                        "lat": 51.6664,
                    },
                    {
                        "ods_code": "7A7",
                        "publication_date": "2022-04-14",
                        "boundary_identifier": "W11000024",
                        "name": "Powys Teaching Health Board",
                        "welsh_name": "Bwrdd Iechyd Addysgu Powys",
                        "bng_e": 302328,
                        "bng_n": 273254,
                        "long": -3.43533,
                        "lat": 52.34863,
                    },
                ],
                response_only=True,
            )
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns a Local Health Board by ods_code.",
        examples=[
            OpenApiExample(
                "/local_health_boards/7A3/",
                value={
                    "ods_code": "7A3",
                    "publication_date": "2022-04-14",
                    "boundary_identifier": "W11000031",
                    "name": "Swansea Bay University Health Board",
                    "welsh_name": "Bwrdd Iechyd Prifysgol Bae Abertawe",
                    "bng_e": 266283,
                    "bng_n": 198175,
                    "long": -3.93489,
                    "lat": 51.6664,
                },
                response_only=True,
            )
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns GeoJSON boundaries of all Local Health Boards.",
        operation_id="list_local_health_boards_geojson",
    )
    @action(detail=False, url_path="geojson", url_name="geojson")
    def list_geojson(self, request, ods_code=None):
        """
        This endpoint returns a GeoJSON object of a Local Health Board by ods_code.
        """
        queryset = self.get_queryset()
        serializer = LocalHealthBoardGeoJSONSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="This endpoint returns GeoJSON boundary of a Local Health Board by ods_code.",
        operation_id="retrieve_local_health_board_geojson",
    )
    @action(detail=True, url_path="geojson", url_name="geojson")
    def retrieve_geojson(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = LocalHealthBoardGeoJSONSerializer(instance)
        return Response(serializer.data)

    @extend_schema(
        summary="This endpoint returns a list of Local Health Boards with all child organisations nested within.",
        examples=[
            OpenApiExample(
                "local_health_boards/organisations",
                value={
                    "ods_code": "7A3",
                    "boundary_identifier": "W11000031",
                    "name": "Swansea Bay University Health Board",
                    "organisations": [
                        {"ods_code": "7A3LW", "name": "CHILD DEVELOPMENT UNIT"},
                        {"ods_code": "7A3C7", "name": "MORRISTON HOSPITAL"},
                        {"ods_code": "7A3CJ", "name": "NEATH PORT TALBOT HOSPITAL"},
                        {"ods_code": "7A3C4", "name": "SINGLETON HOSPITAL"},
                        {"ods_code": "7A3LE", "name": "THE MOUNT SURGERY"},
                    ],
                },
                response_only=True,
            ),
        ],
        operation_id="list_local_health_boards_with_organisations",
    )
    @action(detail=False, url_path="organisations", url_name="organisations")
    def list_organisations(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = LocalHealthBoardOrganisationsSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="This endpoint returns an individual Local Health Board by ODS code with all child organisations nested within.",
        examples=[
            OpenApiExample(
                "Local Health Board with organisations",
                value={
                    "ods_code": "7A1",
                    "name": "Aneurin Bevan University Health Board",
                    "welsh_name": "Bwrdd Iechyd Prifysgol Aneurin Bevan",
                    "bng_e": "328000",
                    "bng_n": "188000",
                    "long": "-3.051",
                    "lat": "51.656",
                    "boundary_identifier": "LHB",
                    "organisations": [
                        {
                            "ods_code": "7A1AA",
                            "name": "Aneurin Bevan University Health Board",
                            "type": "Local Health Board",
                            "parent": "7A1",
                        },
                        {
                            "ods_code": "7A1AA",
                            "name": "Aneurin Bevan University Health Board",
                            "type": "Local Health Board",
                            "parent": "7A1",
                        },
                    ],
                },
                response_only=True,
            )
        ],
        operation_id="retrieve_local_health_board_with_organisations",
    )
    @action(detail=True, url_path="organisations", url_name="organisations")
    def retrieve_organisations(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = LocalHealthBoardOrganisationsSerializer(instance)
        return Response(serializer.data)
