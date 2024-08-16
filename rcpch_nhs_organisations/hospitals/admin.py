from django.contrib import admin

# Register your models here.
from .models import (
    LocalHealthBoard,
    Organisation,
    PaediatricDiabetesUnit,
    Trust,
)

# Register your models here.
admin.site.register(LocalHealthBoard)
admin.site.register(Organisation)
admin.site.register(PaediatricDiabetesUnit)
admin.site.register(Trust)
