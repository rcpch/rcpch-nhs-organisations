from django.contrib import admin
from django import forms
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone

# Register your models here.
from .models import (
    Country,
    IntegratedCareBoard,
    IntegratedCareBoardVersion,
    LocalHealthBoard,
    LocalHealthBoardVersion,
    NHSEnglandRegion,
    NHSEnglandRegionVersion,
    Organisation,
    OrganisationIntegratedCareBoardMembership,
    OrganisationLocalHealthBoardMembership,
    OrganisationLowerLayerSuperOutputAreaMembership,
    OrganisationLondonBoroughMembership,
    OrganisationLondonBoroughMembership,
    OrganisationNHSEnglandRegionMembership,
    OrganisationOPENUKNetworkMembership,
    OrganisationPaediatricDiabetesUnitMembership,
    OrganisationSuccession,
    OrganisationTrustMembership,
    OrganisationVersion,
    PaediatricDiabetesNetwork,
    PaediatricDiabetesNetworkVersion,
    PaediatricDiabetesUnit,
    PaediatricDiabetesUnitNetworkMembership,
    PaediatricDiabetesUnitSuccession,
    PaediatricDiabetesUnitVersion,
    Trust,
    TrustIntegratedCareBoardMembership,
    TrustNHSEnglandRegionMembership,
    TrustSuccession,
    TrustVersion,
)
from .general_functions.membership import reassign_organisation_trust


# ---------------------------------------------------------------------------
# Read-only history inlines
# ---------------------------------------------------------------------------


class OrganisationVersionInline(admin.TabularInline):
    model = OrganisationVersion
    extra = 0
    can_delete = False
    fields = (
        "valid_from",
        "valid_to",
        "name",
        "address1",
        "city",
        "postcode",
        "active",
    )
    readonly_fields = fields
    ordering = ("-valid_from",)
    verbose_name = "Attribute history"
    verbose_name_plural = "Attribute history"

    def has_add_permission(self, request, obj=None):
        return False


class OrganisationTrustMembershipInline(admin.TabularInline):
    model = OrganisationTrustMembership
    extra = 0
    can_delete = False
    fields = ("trust", "valid_from", "valid_to")
    readonly_fields = ("trust", "valid_from", "valid_to")
    ordering = ("-valid_from",)
    verbose_name = "Trust membership history"
    verbose_name_plural = "Trust membership history"

    def has_add_permission(self, request, obj=None):
        return False


class OrganisationIntegratedCareBoardMembershipInline(admin.TabularInline):
    model = OrganisationIntegratedCareBoardMembership
    extra = 0
    can_delete = False
    fields = ("integrated_care_board", "valid_from", "valid_to")
    readonly_fields = ("integrated_care_board", "valid_from", "valid_to")
    ordering = ("-valid_from",)
    verbose_name = "ICB membership history"
    verbose_name_plural = "ICB membership history"

    def has_add_permission(self, request, obj=None):
        return False


class OrganisationPaediatricDiabetesUnitMembershipInline(admin.TabularInline):
    model = OrganisationPaediatricDiabetesUnitMembership
    extra = 0
    can_delete = False
    fields = ("paediatric_diabetes_unit", "valid_from", "valid_to")
    readonly_fields = ("paediatric_diabetes_unit", "valid_from", "valid_to")
    ordering = ("-valid_from",)
    verbose_name = "PDU membership history"
    verbose_name_plural = "PDU membership history"

    def has_add_permission(self, request, obj=None):
        return False


class TrustVersionInline(admin.TabularInline):
    model = TrustVersion
    extra = 0
    can_delete = False
    fields = ("valid_from", "valid_to", "name", "active")
    readonly_fields = fields
    ordering = ("-valid_from",)
    verbose_name = "Attribute history"
    verbose_name_plural = "Attribute history"

    def has_add_permission(self, request, obj=None):
        return False


class TrustIntegratedCareBoardMembershipInline(admin.TabularInline):
    model = TrustIntegratedCareBoardMembership
    extra = 0
    can_delete = False
    fields = ("integrated_care_board", "valid_from", "valid_to")
    readonly_fields = ("integrated_care_board", "valid_from", "valid_to")
    ordering = ("-valid_from",)
    verbose_name = "ICB membership history"
    verbose_name_plural = "ICB membership history"

    def has_add_permission(self, request, obj=None):
        return False


class PaediatricDiabetesUnitVersionInline(admin.TabularInline):
    model = PaediatricDiabetesUnitVersion
    extra = 0
    can_delete = False
    fields = ("valid_from", "valid_to", "active")
    readonly_fields = fields
    ordering = ("-valid_from",)
    verbose_name = "Attribute history"
    verbose_name_plural = "Attribute history"

    def has_add_permission(self, request, obj=None):
        return False


class PaediatricDiabetesUnitNetworkMembershipInline(admin.TabularInline):
    model = PaediatricDiabetesUnitNetworkMembership
    extra = 0
    can_delete = False
    fields = ("paediatric_diabetes_network", "valid_from", "valid_to")
    readonly_fields = ("paediatric_diabetes_network", "valid_from", "valid_to")
    ordering = ("-valid_from",)
    verbose_name = "Network membership history"
    verbose_name_plural = "Network membership history"

    def has_add_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# Reassign trust admin action
# ---------------------------------------------------------------------------


class ReassignTrustForm(forms.Form):
    new_trust = forms.ModelChoiceField(
        queryset=Trust.objects.all(),
        label="New trust",
        help_text="The trust the selected organisations will be reassigned to.",
    )
    effective_date = forms.DateField(
        initial=timezone.now,
        label="Effective date",
        help_text="The date the reassignment takes effect.",
    )


class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("ods_code", "name", "active")
    search_fields = ("ods_code", "name")
    list_filter = ("active",)
    ordering = ("-active", "-name")
    list_per_page = 20
    actions = ["reassign_trust"]
    inlines = [
        OrganisationVersionInline,
        OrganisationTrustMembershipInline,
        OrganisationIntegratedCareBoardMembershipInline,
        OrganisationPaediatricDiabetesUnitMembershipInline,
    ]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "reassign-trust/",
                self.admin_site.admin_view(self.reassign_trust_view),
                name="hospitals_organisation_reassign_trust",
            ),
        ]
        return custom_urls + urls

    def reassign_trust(self, request, queryset):
        """Reassign the selected organisations to a new trust, recording the
        change in OrganisationTrustMembership."""
        selected = queryset.values_list("pk", flat=True)
        from django.http import HttpResponseRedirect
        from urllib.parse import urlencode
        url = reverse("admin:hospitals_organisation_reassign_trust")
        return HttpResponseRedirect(f"{url}?{urlencode({'ids': ','.join(str(pk) for pk in selected)})}")

    reassign_trust.short_description = "Reassign to a new trust"

    def reassign_trust_view(self, request):
        if request.method == "POST":
            form = ReassignTrustForm(request.POST)
            if form.is_valid():
                new_trust = form.cleaned_data["new_trust"]
                effective_date = form.cleaned_data["effective_date"]
                ids = request.POST.get("ids", "").split(",")
                organisations = Organisation.objects.filter(pk__in=ids)
                count = 0
                for org in organisations:
                    reassign_organisation_trust(
                        org, new_trust, effective_date=effective_date
                    )
                    count += 1
                self.message_user(
                    request,
                    f"Reassigned {count} organisation(s) to {new_trust} "
                    f"(effective {effective_date}).",
                )
                return redirect("admin:hospitals_organisation_changelist")
        else:
            ids = request.GET.get("ids", "")
            form = ReassignTrustForm(initial={"ids": ids})

        return render(
            request,
            "admin/hospitals/organisation/reassign_trust.html",
            {"form": form, "ids": ids, "opts": self.model._meta},
        )


class PaediatricDiabetesUnitAdmin(admin.ModelAdmin):
    list_display = ("pz_code", "paediatric_diabetes_network", "active", "updated_at")
    search_fields = ("pz_code", "paediatric_diabetes_network__name")
    list_filter = ("active",)
    ordering = ("pz_code", "-active", "-updated_at")
    list_per_page = 20
    inlines = [
        PaediatricDiabetesUnitVersionInline,
        PaediatricDiabetesUnitNetworkMembershipInline,
    ]


class TrustAdmin(admin.ModelAdmin):
    list_display = ("ods_code", "name", "active")
    search_fields = ("ods_code", "name")
    list_filter = ("active",)
    ordering = ("-active", "name")
    list_per_page = 20
    inlines = [
        TrustVersionInline,
        TrustIntegratedCareBoardMembershipInline,
    ]


# ---------------------------------------------------------------------------
# Succession admin pages
# ---------------------------------------------------------------------------


class TrustSuccessionAdmin(admin.ModelAdmin):
    list_display = ("predecessor", "successor", "succession_date", "succession_type")
    list_filter = ("succession_type",)
    search_fields = (
        "predecessor__ods_code",
        "successor__ods_code",
        "predecessor__name",
        "successor__name",
    )
    date_hierarchy = "succession_date"
    ordering = ("-succession_date",)


class OrganisationSuccessionAdmin(admin.ModelAdmin):
    list_display = ("predecessor", "successor", "succession_date", "succession_type")
    list_filter = ("succession_type",)
    search_fields = (
        "predecessor__ods_code",
        "successor__ods_code",
        "predecessor__name",
        "successor__name",
    )
    date_hierarchy = "succession_date"
    ordering = ("-succession_date",)


class PaediatricDiabetesUnitSuccessionAdmin(admin.ModelAdmin):
    list_display = ("predecessor", "successor", "succession_date", "succession_type")
    list_filter = ("succession_type",)
    search_fields = (
        "predecessor__pz_code",
        "successor__pz_code",
    )
    date_hierarchy = "succession_date"
    ordering = ("-succession_date",)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


admin.site.register(LocalHealthBoard)
admin.site.register(Organisation, OrganisationAdmin)
admin.site.register(PaediatricDiabetesUnit, PaediatricDiabetesUnitAdmin)
admin.site.register(PaediatricDiabetesNetwork)
admin.site.register(Trust, TrustAdmin)

admin.site.register(Country)

admin.site.register(TrustSuccession, TrustSuccessionAdmin)
admin.site.register(OrganisationSuccession, OrganisationSuccessionAdmin)
admin.site.register(
    PaediatricDiabetesUnitSuccession, PaediatricDiabetesUnitSuccessionAdmin
)

admin.site.site_header = "RCPCH NHS Organisations"
admin.site.site_title = "RCPCH NHS Organisations admin"
admin.site.index_title = "RCPCH NHS Organisations"
admin.site.site_url = "/"
