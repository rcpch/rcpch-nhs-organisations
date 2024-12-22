from django.urls import include, path
from rest_framework import routers
from .views import (
    OrganisationViewSet,
    IntegratedCareBoardViewSet,
    LocalAuthorityDistrictViewSet,
    LocalHealthBoardViewSet,
    LondonBoroughViewSet,
    NHSEnglandRegionViewSet,
    PaediatricDiabetesUnitViewSet,
    PaediatricDiabetesUnitForOrganisationWithParentViewSet,
    # PaediatricDiabetesUnitForParentViewSet,
    TrustViewSet,
)

from drf_spectacular.views import SpectacularJSONAPIView, SpectacularSwaggerView

router = routers.DefaultRouter()

from django.contrib import admin

# organisation endpoints
router.register(r"organisations", viewset=OrganisationViewSet, basename="organisation")

# trust endpoints
router.register(
    r"trusts",
    viewset=TrustViewSet,
    basename="trusts",
)
# local health board endpoints
router.register(
    r"local_health_boards",
    viewset=LocalHealthBoardViewSet,
    basename="local_health_board",
)
# ICB endpoints
router.register(
    r"integrated_care_boards",
    viewset=IntegratedCareBoardViewSet,
    basename="integrated_care_board",
)
# London Borough endpoints
router.register(
    r"london_boroughs",
    viewset=LondonBoroughViewSet,
    basename="london_borough",
)
# NHS England Region endpoints
router.register(
    r"nhs_england_regions",
    viewset=NHSEnglandRegionViewSet,
    basename="nhs_england_region",
)

# RCPCH networks
router.register(
    r"paediatric_diabetes_units",
    viewset=PaediatricDiabetesUnitViewSet,
    basename="paediatric_diabetes_unit",
)

# router.register(
#     r"local_authority_districts",
#     viewset=LocalAuthorityDistrictViewSet,
#     basename="local_authority_district",
# )

drf_routes = [
    # rest framework paths
    path("", include(router.urls)),
    # JSON Schema
    path(
        "paediatric_diabetes_units/sibling-organisations/<str:ods_code>/",
        PaediatricDiabetesUnitForOrganisationWithParentViewSet.as_view({"get": "list"}),
        name="paediatric_diabetes_unit_organisation_with_parent",
    ),
    path("schema/", SpectacularJSONAPIView.as_view(), name="schema"),
    # Swagger UI
    path("swagger-ui/", SpectacularSwaggerView.as_view(), name="swagger-ui"),
]

urlpatterns = []

urlpatterns += (path("admin/", admin.site.urls),)


urlpatterns += drf_routes
