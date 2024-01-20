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

from ..models import NHSEnglandRegion
from ..serializers import (
    NHSEnglandRegionSerializer,
    NHSEnglandRegionWithNestedOrganisationsSerializer,
)


@extend_schema(
    request=NHSEnglandRegionSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/nhs_england_region/1/",
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
                        "globalid": "4e8906ed-a19e-49ac-a111-3474937655e9",
                        "geom": "SRID=27700;MULTIPOLYGON (((87767.5686999997 8868.28480000049, 89125.5478999997 ...",
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
    `globalid`
    `geom`

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
        "globalid",
    ]
    filter_backends = (DjangoFilterBackend,)


@extend_schema(
    request=NHSEnglandRegionWithNestedOrganisationsSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/nhs_england_region/1/",
                    external_value="external value",
                    value={
                        "region_code": "Y58",
                        "publication_date": "2022-07-30",
                        "boundary_identifier": "E40000006",
                        "name": "South West",
                        "nhs_england_region_organisations": [
                            {"ods_code": "RVN38", "name": "BARTON HILL SETTLEMENT"},
                            {
                                "ods_code": "RA723",
                                "name": "BRISTOL ROYAL HOSPITAL FOR CHILDREN",
                            },
                            {
                                "ods_code": "C1G7Z",
                                "name": "CDC POOLE @ DORSET HEALTH VILLAGE",
                            },
                            {
                                "ods_code": "RTE01",
                                "name": "CHELTENHAM GENERAL HOSPITAL",
                            },
                            {"ods_code": "RK98A", "name": "CHILD DEVELOPMENT CENTRE"},
                            {"ods_code": "REFCH", "name": "CHILD HEALTH"},
                            {"ods_code": "RK950", "name": "DERRIFORD HOSPITAL"},
                            {"ods_code": "RBD01", "name": "DORSET COUNTY HOSPITAL"},
                            {"ods_code": "RVN4T", "name": "DROVE HOUSE"},
                            {"ods_code": "RVJT9", "name": "EASTGATE HOUSE"},
                            {
                                "ods_code": "RTE03",
                                "name": "GLOUCESTERSHIRE ROYAL HOSPITAL",
                            },
                            {"ods_code": "RVNE6", "name": "KINGSWOOD HUB"},
                            {"ods_code": "RN351", "name": "MOREDON MEDICAL CENTRE"},
                            {"ods_code": "RK901", "name": "MOUNT GOULD HOSPITAL"},
                            {"ods_code": "RH5A8", "name": "MUSGROVE PARK HOSPITAL"},
                            {
                                "ods_code": "RH880",
                                "name": "NORTH DEVON DISTRICT HOSPITAL",
                            },
                            {"ods_code": "RVNE9", "name": "OSPREY COURT"},
                            {"ods_code": "RVJT4", "name": "PATCHWAY LOCALITY HUB"},
                            {"ods_code": "R0D01", "name": "POOLE HOSPITAL"},
                            {"ods_code": "R0D02", "name": "ROYAL BOURNEMOUTH HOSPITAL"},
                            {
                                "ods_code": "REF12",
                                "name": "ROYAL CORNWALL HOSPITAL (TRELISKE)",
                            },
                            {
                                "ods_code": "RK963",
                                "name": "ROYAL DEVON & EXETER FOUNDATION HOSPITAL",
                            },
                            {
                                "ods_code": "RH801",
                                "name": "ROYAL DEVON & EXETER HOSPITAL (WONFORD)",
                            },
                            {"ods_code": "RD130", "name": "ROYAL UNITED HOSPITAL"},
                            {
                                "ods_code": "RNZ02",
                                "name": "SALISBURY DISTRICT HOSPITAL",
                            },
                            {
                                "ods_code": "RA773",
                                "name": "SOUTH BRISTOL COMMUNITY HOSPITAL",
                            },
                            {
                                "ods_code": "RVJ72",
                                "name": "SOUTH GLOUCESTERSHIRE COMMUNITY HEALTH SERVICES",
                            },
                            {"ods_code": "RA707", "name": "ST MICHAEL'S HOSPITAL"},
                            {"ods_code": "RN341", "name": "SWINDON HEALTH CENTRE"},
                            {"ods_code": "RN325", "name": "THE GREAT WESTERN HOSPITAL"},
                            {"ods_code": "RA901", "name": "TORBAY HOSPITAL"},
                            {"ods_code": "RVJJ8", "name": "WESTON GENERAL HOSPITAL"},
                            {"ods_code": "RA430", "name": "YEOVIL DISTRICT HOSPITAL"},
                        ],
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of NHS England regions, or an individual region by region_code, with all child organisations nested within.",
)
class NHSEnglandRegionOrganisationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of NHS England regions, or an individual region by region_code, with all child organisations nested within.

    Filter Parameters:

    `region_code`
    `publication_date`
    `boundary_identifier`
    `name`

    If none are passed, a list is returned.

    """

    queryset = NHSEnglandRegion.objects.all().order_by("-name")
    serializer_class = NHSEnglandRegionWithNestedOrganisationsSerializer
    lookup_field = "region_code"
    filterset_fields = [
        "region_code",
        "publication_date",
        "boundary_identifier",
        "name",
    ]
    filter_backends = (DjangoFilterBackend,)
