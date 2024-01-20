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

from ..models import LocalHealthBoard
from ..serializers import (
    LocalHealthBoardSerializer,
    LocalHealthBoardOrganisationsSerializer,
)


@extend_schema(
    request=LocalHealthBoardSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/local_health_boards/1/",
                    external_value="external value",
                    value=[
                        {
                            "ods_code": "7A3",
                            "publication_date": "2022-04-14",
                            "boundary_identifier": "W11000031",
                            "name": "Swansea Bay University Health Board",
                            "welsh_name": "Bwrdd Iechyd Prifysgol Bae Abertawe",
                            "bng_e": 266283,
                            "bng_n": 198175,
                            "long": -3.93489,
                            "lat": 51.6664,
                            "globalid": "b260424c-9314-45c2-8a46-eec1284fd8c3",
                            "geom": {
                                "type": "MultiPolygon",
                                "coordinates": [
                                    [
                                        [
                                            [275483.4995, 211465.298],
                                            [277901.6027, 207685.9998],
                                            [279570.8978, 207520.0973],
                                            [280885.8037, 210027.399599999],
                                            [284883.6029, 211157.2962],
                                            [289467.5024, 209568.800899999],
                                            [290258.2037, 207411.398399999],
                                            [291042.5976, 203307.6031],
                                            [290193.4965, 199030.397500001],
                                            [291929.6013, 195233.6043],
                                            [289668.5005, 194419.5973],
                                            [285114.5966, 195380.6022],
                                            [283746.9965, 192792.603],
                                            [283969.3988, 190496.8002],
                                            [282979.0021, 190763.8038],
                                            [282726.7032, 189740.196799999],
                                            [285363.0038, 186404.9015],
                                            [285222.4997, 183571.102700001],
                                            [283039.1003, 183409.4989],
                                            [281949.8041, 182292.1987],
                                            [277977.4052, 183319.683599999],
                                            [276045.1036, 187176.2006],
                                            [274164.5997, 187726.4001],
                                            [275426.6835, 187578.304300001],
                                            [275196.2001, 188533.5011],
                                            [274201.3998, 188319.9001],
                                            [275429.2965, 188928.2991],
                                            [274563.0998, 188743.300000001],
                                            [271951.2999, 192237.501],
                                            [272946.601, 193255.999600001],
                                            [269507.8997, 192653.2029],
                                            [266657.7964, 191484.7974],
                                            [266548.9039, 192273.7015],
                                            [264500.5009, 192190.5954],
                                            [261995.7008, 190757.095699999],
                                            [261484.0041, 188689.297599999],
                                            [263093.3994, 187418.000399999],
                                            [262802.6999, 186955.5001],
                                            [259777.3998, 186858.500399999],
                                            [259067.9001, 187658.100199999],
                                            [256988.0959, 186282.196599999],
                                            [253768.7999, 187783.9001],
                                            [254325.402, 188642.600400001],
                                            [250611.3987, 186981.5964],
                                            [250816.7997, 184655.4013],
                                            [247916.6983, 185545.997300001],
                                            [246600.9009, 184386.299699999],
                                            [242136.2, 187196.200200001],
                                            [240102.4997, 187428.3993],
                                            [241477.9995, 188869.300100001],
                                            [240200.0962, 192613.304400001],
                                            [242268.1966, 193248.8024],
                                            [244920.5421, 196823.2892],
                                            [245784.1133, 196081.241599999],
                                            [244941.229, 194824.6713],
                                            [246296.2616, 195306.4893],
                                            [248553.2006, 194507.602],
                                            [248282.8286, 193902.405300001],
                                            [250298.0926, 194182.0078],
                                            [250717.1999, 195040.5997],
                                            [253666.8, 196112.1998],
                                            [254657.2007, 197061.601],
                                            [256141.6992, 197472.103499999],
                                            [256943.4985, 196960.1],
                                            [256143.5998, 197975.299900001],
                                            [257067.7021, 198714.4978],
                                            [256196.1951, 200515.9246],
                                            [257082.8938, 200456.921499999],
                                            [257389.0988, 201842.0251],
                                            [258388.5981, 202261.525],
                                            [258188.5977, 203161.217599999],
                                            [258913.8992, 202868.4213],
                                            [258569.1979, 205418.2216],
                                            [261964.4026, 208998.6041],
                                            [262123.1035, 210278.297800001],
                                            [264479.6986, 209051.698899999],
                                            [266481.6984, 209849.500499999],
                                            [267740.6038, 210255.304400001],
                                            [269875.4975, 209475.897500001],
                                            [270282.9024, 211591.6019],
                                            [269101.8964, 213372.302200001],
                                            [271494.3987, 214057.7959],
                                            [274703.5991, 213086.6039],
                                            [275483.4995, 211465.298],
                                        ]
                                    ]
                                ],
                            },
                        }
                    ],
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of Local Health Boards (Wales) with their boundaries, or an individual LHB by ods_code.",
)
class LocalHealthBoardViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of Local Health Boards (Wales) with their boundaries, or an individual LHB by ods_code.

    Filter Parameters:

    `ods_code`,
    `publication_date`,
    `boundary_identifier`,
    `name`,
    `welsh_name`,

    If none are passed, a list is returned.

    """

    queryset = LocalHealthBoard.objects.all().order_by("-name")
    serializer_class = LocalHealthBoardSerializer
    lookup_field = "ods_code"
    filterset_fields = [
        "ods_code",
        "publication_date",
        "boundary_identifier",
        "name",
        "welsh_name",
    ]
    filter_backends = (DjangoFilterBackend,)


@extend_schema(
    request=LocalHealthBoard,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Valid Response",
            examples=[
                OpenApiExample(
                    "/local_health_boards/1/organisations",
                    external_value="external value",
                    value={
                        "ods_code": "7A3",
                        "boundary_identifier": "W11000031",
                        "name": "Swansea Bay University Health Board",
                        "organisations": [
                            {"ods_code": "7A3LW", "name": "CHILD DEVELOPMENT UNIT"},
                            {"ods_code": "7A3C7", "name": "MORRISTON HOSPITAL"},
                            {"ods_code": "7A3CJ", "name": "NEATH PORT TALBOT HOSPITAL"},
                            {"ods_code": "7A3B7", "name": "PRINCESS OF WALES HOSPITAL"},
                            {"ods_code": "7A3C4", "name": "SINGLETON HOSPITAL"},
                            {"ods_code": "7A3LE", "name": "THE MOUNT SURGERY"},
                        ],
                    },
                    response_only=True,
                ),
            ],
        ),
    },
    summary="This endpoint returns a list of Local Health Boards, or an individual LHB by ods_code, with all child organisations nested within.",
)
class LocalHealthBoardOrganisationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This endpoint returns a list of Local Health Boards, or an individual LHB by ods_code, with all child organisations nested within.

    Filter Parameters:

    `ods_code`
    `boundary_identifier`
    `name`

    If none are passed, a list is returned.

    """

    queryset = LocalHealthBoard.objects.all().order_by("-name")
    serializer_class = LocalHealthBoardOrganisationsSerializer
    lookup_field = "ods_code"
    filterset_fields = [
        "ods_code",
        "boundary_identifier",
        "name",
    ]
    filter_backends = (DjangoFilterBackend,)
