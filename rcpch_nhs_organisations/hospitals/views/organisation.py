# Django imports
from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
    filters,
    generics,
)
from rest_framework.response import Response
from rest_framework.decorators import action

# Third-party imports
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
)

# RCPCH NHS Organisations imports
from ..models import Organisation
from ..serializers import (
    OrganisationSerializer,
    OrganisationNoParentsSerializer,
)


@extend_schema(
    tags=["Organisations"],
    request=OrganisationSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/organisations/RGT01/",
                    external_value="external value",
                    value={
                        "ods_code": "RGT01",
                        "name": "ADDENBROOKE'S HOSPITAL",
                        "website": "https://www.cuh.nhs.uk/",
                        "address1": "HILLS ROAD",
                        "address2": "",
                        "address3": "",
                        "telephone": "01223 245151",
                        "city": "CAMBRIDGE",
                        "county": "CAMBRIDGESHIRE",
                        "latitude": 52.17513275,
                        "longitude": 0.140753239,
                        "postcode": "CB2 0QQ",
                        "geocode_coordinates": {
                            "type": "Point",
                            "coordinates": [0.140753239, 52.17513275],
                        },
                        "active": True,
                        "published_at": "",
                        "local_authority_district": {
                            "lad24cd": "E07000008",
                            "lad24nm": "Cambridge",
                            "lad24nmw": "",
                            "bng_e": 545420,
                            "bng_n": 257901,
                            "long": 0.126436,
                            "lat": 52.2002,
                        },
                        "lower_layer_super_output_area": {
                            "lsoa11cd": "E01017995",
                            "lsoa11nm": "Cambridge 013D",
                            "lsoa11nmw": "Cambridge 013D",
                            "bng_e": 546965,
                            "bng_n": 254958,
                            "long": 0.147751,
                            "lat": 52.1733,
                        },
                        "paediatric_diabetes_unit": {
                            "pz_code": "PZ041",
                            "paediatric_diabetes_network": "",
                        },
                        "trust": {
                            "ods_code": "RGT",
                            "name": "CAMBRIDGE UNIVERSITY HOSPITALS NHS FOUNDATION TRUST",
                            "address_line_1": "CAMBRIDGE BIOMEDICAL CAMPUS",
                            "address_line_2": "HILLS ROAD",
                            "town": "CAMBRIDGE",
                            "postcode": "CB2 0QQ",
                            "country": "ENGLAND",
                            "telephone": "",
                            "website": "",
                            "active": True,
                            "published_at": "",
                        },
                        "local_health_board": "",
                        "integrated_care_board": {
                            "boundary_identifier": "E54000056",
                            "name": "NHS Cambridgeshire and Peterborough Integrated Care Board",
                            "ods_code": "QUE",
                        },
                        "nhs_england_region": {
                            "region_code": "Y61",
                            "publication_date": "2022-07-30",
                            "boundary_identifier": "E40000007",
                            "name": "East of England",
                        },
                        "openuk_network": {
                            "name": "Eastern Paediatric Epilepsy Network",
                            "boundary_identifier": "EPEN",
                            "country": "England",
                            "publication_date": "2022-12-08",
                        },
                        "london_borough": "",
                        "country": {
                            "boundary_identifier": "E92000001",
                            "name": "England",
                        },
                    },
                    response_only="true",
                ),
            ],
        ),
    },
)
class OrganisationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of NHS Organisations (Acute or Community Hospitals), with nested parent regions or organisations, from the UK, or a single organisation against an ODS code.

    Filter Parameters:

    `ods_code`
    `name`
    `website`
    `address1`
    `address2`
    `address3`
    `telephone`
    `city`
    `county`
    `latitude`
    `longitude`
    `postcode`
    `active`
    `published_at`

    If none are passed, a list is returned.

    """

    queryset = Organisation.objects.all().order_by("name")
    serializer_class = OrganisationSerializer
    lookup_field = "ods_code"
    filterset_fields = [
        "ods_code",
        "name",
        "website",
        "address1",
        "address2",
        "address3",
        "telephone",
        "city",
        "county",
        "latitude",
        "longitude",
        "postcode",
        "active",
        "published_at",
    ]
    filter_backends = (DjangoFilterBackend,)
    pagination_class = None

    def get_serializer_class(self):
        if self.action in ["list_limited", "retrieve_limited"]:
            return OrganisationNoParentsSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in [
            "list_paediatric_diabetes_units",
            "retrieve_paediatric_diabetes_unit",
        ]:
            queryset = queryset.filter(paediatric_diabetes_unit__isnull=False)
        return queryset

    @extend_schema(
        summary="This endpoint returns a list of NHS Organisations (Acute or Community Hospitals), with nested parent regions or organisations, from the UK.",
        examples=[
            OpenApiExample(
                "/organisations/",
                external_value="external value",
                value=[
                    {
                        "ods_code": "RGT01",
                        "name": "ADDENBROOKE'S HOSPITAL",
                        "website": "https://www.cuh.nhs.uk/",
                        "address1": "HILLS ROAD",
                        "address2": "",
                        "address3": "",
                        "telephone": "01223 245151",
                        "city": "CAMBRIDGE",
                        "county": "CAMBRIDGESHIRE",
                        "latitude": 52.17513275,
                        "longitude": 0.140753239,
                        "postcode": "CB2 0QQ",
                        "geocode_coordinates": {
                            "type": "Point",
                            "coordinates": [0.140753239, 52.17513275],
                        },
                        "active": True,
                        "published_at": "",
                        "local_authority_district": {
                            "lad24cd": "E07000008",
                            "lad24nm": "Cambridge",
                            "lad24nmw": "",
                            "bng_e": 545420,
                            "bng_n": 257901,
                            "long": 0.126436,
                            "lat": 52.2002,
                        },
                        "lower_layer_super_output_area": {
                            "lsoa11cd": "E01017995",
                            "lsoa11nm": "Cambridge 013D",
                            "lsoa11nmw": "Cambridge 013D",
                            "bng_e": 546965,
                            "bng_n": 254958,
                            "long": 0.147751,
                            "lat": 52.1733,
                        },
                        "paediatric_diabetes_unit": {
                            "pz_code": "PZ041",
                            "paediatric_diabetes_network": "",
                        },
                        "trust": {
                            "ods_code": "RGT",
                            "name": "CAMBRIDGE UNIVERSITY HOSPITALS NHS FOUNDATION TRUST",
                            "address_line_1": "CAMBRIDGE BIOMEDICAL CAMPUS",
                            "address_line_2": "HILLS ROAD",
                            "town": "CAMBRIDGE",
                            "postcode": "CB2 0QQ",
                            "country": "ENGLAND",
                            "telephone": "",
                            "website": "",
                            "active": True,
                            "published_at": "",
                        },
                        "local_health_board": "",
                        "integrated_care_board": {
                            "boundary_identifier": "E54000056",
                            "name": "NHS Cambridgeshire and Peterborough Integrated Care Board",
                            "ods_code": "QUE",
                        },
                        "nhs_england_region": {
                            "region_code": "Y61",
                            "publication_date": "2022-07-30",
                            "boundary_identifier": "E40000007",
                            "name": "East of England",
                        },
                        "openuk_network": {
                            "name": "Eastern Paediatric Epilepsy Network",
                            "boundary_identifier": "EPEN",
                            "country": "England",
                            "publication_date": "2022-12-08",
                        },
                        "london_borough": "",
                        "country": {
                            "boundary_identifier": "E92000001",
                            "name": "England",
                        },
                    },
                ],
            )
        ],
    )
    def list(self, request, *args, **kwargs):
        """
        This endpoint returns a list of NHS Organisations (Acute or Community Hospitals), with nested parent regions or organisations, from the UK.
        """
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns a single NHS Organisation (Acute or Community Hospital), with nested parent regions or organisations, from the UK, against an ODS code.",
    )
    def retrieve(self, request, *args, **kwargs):
        """
        This endpoint returns a single NHS Organisation (Acute or Community Hospital), with nested parent regions or organisations, from the UK, against an ODS code.
        """
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns a simple list of NHS Organisations (Acute or Community Hospitals), without the health or geographical relationships.",
        operation_id="list_organisations_limited",
        examples=[
            OpenApiExample(
                "/organisations/limited",
                external_value="external value",
                value=[
                    {
                        "ods_code": "RGT01",
                        "name": "ADDENBROOKE'S HOSPITAL",
                    },
                    {
                        "ods_code": "RCF22",
                        "name": "AIREDALE GENERAL HOSPITAL",
                    },
                ],
            )
        ],
    )
    @action(detail=False, url_path="limited", url_name="limited")
    def list_limited(self, request, *args, **kwargs):
        """
        This endpoint returns a simple list of NHS Organisations (Acute or Community Hospitals), without the health or geographical relationships.
        """
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns a single NHS Organisation (Acute or Community Hospital), without the health or geographical relationships, against an ODS code.",
        operation_id="retrieve_organisation_limited",
        examples=[
            OpenApiExample(
                "/organisations/RGT01/limited",
                external_value="external value",
                value={
                    "ods_code": "RGT01",
                    "name": "ADDENBROOKE'S HOSPITAL",
                },
            )
        ],
    )
    @action(detail=True, url_path="limited", url_name="limited")
    def retrieve_limited(self, request, *args, **kwargs):
        """
        This endpoint returns a single NHS Organisation (Acute or Community Hospital), without the health or geographical relationships, against an ODS code.
        """
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns a list of all NHS Organisations (Acute or Community Hospitals) associated with a parent Paediatric Diabetes Unit. Includes all the organisation's health and geographical relationships.",
        operation_id="list_paediatric_diabetes_units",
        examples=[
            OpenApiExample(
                "/organisations/paediatric-diabetes-units",
                external_value="external value",
                value=[
                    {
                        "ods_code": "RGT01",
                        "name": "ADDENBROOKE'S HOSPITAL",
                        "website": "https://www.cuh.nhs.uk/",
                        "address1": "HILLS ROAD",
                        "address2": "",
                        "address3": "",
                        "telephone": "01223 245151",
                        "city": "CAMBRIDGE",
                        "county": "CAMBRIDGESHIRE",
                        "latitude": 52.17513275,
                        "longitude": 0.140753239,
                        "postcode": "CB2 0QQ",
                        "geocode_coordinates": {
                            "type": "Point",
                            "coordinates": [0.140753239, 52.17513275],
                        },
                        "active": True,
                        "published_at": "",
                        "local_authority_district": {
                            "lad24cd": "E07000008",
                            "lad24nm": "Cambridge",
                            "lad24nmw": "",
                            "bng_e": 545420,
                            "bng_n": 257901,
                            "long": 0.126436,
                            "lat": 52.2002,
                        },
                        "lower_layer_super_output_area": {
                            "lsoa11cd": "E01017995",
                            "lsoa11nm": "Cambridge 013D",
                            "lsoa11nmw": "Cambridge 013D",
                            "bng_e": 546965,
                            "bng_n": 254958,
                            "long": 0.147751,
                            "lat": 52.1733,
                        },
                        "paediatric_diabetes_unit": {
                            "pz_code": "PZ041",
                            "paediatric_diabetes_network": "",
                        },
                        "trust": {
                            "ods_code": "RGT",
                            "name": "CAMBRIDGE UNIVERSITY HOSPITALS NHS FOUNDATION TRUST",
                            "address_line_1": "CAMBRIDGE BIOMEDICAL CAMPUS",
                            "address_line_2": "HILLS ROAD",
                            "town": "CAMBRIDGE",
                            "postcode": "CB2 0QQ",
                            "country": "ENGLAND",
                            "telephone": "",
                            "website": "",
                            "active": True,
                            "published_at": "",
                        },
                        "local_health_board": "",
                        "integrated_care_board": {
                            "boundary_identifier": "E54000056",
                            "name": "NHS Cambridgeshire and Peterborough Integrated Care Board",
                            "ods_code": "QUE",
                        },
                        "nhs_england_region": {
                            "region_code": "Y61",
                            "publication_date": "2022-07-30",
                            "boundary_identifier": "E40000007",
                            "name": "East of England",
                        },
                        "openuk_network": {
                            "name": "Eastern Paediatric Epilepsy Network",
                            "boundary_identifier": "EPEN",
                            "country": "England",
                            "publication_date": "2022-12-08",
                        },
                        "london_borough": "",
                        "country": {
                            "boundary_identifier": "E92000001",
                            "name": "England",
                        },
                    },
                    {
                        "ods_code": "RCF22",
                        "name": "AIREDALE GENERAL HOSPITAL",
                        "website": "https://www.airedaletrust.nhs.uk/",
                        "address1": "SKIPTON ROAD",
                        "address2": "STEETON",
                        "address3": "",
                        "telephone": "",
                        "city": "KEIGHLEY",
                        "county": "WEST YORKSHIRE",
                        "latitude": 53.8979454,
                        "longitude": -1.962710142,
                        "postcode": "BD20 6TD",
                        "geocode_coordinates": {
                            "type": "Point",
                            "coordinates": [-1.962710142, 53.8979454],
                        },
                        "active": True,
                        "published_at": "",
                        "local_authority_district": {
                            "lad24cd": "E08000032",
                            "lad24nm": "Bradford",
                            "lad24nmw": "",
                            "bng_e": 408395,
                            "bng_n": 438626,
                            "long": -1.87389,
                            "lat": 53.8438,
                        },
                        "lower_layer_super_output_area": {
                            "lsoa11cd": "E01010645",
                            "lsoa11nm": "Bradford 004H",
                            "lsoa11nmw": "Bradford 004H",
                            "bng_e": 403114,
                            "bng_n": 444893,
                            "long": -1.95409,
                            "lat": 53.9002,
                        },
                        "paediatric_diabetes_unit": {
                            "pz_code": "PZ047",
                            "paediatric_diabetes_network": "",
                        },
                        "trust": {
                            "ods_code": "RCF",
                            "name": "AIREDALE NHS FOUNDATION TRUST",
                            "address_line_1": "AIREDALE GENERAL HOSPITAL",
                            "address_line_2": "SKIPTON ROAD",
                            "town": "KEIGHLEY",
                            "postcode": "BD20 6TD",
                            "country": "ENGLAND",
                            "telephone": "",
                            "website": "",
                            "active": True,
                            "published_at": "",
                        },
                        "local_health_board": "",
                        "integrated_care_board": {
                            "boundary_identifier": "E54000054",
                            "name": "NHS West Yorkshire Integrated Care Board",
                            "ods_code": "QWO",
                        },
                        "nhs_england_region": {
                            "region_code": "Y63",
                            "publication_date": "2022-07-30",
                            "boundary_identifier": "E40000012",
                            "name": "North East and Yorkshire",
                        },
                        "openuk_network": {
                            "name": "Yorkshire Paediatric Neurology Network",
                            "boundary_identifier": "YPEN",
                            "country": "England",
                            "publication_date": "2022-12-08",
                        },
                        "london_borough": "",
                        "country": {
                            "boundary_identifier": "E92000001",
                            "name": "England",
                        },
                    },
                ],
            ),
        ],
    )
    @action(
        detail=False,
        url_path="paediatric-diabetes-units",
        url_name="paediatric_diabetes_units",
    )
    def list_paediatric_diabetes_units(self, request, *args, **kwargs):
        """
        This endpoint returns a list of all NHS Organisations (Acute or Community Hospitals) associated with a parent Paediatric Diabetes Unit. Includes all the organisation's health and geographical relationships.
        """
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="This endpoint returns a specific NHS Organisation (Acute or Community Hospital) associated with a parent Paediatric Diabetes Unit, by ods_code. Includes all the organisation's health and geographical relationships.",
        operation_id="retrieve_paediatric_diabetes_unit",
        examples=[
            OpenApiExample(
                "/organisations/RGT01/paediatric-diabetes-units",
                external_value="external value",
                value={
                    "ods_code": "RGT01",
                    "name": "ADDENBROOKE'S HOSPITAL",
                    "website": "https://www.cuh.nhs.uk/",
                    "address1": "HILLS ROAD",
                    "address2": "",
                    "address3": "",
                    "telephone": "01223 245151",
                    "city": "CAMBRIDGE",
                    "county": "CAMBRIDGESHIRE",
                    "latitude": 52.17513275,
                    "longitude": 0.140753239,
                    "postcode": "CB2 0QQ",
                    "geocode_coordinates": {
                        "type": "Point",
                        "coordinates": [0.140753239, 52.17513275],
                    },
                    "active": True,
                    "published_at": "",
                    "local_authority_district": {
                        "lad24cd": "E07000008",
                        "lad24nm": "Cambridge",
                        "lad24nmw": "",
                        "bng_e": 545420,
                        "bng_n": 257901,
                        "long": 0.126436,
                        "lat": 52.2002,
                    },
                    "lower_layer_super_output_area": {
                        "lsoa11cd": "E01017995",
                        "lsoa11nm": "Cambridge 013D",
                        "lsoa11nmw": "Cambridge 013D",
                        "bng_e": 546965,
                        "bng_n": 254958,
                        "long": 0.147751,
                        "lat": 52.1733,
                    },
                    "paediatric_diabetes_unit": {
                        "pz_code": "PZ041",
                        "paediatric_diabetes_network": "",
                    },
                    "trust": {
                        "ods_code": "RGT",
                        "name": "CAMBRIDGE UNIVERSITY HOSPITALS NHS FOUNDATION TRUST",
                        "address_line_1": "CAMBRIDGE BIOMEDICAL CAMPUS",
                        "address_line_2": "HILLS ROAD",
                        "town": "CAMBRIDGE",
                        "postcode": "CB2 0QQ",
                        "country": "ENGLAND",
                        "telephone": "",
                        "website": "",
                        "active": True,
                        "published_at": "",
                    },
                    "local_health_board": "",
                    "integrated_care_board": {
                        "boundary_identifier": "E54000056",
                        "name": "NHS Cambridgeshire and Peterborough Integrated Care Board",
                        "ods_code": "QUE",
                    },
                    "nhs_england_region": {
                        "region_code": "Y61",
                        "publication_date": "2022-07-30",
                        "boundary_identifier": "E40000007",
                        "name": "East of England",
                    },
                    "openuk_network": {
                        "name": "Eastern Paediatric Epilepsy Network",
                        "boundary_identifier": "EPEN",
                        "country": "England",
                        "publication_date": "2022-12-08",
                    },
                    "london_borough": "",
                    "country": {
                        "boundary_identifier": "E92000001",
                        "name": "England",
                    },
                },
            ),
        ],
    )
    @action(
        detail=True,
        url_path="paediatric-diabetes-units",
        url_name="paediatric_diabetes_units",
    )
    def retrieve_paediatric_diabetes_unit(self, request, *args, **kwargs):
        """
        This endpoint returns a specific NHS Organisation (Acute or Community Hospital) associated with a parent Paediatric Diabetes Unit, by ods_code. Includes all the organisation's health and geographical relationships.
        """
        return super().retrieve(request, *args, **kwargs)
