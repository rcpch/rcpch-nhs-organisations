"""
rcpch_nhs_organisations URL Configuration
"""
from django.urls import path, include

urlpatterns = [
    path(
        "rcpch-nhs-organisations/api/v1/",
        include("rcpch_nhs_organisations.hospitals.urls"),
    ),
]
