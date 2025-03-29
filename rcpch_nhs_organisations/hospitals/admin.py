from django.contrib import admin

# Register your models here.
from .models import (
    Country,
    LocalHealthBoard,
    Organisation,
    PaediatricDiabetesNetwork,
    PaediatricDiabetesUnit,
    Trust,
)


class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("ods_code", "name", "active")
    search_fields = ("ods_code", "name")
    list_filter = ("active",)
    ordering = ("-active", "-name")
    list_per_page = 20


class PaediatricDiabetesUnitAdmin(admin.ModelAdmin):
    list_display = ("pz_code", "paediatric_diabetes_network", "active", "updated_at")
    search_fields = ("pz_code", "paediatric_diabetes_network__name")
    list_filter = ("active",)
    ordering = ("pz_code", "-active", "-updated_at")
    list_per_page = 20


admin.site.register(LocalHealthBoard)
admin.site.register(Organisation, OrganisationAdmin)
admin.site.register(PaediatricDiabetesUnit, PaediatricDiabetesUnitAdmin)
admin.site.register(PaediatricDiabetesNetwork)
admin.site.register(Trust)

admin.site.register(Country)

admin.site.site_header = "RCPCH NHS Organisations"
admin.site.site_title = "RCPCH NHS Organisations admin"
admin.site.index_title = "RCPCH NHS Organisations"
admin.site.site_url = "/"
