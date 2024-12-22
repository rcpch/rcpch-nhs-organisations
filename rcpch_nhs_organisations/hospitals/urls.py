from django.urls import include, path
from rest_framework import routers
from .views import (
    OrganisationViewSet,
    OrganisationLimitedViewSet,
    IntegratedCareBoardViewSet,
    LocalAuthorityDistrictViewSet,
    LocalHealthBoardViewSet,
    LondonBoroughViewSet,
    NHSEnglandRegionViewSet,
    OrganisationsAssociatedWithPaediatricDiabetesUnitsList,
    PaediatricDiabetesUnitViewSet,
    PaediatricDiabetesUnitWithNestedOrganisationsViewSet,
    PaediatricDiabetesUnitForOrganisationWithParentViewSet,
    PaediatricDiabetesUnitForParentViewSet,
    TrustViewSet,
)

from drf_spectacular.views import SpectacularJSONAPIView, SpectacularSwaggerView

router = routers.DefaultRouter()

from django.contrib import admin

# returns a limited list of organisations by name and ods code
router.register(
    r"organisations/limited",
    viewset=OrganisationLimitedViewSet,
    basename="organisation-limited",
)

# returns a list of organisations and their nested parent details (without boundary data) - this runs to 18,000 records so is possibly going to need pagination
router.register(r"organisations", viewset=OrganisationViewSet, basename="organisation")

# returns a list of trusts and their details with their nested child organisations (ods_code and name only)
router.register(
    r"trusts",
    viewset=TrustViewSet,
    basename="trust",
)
# returns a list of local health boards and their boundary details
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
# returns a list of London Boroughs and their boundary data
router.register(
    r"london_boroughs",
    viewset=LondonBoroughViewSet,
    basename="london_borough",
)
# returns a list of NHS England regions and their boundary data
router.register(
    r"nhs_england_regions",
    viewset=NHSEnglandRegionViewSet,
    basename="nhs_england_region",
)

# RCPCH networks
router.register(
    r"paediatric_diabetes_units/extended",
    viewset=PaediatricDiabetesUnitViewSet,
    basename="paediatric_diabetes_unit",
)
# returns a list of Paediatric Diabetes Units with nested child organisations
router.register(
    r"paediatric_diabetes_units/organisations",
    viewset=PaediatricDiabetesUnitWithNestedOrganisationsViewSet,
    basename="paediatric_diabetes_unit",
)
# returns a list of Paediatric Diabetes Units with nested trusts
router.register(
    r"paediatric_diabetes_units/parent",
    viewset=PaediatricDiabetesUnitForParentViewSet,
    basename="paediatric_diabetes_unit",
)

router.register(
    r"local_authority_districts",
    viewset=LocalAuthorityDistrictViewSet,
    basename="local_authority_district",
)

drf_routes = [
    # rest framework paths
    path("", include(router.urls)),
    # JSON Schema
    path(
        "paediatric_diabetes_units/sibling-organisations/<str:ods_code>/",
        PaediatricDiabetesUnitForOrganisationWithParentViewSet.as_view({"get": "list"}),
        name="paediatric_diabetes_unit_organisation_with_parent",
    ),
    path(
        "organisations/paediatric-diabetes-units",
        OrganisationsAssociatedWithPaediatricDiabetesUnitsList.as_view(),
        name="organisations-associated-with-paediatric-diabetes-units",
    ),
    path("schema/", SpectacularJSONAPIView.as_view(), name="schema"),
    # Swagger UI
    path("swagger-ui/", SpectacularSwaggerView.as_view(), name="swagger-ui"),
]

urlpatterns = []

urlpatterns += (path("admin/", admin.site.urls),)


urlpatterns += drf_routes
