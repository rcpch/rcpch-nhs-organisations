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
from drf_spectacular.types import OpenApiTypes

from ..models import LondonBorough
from ..serializers import (
    LondonBoroughSerializer,
    LondonBoroughWithNestedOrganisationsSerializer,
)


@extend_schema(
    request=LondonBoroughSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/london_boroughs/1/",
                    external_value="external value",
                    value={
                        "name": "",
                        "gss_code": "",
                        "hectares": "",
                        "nonld_area": "",
                        "ons_inner": "",
                        "sub_2009": "",
                        "sub_2006": "",
                        "geom": "SRID=27700;MULTIPOLYGON (((87767.5686999997 8868.28480000049, 89125.5478999997 ...",
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


@extend_schema(
    request=LondonBorough,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/london_boroughs/1/organisations",
                    external_value="external value",
                    value={
                        "name": "",
                        "gss_code": "",
                        "hectares": "",
                        "nonld_area": "",
                        "ons_inner": "",
                        "sub_2009": "",
                        "sub_2006": "",
                        "geom": "SRID=27700;MULTIPOLYGON (((87767.5686999997 8868.28480000049, 89125.5478999997 ...",
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of London Boroughts, or an individual London Borough by gss_code, with all child organisations nested within.",
)
class LondonBoroughOrganisationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of London Boroughts, or an individual London Borough by gss_code, with all child organisations nested within.

    Filter Parameters:

    `region_code`
    `boundary_identifier`
    `name`

    If none are passed, a list is returned.

    """

    queryset = LondonBorough.objects.all().order_by("-name")
    serializer_class = LondonBoroughWithNestedOrganisationsSerializer
    lookup_field = "gss_code"
    filterset_fields = [
        "gss_code",
        "name",
    ]
    filter_backends = (DjangoFilterBackend,)
