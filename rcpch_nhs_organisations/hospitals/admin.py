from django.contrib import admin

# Register your models here.
from .models_folder import (
    LocalHealthBoard,
    Organisation,
    PaediatricDiabetesNetwork,
    PaediatricDiabetesUnit,
    Trust,
)

# Register your models here.
admin.site.register(LocalHealthBoard)
admin.site.register(Organisation)
admin.site.register(PaediatricDiabetesUnit)
admin.site.register(PaediatricDiabetesNetwork)
admin.site.register(Trust)

admin.site.site_header = "RCPCH NHS Organisations"
admin.site.site_title = "RCPCH NHS Organisations admin"
admin.site.index_title = "RCPCH NHS Organisations"
admin.site.site_url = "/"
