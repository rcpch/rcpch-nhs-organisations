"""
rcpch_nhs_organisations URL Configuration
"""

from django.urls import path, include

urlpatterns = [
    path(
        "",
        include("rcpch_nhs_organisations.hospitals.urls"),
    ),
]
