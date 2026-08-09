from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
)
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiResponse,
    OpenApiParameter,
    OpenApiTypes,
)
from drf_spectacular.types import OpenApiTypes

from ..models import IntegratedCareBoard
from ..serializers import (
    IntegratedCareBoardSerializer,
    IntegratedCareBoardGeoJSONSerializer,
    IntegratedCareBoardWithNestedOrganisationsSerializer,
)


@extend_schema(
    tags=["Integrated Care Boards"],
    parameters=[
        OpenApiParameter(
            name="boundary_identifier",
            type=OpenApiTypes.STR,
            description="Boundary Identifier",
        ),
        OpenApiParameter(name="name", type=OpenApiTypes.STR, description="Name"),
        OpenApiParameter(
            name="bng_e",
            type=OpenApiTypes.NUMBER,
            description="British National Grid (BNG) Easting",
        ),
        OpenApiParameter(
            name="bng_n",
            type=OpenApiTypes.NUMBER,
            description="British National Grid (BNG) Northing",
        ),
        OpenApiParameter(
            name="long", type=OpenApiTypes.NUMBER, description="Longitude"
        ),
        OpenApiParameter(name="lat", type=OpenApiTypes.NUMBER, description="Latitude"),
        OpenApiParameter(
            name="ods_code", type=OpenApiTypes.STR, description="ODS Code"
        ),
        OpenApiParameter(
            name="publication_date",
            type=OpenApiTypes.DATE,
            description="Publication Date",
        ),
    ],
)
class IntegratedCareBoardViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of Integrated Care Boards from England and Wales, or an individual ICB by ODS code.
    If no ODS code is passed, a list is returned.
    If geojson is requested, the boundary information is included (super-generalized, clipped, SRID=27700).
    Acknowledgements: Contains National Statistics data © Crown copyright and database right 2021.

    Filter Parameters:

    `boundary_identifier, `
    `name, `
    `bng_e, `
    `bng_n, `
    `long, `
    `lat, `
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
    pagination_class = None

    def get_serializer_class(self):
        if self.action in ["list_geojson", "retrieve_geojson"]:
            return IntegratedCareBoardGeoJSONSerializer
        elif self.action in ["list_organisations", "retrieve_organisations"]:
            return IntegratedCareBoardWithNestedOrganisationsSerializer
        return IntegratedCareBoardSerializer

    @extend_schema(
        summary="This endpoint returns a list of Integrated Care Boards from England and Wales.",
        responses={200: IntegratedCareBoardSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns an individual Integrated Care Board by ODS code.",
        responses={200: IntegratedCareBoardSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        request=IntegratedCareBoardGeoJSONSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Valid Response",
                examples=[
                    OpenApiExample(
                        "/integrated_care_boards/geojson",
                        external_value="external value",
                        value={
                            "type": "FeatureCollection",
                            "features": [
                                {
                                    "type": "Feature",
                                    "geometry": {
                                        "type": "MultiPolygon",
                                        "coordinates": [
                                            [
                                                [
                                                    [387209, 483538.094000001],
                                                    [388888.5, 481430.594000001],
                                                    [388888.5, 481430.594000001],
                                                    [387209, 483538.094000001],
                                                ]
                                            ]
                                        ],
                                    },
                                    "properties": {
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
                                }
                            ],
                        },
                        response_only=True,
                    ),
                ],
            ),
        },
        summary="This endpoint returns a list of Integrated Care Boards from England and Wales, with boundaries as geojson (SRID 27700).",
        operation_id="list_geojson",
    )
    @action(detail=False, methods=["get"], url_path="geojson")
    def list_geojson(self, request):
        queryset = self.get_queryset()
        serializer = IntegratedCareBoardGeoJSONSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=IntegratedCareBoardGeoJSONSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Valid Response",
                examples=[
                    OpenApiExample(
                        "/integrated_care_boards/1/geojson",
                        external_value="external value",
                        value={
                            "type": "Feature",
                            "geometry": {
                                "type": "MultiPolygon",
                                "coordinates": [
                                    [
                                        [
                                            [387209, 483538.094000001],
                                            [388888.5, 481430.594000001],
                                            [388888.5, 481430.594000001],
                                            [387209, 483538.094000001],
                                        ]
                                    ]
                                ],
                            },
                            "properties": {
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
                        },
                        response_only=True,
                    ),
                ],
            ),
        },
        operation_id="retrieve_geojson",
        summary="This endpoint returns a single Integrated Care Board from England and Wales by ODS code, with boundaries as geojson (SRID=27700).",
    )
    @action(detail=True, methods=["get"], url_path="geojson")
    def retrieve_geojson(self, request, ods_code=None):
        instance = self.get_object()
        serializer = IntegratedCareBoardGeoJSONSerializer(instance)
        return Response(serializer.data)

    @extend_schema(
        summary="This endpoint returns a list of Integrated Care Boards from England and Wales, with their organisations nested in.",
        responses={
            200: IntegratedCareBoardWithNestedOrganisationsSerializer(many=True)
        },
    )
    @action(detail=False, methods=["get"], url_path="organisations")
    def list_organisations(self, request):
        queryset = self.get_queryset()
        serializer = IntegratedCareBoardWithNestedOrganisationsSerializer(
            queryset, many=True
        )
        return Response(serializer.data)

    @extend_schema(
        summary="This endpoint returns an individual Integrated Care Board by ODS code, with their organisations nested in.",
        responses={200: IntegratedCareBoardWithNestedOrganisationsSerializer},
    )
    @action(detail=True, methods=["get"], url_path="organisations")
    def retrieve_organisations(self, request, ods_code=None):
        instance = self.get_object()
        serializer = IntegratedCareBoardWithNestedOrganisationsSerializer(instance)
        return Response(serializer.data)
