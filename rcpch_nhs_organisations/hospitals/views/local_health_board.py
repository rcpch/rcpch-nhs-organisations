from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
)
from rest_framework.decorators import api_view
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
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns a Local Health Board by ods_code.",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns GeoJSON boundaries of all Local Health Board.",
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
    )
    @action(detail=True, url_path="geojson", url_name="geojson")
    def retrieve_geojson(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = LocalHealthBoardGeoJSONSerializer(instance)
        return Response(serializer.data)


@extend_schema(
    request=LocalHealthBoard,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/local_health_boards/1/organisations",
                    external_value="external value",
                    value={
                        "ods_code": "7A3",
                        "boundary_identifier": "W11000031",
                        "name": "Swansea Bay University Health Board",
                        "organisations": [
                            {"ods_code": "7A3LW", "name": "CHILD DEVELOPMENT UNIT"},
                            {"ods_code": "7A3C7", "name": "MORRISTON HOSPITAL"},
                            {"ods_code": "7A3CJ", "name": "NEATH PORT TALBOT HOSPITAL"},
                            {"ods_code": "7A3B7", "name": "PRINCESS OF WALES HOSPITAL"},
                            {"ods_code": "7A3C4", "name": "SINGLETON HOSPITAL"},
                            {"ods_code": "7A3LE", "name": "THE MOUNT SURGERY"},
                        ],
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of Local Health Boards, or an individual LHB by ods_code, with all child organisations nested within.",
)
class LocalHealthBoardOrganisationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of Local Health Boards, or an individual LHB by ods_code, with all child organisations nested within.

    Filter Parameters:

    `ods_code`
    `boundary_identifier`
    `name`

    If none are passed, a list is returned.

    """

    queryset = LocalHealthBoard.objects.all().order_by("-name")
    serializer_class = LocalHealthBoardOrganisationsSerializer
    lookup_field = "ods_code"
    filterset_fields = [
        "ods_code",
        "boundary_identifier",
        "name",
    ]
    filter_backends = (DjangoFilterBackend,)
