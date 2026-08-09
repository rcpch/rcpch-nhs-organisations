# Python imports

# Django imports
from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
)
from rest_framework.decorators import action
from rest_framework.response import Response

# Third Party imports
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes

from ..models import NHSEnglandRegion
from ..serializers import (
    NHSEnglandRegionSerializer,
    NHSEnglandRegionGeoJSONSerializer,
    NHSEnglandRegionWithNestedOrganisationsSerializer,
    NHSEnglandRegionWithNestedTrustsSerializer,
)


@extend_schema(
    tags=["NHS England Regions"],
    request=NHSEnglandRegionSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/nhs_england_region/Y58/",
                    external_value="external value",
                    value={
                        "region_code": "Y58",
                        "publication_date": "2022-07-30",
                        "boundary_identifier": "E40000006",
                        "name": "South West",
                        "bng_e": 285015,
                        "bng_n": 102567,
                        "long": -3.63343,
                        "lat": 50.8112,
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of NHS England regions with their boundaries, or an individual region by region_code.",
)
class NHSEnglandRegionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of NHS England regions with their boundaries, or an individual region by region_code.

    Filter Parameters:

    `region_code`
    `publication_date`
    `boundary_identifier`
    `name`
    `bng_e`
    `bng_n`
    `long`
    `lat`

    If none are passed, a list is returned.

    """

    queryset = NHSEnglandRegion.objects.all().order_by("-name")
    serializer_class = NHSEnglandRegionSerializer
    lookup_field = "region_code"
    filterset_fields = [
        "region_code",
        "publication_date",
        "boundary_identifier",
        "name",
        "bng_e",
        "bng_n",
        "long",
        "lat",
    ]
    filter_backends = (DjangoFilterBackend,)

    def get_serializer_class(self):
        if self.action == "retrieve_nhs_england_geojson":
            return NHSEnglandRegionGeoJSONSerializer
        return super().get_serializer_class()

    @extend_schema(
        summary="This endpoint returns GeoJSON boundaries of an individual NHS England region by region_code.",
        operation_id="retrieve_nhs_england_geojson",
        examples=[
            OpenApiExample(
                "/nhs_england_region/Y58/geojson/",
                external_value="external value",
                value={
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiPolygon",
                        "coordinates": [
                            [
                                [
                                    [87639.5325999996, 8861.14220000058],
                                    [87767.5686999997, 8868.28480000049],
                                ]
                            ],
                            [
                                [
                                    [93194.4424000001, 11947.8482000008],
                                    [93203.2514000004, 11105.0558000002],
                                ]
                            ],
                            [
                                [
                                    [90235.1972000003, 14756.3121000007],
                                    [89302.3872999996, 13383.4123],
                                ]
                            ],
                            [
                                [
                                    [88032.3142999997, 14719.2186999992],
                                ]
                            ],
                        ],
                    },
                    "properties": {
                        "region_code": "Y58",
                        "publication_date": "2022-07-30",
                        "boundary_identifier": "E40000006",
                        "name": "South West",
                        "bng_e": 285015,
                        "bng_n": 102567,
                        "long": -3.63343,
                        "lat": 50.8112,
                        "globalid": "4e8906ed-a19e-49ac-a111-3474937655e9",
                    },
                },
            )
        ],
    )
    @action(detail=True, methods=["get"], url_path="geojson")
    def retrieve_nhs_england_geojson(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @extend_schema(
        summary="This endpoint returns a list of NHS England regions.",
        operation_id="list",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns an individual NHS England region by region_code.",
        operation_id="retrieve",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns an individual NHS England region by region code with all paediatric organisations nested in.",
        operation_id="list_organisations",
    )
    @action(detail=True, methods=["get"], url_path="organisations")
    def retrieve_organisations(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = NHSEnglandRegionWithNestedOrganisationsSerializer(instance)
        return Response(serializer.data)

    @extend_schema(
        summary="This endpoint returns a list of NHS England regions with all paediatric organisations nested in.",
        operation_id="list_nhs_england_regions_organisations",
    )
    @action(detail=False, methods=["get"], url_path="organisations")
    def list_nhs_england_regions_organisations(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = NHSEnglandRegionWithNestedOrganisationsSerializer(
            queryset, many=True
        )
        return Response(serializer.data)

    @extend_schema(
        summary="This endpoint returns all NHS England regions with constituent NHS Trusts nested in.",
        operation_id="list_trusts",
        examples=[
            OpenApiExample(
                "/nhs_england_region/trusts/",
                external_value="external value",
                value=[
                    {
                        "region_code": "Y59",
                        "publication_date": "2022-07-30",
                        "boundary_identifier": "E40000005",
                        "name": "South East",
                        "trusts": [
                            {
                                "ods_code": "RTK",
                                "name": "ASHFORD AND ST PETER'S HOSPITALS NHS FOUNDATION TRUST",
                            },
                            {
                                "ods_code": "RWX",
                                "name": "BERKSHIRE HEALTHCARE NHS FOUNDATION TRUST",
                            },
                            {
                                "ods_code": "RXQ",
                                "name": "BUCKINGHAMSHIRE HEALTHCARE NHS TRUST",
                            },
                            {
                                "ods_code": "RN7",
                                "name": "DARTFORD AND GRAVESHAM NHS TRUST",
                            },
                            {
                                "ods_code": "RVV",
                                "name": "EAST KENT HOSPITALS UNIVERSITY NHS FOUNDATION TRUST",
                            },
                            {
                                "ods_code": "RXC",
                                "name": "EAST SUSSEX HEALTHCARE NHS TRUST",
                            },
                            {
                                "ods_code": "RVR",
                                "name": "EPSOM AND ST HELIER UNIVERSITY HOSPITALS NHS TRUST",
                            },
                            {
                                "ods_code": "RDU",
                                "name": "FRIMLEY HEALTH NHS FOUNDATION TRUST",
                            },
                            {
                                "ods_code": "RN5",
                                "name": "HAMPSHIRE HOSPITALS NHS FOUNDATION TRUST",
                            },
                            {"ods_code": "R1F", "name": "ISLE OF WIGHT NHS TRUST"},
                            {
                                "ods_code": "RAX",
                                "name": "KINGSTON HOSPITAL NHS FOUNDATION TRUST",
                            },
                            {
                                "ods_code": "RWF",
                                "name": "MAIDSTONE AND TUNBRIDGE WELLS NHS TRUST",
                            },
                            {"ods_code": "RPA", "name": "MEDWAY NHS FOUNDATION TRUST"},
                            {
                                "ods_code": "RTH",
                                "name": "OXFORD UNIVERSITY HOSPITALS NHS FOUNDATION TRUST",
                            },
                            {
                                "ods_code": "RHU",
                                "name": "PORTSMOUTH HOSPITALS UNIVERSITY NATIONAL HEALTH SERVICE TRUST",
                            },
                            {
                                "ods_code": "RHW",
                                "name": "ROYAL BERKSHIRE NHS FOUNDATION TRUST",
                            },
                            {
                                "ods_code": "RA2",
                                "name": "ROYAL SURREY COUNTY HOSPITAL NHS FOUNDATION TRUST",
                            },
                            {"ods_code": "R1C", "name": "SOLENT NHS TRUST"},
                            {
                                "ods_code": "RW1",
                                "name": "SOUTHERN HEALTH NHS FOUNDATION TRUST",
                            },
                            {
                                "ods_code": "RTP",
                                "name": "SURREY AND SUSSEX HEALTHCARE NHS TRUST",
                            },
                            {
                                "ods_code": "RDR",
                                "name": "SUSSEX COMMUNITY NHS FOUNDATION TRUST",
                            },
                            {
                                "ods_code": "RHM",
                                "name": "UNIVERSITY HOSPITAL SOUTHAMPTON NHS FOUNDATION TRUST",
                            },
                            {
                                "ods_code": "RYR",
                                "name": "UNIVERSITY HOSPITALS SUSSEX NHS FOUNDATION TRUST",
                            },
                        ],
                    },
                ],
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="trusts")
    def list_trusts(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = NHSEnglandRegionWithNestedTrustsSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="This endpoint returns an individual NHS England region by region code with all NHS Trusts nested in.",
        operation_id="retrieve_trusts",
        examples=[
            OpenApiExample(
                "/nhs_england_region/Y59/trusts/",
                external_value="external value",
                value={
                    "region_code": "Y59",
                    "publication_date": "2022-07-30",
                    "boundary_identifier": "E40000005",
                    "name": "South East",
                    "trusts": [
                        {
                            "ods_code": "RTK",
                            "name": "ASHFORD AND ST PETER'S HOSPITALS NHS FOUNDATION TRUST",
                        },
                        {
                            "ods_code": "RWX",
                            "name": "BERKSHIRE HEALTHCARE NHS FOUNDATION TRUST",
                        },
                        {
                            "ods_code": "RXQ",
                            "name": "BUCKINGHAMSHIRE HEALTHCARE NHS TRUST",
                        },
                        {
                            "ods_code": "RN7",
                            "name": "DARTFORD AND GRAVESHAM NHS TRUST",
                        },
                        {
                            "ods_code": "RVV",
                            "name": "EAST KENT HOSPITALS UNIVERSITY NHS FOUNDATION TRUST",
                        },
                        {
                            "ods_code": "RXC",
                            "name": "EAST SUSSEX HEALTHCARE NHS TRUST",
                        },
                        {
                            "ods_code": "RVR",
                            "name": "EPSOM AND ST HELIER UNIVERSITY HOSPITALS NHS TRUST",
                        },
                        {
                            "ods_code": "RDU",
                            "name": "FRIMLEY HEALTH NHS FOUNDATION TRUST",
                        },
                        {
                            "ods_code": "RN5",
                            "name": "HAMPSHIRE HOSPITALS NHS FOUNDATION TRUST",
                        },
                        {"ods_code": "R1F", "name": "ISLE OF WIGHT NHS TRUST"},
                        {
                            "ods_code": "RAX",
                            "name": "KINGSTON HOSPITAL NHS FOUNDATION TRUST",
                        },
                        {
                            "ods_code": "RWF",
                            "name": "MAIDSTONE AND TUNBRIDGE WELLS NHS TRUST",
                        },
                        {"ods_code": "RPA", "name": "MEDWAY NHS FOUNDATION TRUST"},
                        {
                            "ods_code": "RTH",
                            "name": "OXFORD UNIVERSITY HOSPITALS NHS FOUNDATION TRUST",
                        },
                    ],
                },
            )
        ],
    )
    @action(detail=True, methods=["get"], url_path="trusts")
    def retrieve_trusts(self, request, *args, **kwargs):
        nhs_england_region = self.get_object()
        serializer = NHSEnglandRegionWithNestedTrustsSerializer(nhs_england_region)
        return Response(serializer.data)
