from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes

from ..models import OPENUKNetwork
from ..serializers import OPENUKNetworkSerializer


@extend_schema(
    tags=["Child Health Geographies"],
    parameters=[
        OpenApiParameter(
            name="name",
            type=OpenApiTypes.STR,
            description="OPENUK Network name",
        ),
        OpenApiParameter(
            name="boundary_identifier",
            type=OpenApiTypes.STR,
            description="Boundary Identifier",
        ),
        OpenApiParameter(
            name="country",
            type=OpenApiTypes.STR,
            description="Country the network belongs to",
        ),
        OpenApiParameter(
            name="publication_date",
            type=OpenApiTypes.DATE,
            description="Publication Date",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/openuk_networks/E38000001/",
                    external_value="external value",
                    value={
                        "name": "North Thames Paediatric Epilepsy Network",
                        "boundary_identifier": "E38000001",
                        "country": "England",
                        "publication_date": "2023-04-01",
                    },
                    response_only=True,
                ),
            ],
        ),
    },
)
class OPENUKNetworkViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of OPENUK Networks (paediatric epilepsy
    networks), or an individual network by boundary identifier.

    Filter Parameters:

    `name`
    `boundary_identifier`
    `country`
    `publication_date`

    If none are passed, a list is returned.

    """

    queryset = OPENUKNetwork.objects.all().order_by("name")
    serializer_class = OPENUKNetworkSerializer
    lookup_field = "boundary_identifier"
    filterset_fields = [
        "name",
        "boundary_identifier",
        "country",
        "publication_date",
    ]
    filter_backends = (DjangoFilterBackend,)
    pagination_class = None
