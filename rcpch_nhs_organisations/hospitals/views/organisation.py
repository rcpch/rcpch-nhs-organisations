from rest_framework import (
    viewsets,
    serializers,  # serializers here required for drf-spectacular @extend_schema
)
from rest_framework.decorators import api_view
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes

from ..models import Organisation
from ..serializers import OrganisationSerializer


@extend_schema(
    request=OrganisationSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/organisations/1/",
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
                        "active": "true",
                        "published_at": "null",
                        "paediatric_diabetes_unit": {"pz_code": "PZ041"},
                        "trust": {
                            "ods_code": "RGT",
                            "name": "CAMBRIDGE UNIVERSITY HOSPITALS NHS FOUNDATION TRUST",
                            "address_line_1": "CAMBRIDGE BIOMEDICAL CAMPUS",
                            "address_line_2": "HILLS ROAD",
                            "town": "CAMBRIDGE",
                            "postcode": "CB2 0QQ",
                            "country": "ENGLAND",
                            "telephone": "null",
                            "website": "null",
                            "active": "true",
                            "published_at": "null",
                        },
                        "local_health_board": "null",
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
                        "london_borough": "null",
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
    summary="This endpoint returns a list of NHS Organisations (Acute or Community Hospitals), with nested parent regions or organisations, from the UK, or a single organisation against an ODS code.",
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
