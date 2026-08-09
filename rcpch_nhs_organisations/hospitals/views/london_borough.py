# Python imports

# Django import
from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
)
from rest_framework.decorators import action
from rest_framework.response import Response

# Third party imports
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiResponse,
)
from drf_spectacular.openapi import OpenApiExample

# RCPCH imports
from ..models import LondonBorough
from ..serializers import (
    LondonBoroughSerializer,
    LondonBoroughGeoJSONSerializer,
    LondonBoroughWithNestedOrganisationsSerializer,
)


@extend_schema(
    tags=["Boundaries"],
    request=LondonBoroughSerializer,
    responses={
        200: OpenApiResponse(
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/london_boroughs/1/",
                    external_value="external value",
                    value={
                        "name": "Westminster",
                        "gss_code": "E09000033",
                        "hectares": 2203.005,
                        "nonld_area": 54.308,
                        "ons_inner": "T",
                        "sub_2009": "",
                        "sub_2006": "",
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of London Boroughs with their boundaries, or an individual borough by gss_code.",
)
class LondonBoroughViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of NHS England regions with their boundaries, or an individual region by region_code.

    Filter Parameters:

    `name`,
    `gss_code`,
    `hectares`,
    `nonld_area`,
    `ons_inner`,
    `sub_2009`,
    `sub_2006`,

    If none are passed, a list is returned.

    """

    queryset = LondonBorough.objects.all().order_by("-name")
    serializer_class = LondonBoroughSerializer
    lookup_field = "gss_code"
    filterset_fields = [
        "name",
        "gss_code",
        "hectares",
        "nonld_area",
        "ons_inner",
        "sub_2009",
        "sub_2006",
    ]
    filter_backends = (DjangoFilterBackend,)
    pagination_class = None

    def get_serializer_class(self):
        if self.action == "geojson":
            return LondonBoroughGeoJSONSerializer
        return super().get_serializer_class()

    @extend_schema(
        summary="This endpoint returns a London Borough by ONS gss code. It also returns the area in hectares.",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns a list of London Boroughs, with their areas in hectares.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns GeoJSON boundaries of a London Borough by gss_code.",
        examples=[
            OpenApiExample(
                "/london_boroughs/E09000033/geojson",
                external_value="external value",
                value={
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiPolygon",
                        "coordinates": [
                            [
                                [
                                    [528549.5, 177903.8],
                                    [528542.6, 177949.4],
                                    [528540.1, 177958.4],
                                    [528534.5, 177971.1],
                                ]
                            ]
                        ],
                    },
                    "properties": {
                        "name": "Westminster",
                        "gss_code": "E09000033",
                        "hectares": 2203.005,
                        "nonld_area": 54.308,
                        "ons_inner": "T",
                        "sub_2009": "",
                        "sub_2006": "",
                    },
                },  # noqa
                response_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["get"], url_path="geojson")
    def retrieve_geojson(self, request, gss_code=None):
        """
        This endpoint returns GeoJSON boundaries of a London Borough by gss_code.
        """
        london_borough = self.get_object()
        serializer = LondonBoroughGeoJSONSerializer(london_borough)
        return Response(serializer.data)

    @extend_schema(
        summary="This endpoint returns all London Boroughs with their child paediatric organisations nested in.",
        operation_id="list_london_boroughs_with_organisations",
        responses={
            200: OpenApiResponse(
                description="Valid Response",
                examples=[
                    OpenApiExample(
                        "Example Response",
                        value={
                            "name": "Tower Hamlets",
                            "gss_code": "E09000030",
                            "organisations": [
                                {
                                    "ods_code": "R1H12",
                                    "name": "THE ROYAL LONDON HOSPITAL",
                                }
                            ],
                        },
                        response_only=True,
                    ),
                ],
            ),
        },
    )
    @action(detail=False, url_path="organisations")
    def list_organisations(self, request):
        """
        This endpoint returns a list of London Boroughs with all child organisations nested within.
        """
        queryset = self.get_queryset()
        serializer = LondonBoroughWithNestedOrganisationsSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="This endpoint returns a London Borough by gss_code, with all child organisations nested within.",
        operation_id="retrieve_london_borough_with_organisations",
        responses={
            200: OpenApiResponse(
                description="Valid Response",
                examples=[
                    OpenApiExample(
                        "Example Response",
                        value={
                            "name": "Tower Hamlets",
                            "gss_code": "E09000030",
                            "organisations": [
                                {
                                    "ods_code": "R1H12",
                                    "name": "THE ROYAL LONDON HOSPITAL",
                                }
                            ],
                        },
                        response_only=True,
                    ),
                ],
            ),
        },
    )
    @action(detail=True, methods=["get"], url_path="organisations")
    def retrieve_organisations(self, request, gss_code=None):
        """
        This endpoint returns a London Borough by gss_code, with all child organisations nested within.
        """
        london_borough = self.get_object()
        serializer = LondonBoroughWithNestedOrganisationsSerializer(london_borough)
        return Response(serializer.data)
