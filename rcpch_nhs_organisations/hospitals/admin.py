from django.contrib import admin

# Register your models here.
from .models import (
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
