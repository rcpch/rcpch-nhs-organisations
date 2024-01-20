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

from ..models import Country
from ..serializers import CountrySerializer


@extend_schema(
    request=CountrySerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/country/1/",
                    external_value="external value",
                    value={
                        "boundary_identifier": "E92000001",
                        "name": "England",
                        "welsh_name": "Lloegr",
                        "bng_e": "394883",
                        "bng_n": "370883",
                        "long": "-2.07811",
                        "lat": "53.235",
                        "globalid": "f6b76559-3626-49b8-b50b-bd15efcb0505",
                        "geom": "",
                    },
                    response_only=True,
                ),
            ],
        ),
    },
)
class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of Countries from the UK.

    Filter Parameters:

    `boundary_identifier`
    `name`
    `welsh_name`
    `bng_e`
    `bng_n`
    `long`
    `lat`
    `globalid`
    `geom`

    If none are passed, a list is returned.

    """

    queryset = Country.objects.all().order_by("-name")
    serializer_class = CountrySerializer
    filterset_fields = [
        "boundary_identifier",
        "name",
        "welsh_name",
        "bng_e",
        "bng_n",
        "long",
        "lat",
        "globalid",
    ]
    filter_backends = (DjangoFilterBackend,)
