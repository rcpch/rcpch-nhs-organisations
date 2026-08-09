from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes

from ..models import Country
from ..serializers import CountrySerializer


# Fields a client may select via ?fields=. The geometry column is the
# expensive one, so this lets consumers request a lightweight payload
# (e.g. ?fields=boundary_identifier,name) without a separate endpoint.
COUNTRY_FIELDS = [
    "boundary_identifier",
    "name",
    "welsh_name",
    "bng_e",
    "bng_n",
    "long",
    "lat",
    "globalid",
    "geom",
]


@extend_schema(
    tags=["Boundaries"],
    request=CountrySerializer,
    parameters=[
        OpenApiParameter(
            name="fields",
            type=OpenApiTypes.STR,
            description=(
                "Comma-separated list of fields to return. "
                "Use this to omit the (large) `geom` column, e.g. "
                "`?fields=boundary_identifier,name`. "
                f"Allowed fields: {', '.join(COUNTRY_FIELDS)}."
            ),
            required=False,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/countries/E92000001/",
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
    This endpoint returns a list of Countries from the UK, or an individual
    Country by boundary identifier (e.g. `E92000001` for England).

    Filter Parameters:

    `boundary_identifier`
    `name`
    `welsh_name`
    `bng_e`
    `bng_n`
    `long`
    `lat`
    `globalid`

    If none are passed, a list is returned.

    To omit the (large) `geom` geometry column, pass `?fields=` with a
    comma-separated list of the columns you want, e.g.
    `/countries/?fields=boundary_identifier,name`.

    """

    queryset = Country.objects.all().order_by("-name")
    serializer_class = CountrySerializer
    lookup_field = "boundary_identifier"
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
    pagination_class = None

    def get_serializer(self, *args, **kwargs):
        # Support ?fields=boundary_identifier,name to project a subset of
        # columns. This avoids a separate /limited/ endpoint while letting
        # clients drop the heavy `geom` geometry from the response.
        requested = self.request.query_params.get("fields")
        if requested:
            fields = [
                f.strip() for f in requested.split(",") if f.strip() in COUNTRY_FIELDS
            ]
            if fields:
                kwargs["fields"] = fields
        return super().get_serializer(*args, **kwargs)
