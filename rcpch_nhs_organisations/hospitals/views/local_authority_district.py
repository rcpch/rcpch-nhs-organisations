from rest_framework.response import Response
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from rest_framework.decorators import action
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
    OpenApiTypes,
    OpenApiParameter,
)
from drf_spectacular.types import OpenApiTypes

from ..models import LocalAuthorityDistrict
from ..serializers import LocalAuthorityDistrictSerializer


@extend_schema(
    request=LocalAuthorityDistrictSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/local_authority_district/1/",
                    external_value="external value",
                    value=[
                        {
                            "lad24cd": "E06000001",
                            "lad24nm": "Hartlepool",
                            "lad24nmw": "",
                            "bng_e": 447160,
                            "bng_n": 531474,
                            "long": -1.270225,
                            "lat": 54.676159,
                            "globalid": "{F1D3D2A4-1D4D-4D3D-8D3D-3D1D4D3D1D4D}",
                            "geom": [...],
                        }
                    ],
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of Local Authority Districts with their boundaries, or an individual local authority district.",
)
class LocalAuthorityDistrictViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of Local Authority Districts (2024 publication) with their boundaries, or an individual local health authority by LAD24CD.

    Filter Parameters:

    `lad24cd`
    `lad24nm`
    `lad24nmw`
    `bng_e`
    `bng_n`
    `long`
    `lat`
    `globalid`

    If none are passed, a list is returned.

    """

    queryset = LocalAuthorityDistrict.objects.all().order_by("-lad24nm")
    serializer_class = LocalAuthorityDistrictSerializer
    lookup_field = "lad24cd"
    filterset_fields = [
        "lad24cd",
        "lad24nm",
        "lad24nmw",
        "bng_e",
        "bng_n",
        "long",
        "lat",
        "globalid",
    ]
    filter_backends = (DjangoFilterBackend,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="lat",
                type=OpenApiTypes.NUMBER,
                description="Latitude of the center point",
            ),
            OpenApiParameter(
                name="long",
                type=OpenApiTypes.NUMBER,
                description="Longitude of the center point",
            ),
            OpenApiParameter(
                name="radius", type=OpenApiTypes.NUMBER, description="Radius in meters"
            ),
        ],
        responses={200: LocalAuthorityDistrictSerializer(many=True)},
        summary="Get Local Authority Districts within a radius",
        description="This endpoint returns a list of Local Authority Districts within a specified radius from a given latitude and longitude. It also returns geojson boundaries for each district.",
    )
    @action(detail=False, methods=["get"])
    def within_radius(self, request):
        try:
            lat = float(request.query_params.get("lat"))
            long = float(request.query_params.get("long"))
            radius = float(request.query_params.get("radius"))
        except (TypeError, ValueError):
            return Response({"error": "Invalid parameters"}, status=400)

        user_location = Point(long, lat, srid=4326)
        queryset = self.queryset.annotate(
            distance=Distance("geom", user_location)
        ).filter(distance__lte=radius)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
