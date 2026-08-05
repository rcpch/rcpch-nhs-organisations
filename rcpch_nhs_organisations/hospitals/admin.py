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
from .general_functions.membership import (
    reassign_organisation_trust,
    rename_paediatric_diabetes_unit,
    rename_trust,
    deactivate_organisation,
    deactivate_paediatric_diabetes_unit,
    deactivate_trust,
)


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
# Attribute-edit form (dynamic, built from the version model's snapshot fields)
# ---------------------------------------------------------------------------


def _build_attribute_form(version_model):
    """Build a Django Form class whose fields are the snapshot fields of the
    given version model, plus an `effective_date` field.

    The form is pre-populated from the current entity row (the denormalised
    current state). On submit, only the fields that differ from the current
    value are passed to the update helper — though passing all of them is also
    fine, since the helper snapshots unchanged fields from the entity anyway.

    `active` is intentionally excluded: deactivation is a business event with
    audit implications (the entity stops operating) and belongs to the
    merger/closure workflow, not the attribute-edit form. Use the Deactivate…
    action instead, which writes both a version row and a succession row.
    """
    from .general_functions.membership import _snapshot_fields

    excluded_fields = {"active"}
    field_dict = {}
    for field in _snapshot_fields(version_model):
        if field.name in excluded_fields:
            continue
        form_field = field.formfield()
        if form_field is not None:
            field_dict[field.name] = form_field
    field_dict["effective_date"] = forms.DateField(
        initial=timezone.now,
        label="Effective date",
        help_text="The date the attribute change takes effect.",
    )
    return type("AttributeEditForm", (forms.Form,), field_dict)


# Cache of form classes keyed by version model name, so we don't rebuild the
# form class on every request.
_attribute_form_cache = {}


def _get_attribute_form(version_model):
    key = version_model.__name__
    if key not in _attribute_form_cache:
        _attribute_form_cache[key] = _build_attribute_form(version_model)
    return _attribute_form_cache[key]


# ---------------------------------------------------------------------------
# Mixin: "Edit attributes as of…" action for any versioned entity
# ---------------------------------------------------------------------------


class AttributeEditAdminMixin:
    """Adds an "Edit attributes as of…" action to a ModelAdmin.

    The mixin introspects the entity's version model (configured via
    `version_model` and `update_helper` on the concrete admin class) and
    builds a form from its snapshot fields. On submit it calls the helper,
    which closes the current version row and opens a new one.

    Concrete admins must set:
        version_model  — the *Version model class (e.g. TrustVersion)
        update_helper  — the update_<entity>_attributes callable
    """

    version_model = None
    update_helper = None
    change_form_template = "admin/hospitals/change_form_with_edit_attributes.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/edit-attributes/",
                self.admin_site.admin_view(self.edit_attributes_view),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_edit_attributes",
            ),
        ]
        return custom_urls + urls

    def edit_attributes_view(self, request, object_id):
        from django.shortcuts import get_object_or_404

        obj = get_object_or_404(self.model, pk=object_id)
        FormClass = _get_attribute_form(self.version_model)
        opts = self.model._meta

        if request.method == "POST":
            form = FormClass(request.POST)
            if form.is_valid():
                effective_date = form.cleaned_data.pop("effective_date")
                # Only pass fields that actually changed — keeps the version
                # row's snapshot clean and the audit log meaningful.
                fields = {}
                for name, value in form.cleaned_data.items():
                    if getattr(obj, name, None) != value:
                        fields[name] = value
                if not fields:
                    self.message_user(
                        request,
                        f"No changes to {opts.verbose_name} attributes.",
                    )
                    return redirect(
                        f"admin:{opts.app_label}_{opts.model_name}_change",
                        object_id,
                    )
                self.update_helper(obj, effective_date=effective_date, **fields)
                self.message_user(
                    request,
                    f"Updated {opts.verbose_name} attributes "
                    f"(effective {effective_date}).",
                )
                return redirect(
                    f"admin:{opts.app_label}_{opts.model_name}_change",
                    object_id,
                )
        else:
            initial = {
                f.name: getattr(obj, f.name, None)
                for f in self.version_model._meta.get_fields()
                if hasattr(f, "attname")
            }
            initial["effective_date"] = timezone.now().date()
            form = FormClass(initial=initial)

        return render(
            request,
            "admin/hospitals/edit_attributes.html",
            {
                "form": form,
                "object": obj,
                "opts": opts,
            },
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["has_edit_attributes_action"] = True
        return super().changeform_view(request, object_id, form_url, extra_context)


# ---------------------------------------------------------------------------
# Mixin: "Rename…" action for entities with a succession table (Trust, PDU)
# ---------------------------------------------------------------------------


class RenameAdminMixin:
    """Adds a "Rename…" action to a ModelAdmin for an entity that has both a
    version table and a succession table.

    The rename action performs two writes in one transaction:
      1. a Layer 1 version update via the rename helper (which calls
         update_<entity>_attributes internally);
      2. a Layer 3 succession row with succession_type='rename'.

    Concrete admins must set:
        rename_helper  — the rename_<entity> callable (e.g. rename_trust)
        name_field     — the attribute on the entity that holds the name
                         (e.g. "name" for Trust, "unit_name" for PDU)
    """

    rename_helper = None
    name_field = "name"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/rename/",
                self.admin_site.admin_view(self.rename_view),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_rename",
            ),
        ]
        return custom_urls + urls

    def rename_view(self, request, object_id):
        from django.shortcuts import get_object_or_404

        obj = get_object_or_404(self.model, pk=object_id)
        opts = self.model._meta

        if request.method == "POST":
            form = RenameForm(request.POST)
            if form.is_valid():
                new_name = form.cleaned_data["new_name"]
                effective_date = form.cleaned_data["effective_date"]
                notes = form.cleaned_data.get("notes", "")
                self.rename_helper(
                    obj,
                    new_name,
                    effective_date=effective_date,
                    notes=notes,
                )
                self.message_user(
                    request,
                    f"Renamed {opts.verbose_name} to {new_name!r} "
                    f"(effective {effective_date}).",
                )
                return redirect(
                    f"admin:{opts.app_label}_{opts.model_name}_change",
                    object_id,
                )
        else:
            current_name = getattr(obj, self.name_field, "") or ""
            form = RenameForm(
                initial={
                    "new_name": current_name,
                    "effective_date": timezone.now().date(),
                }
            )

        return render(
            request,
            "admin/hospitals/rename_entity.html",
            {
                "form": form,
                "object": obj,
                "opts": opts,
            },
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["has_rename_action"] = True
        return super().changeform_view(request, object_id, form_url, extra_context)


class RenameForm(forms.Form):
    new_name = forms.CharField(
        max_length=255,
        label="New name",
        help_text="The new name for this entity.",
    )
    effective_date = forms.DateField(
        initial=timezone.now,
        label="Effective date",
        help_text="The date the rename takes effect.",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Notes",
        help_text=(
            "Optional free-text notes about the rename, recorded on the "
            "succession row."
        ),
    )


# ---------------------------------------------------------------------------
# Mixin: "Deactivate…" action (closure with no successor)
# ---------------------------------------------------------------------------


class DeactivateForm(forms.Form):
    effective_date = forms.DateField(
        initial=timezone.now,
        label="Effective date",
        help_text="The date the closure takes effect.",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Reason / notes",
        help_text=(
            "Why is this entity being closed? Recorded on the succession row "
            "so the audit trail shows the reason, not just the date."
        ),
    )
    confirm = forms.BooleanField(
        required=True,
        label="I understand this entity will be marked inactive",
        help_text=(
            "Once inactive, the entity is hidden from default lists. "
            "Reactivation requires a new version row via the attribute-edit "
            "action."
        ),
    )


class DeactivateAdminMixin:
    """Adds a "Deactivate…" action to a ModelAdmin for an entity that has both
    a version table and a succession table.

    The deactivate action performs two writes in one transaction:
      1. a Layer 1 version update with active=False via the deactivate helper;
      2. a Layer 3 succession row with succession_type='closure' and
         successor=None.

    This is the only sanctioned way to flip `active` to False. The
    attribute-edit form excludes `active` precisely so that deactivation goes
    through this action, which records *why* the entity closed.

    Concrete admins must set:
        deactivate_helper  — the deactivate_<entity> callable
    """

    deactivate_helper = None

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/deactivate/",
                self.admin_site.admin_view(self.deactivate_view),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_deactivate",
            ),
        ]
        return custom_urls + urls

    def deactivate_view(self, request, object_id):
        from django.shortcuts import get_object_or_404

        obj = get_object_or_404(self.model, pk=object_id)
        opts = self.model._meta

        if request.method == "POST":
            form = DeactivateForm(request.POST)
            if form.is_valid():
                effective_date = form.cleaned_data["effective_date"]
                notes = form.cleaned_data.get("notes", "")
                self.deactivate_helper(
                    obj,
                    effective_date=effective_date,
                    notes=notes,
                )
                self.message_user(
                    request,
                    f"Deactivated {opts.verbose_name} {obj} "
                    f"(effective {effective_date}).",
                    level="WARNING",
                )
                return redirect(
                    f"admin:{opts.app_label}_{opts.model_name}_change",
                    object_id,
                )
        else:
            form = DeactivateForm(
                initial={"effective_date": timezone.now().date()}
            )

        return render(
            request,
            "admin/hospitals/deactivate_entity.html",
            {
                "form": form,
                "object": obj,
                "opts": opts,
            },
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["has_deactivate_action"] = True
        return super().changeform_view(request, object_id, form_url, extra_context)


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


class OrganisationAdmin(AttributeEditAdminMixin, DeactivateAdminMixin, admin.ModelAdmin):
    version_model = OrganisationVersion
    from .general_functions.membership import update_organisation_attributes
    update_helper = staticmethod(update_organisation_attributes)
    deactivate_helper = staticmethod(deactivate_organisation)

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


class PaediatricDiabetesUnitAdmin(
    AttributeEditAdminMixin, RenameAdminMixin, DeactivateAdminMixin, admin.ModelAdmin
):
    version_model = PaediatricDiabetesUnitVersion
    from .general_functions.membership import update_paediatric_diabetes_unit_attributes
    update_helper = staticmethod(update_paediatric_diabetes_unit_attributes)
    rename_helper = staticmethod(rename_paediatric_diabetes_unit)
    deactivate_helper = staticmethod(deactivate_paediatric_diabetes_unit)
    name_field = "unit_name"

    list_display = ("pz_code", "paediatric_diabetes_network", "active", "updated_at")
    search_fields = ("pz_code", "paediatric_diabetes_network__name")
    list_filter = ("active",)
    ordering = ("pz_code", "-active", "-updated_at")
    list_per_page = 20
    inlines = [
        PaediatricDiabetesUnitVersionInline,
        PaediatricDiabetesUnitNetworkMembershipInline,
    ]


class TrustAdmin(AttributeEditAdminMixin, RenameAdminMixin, DeactivateAdminMixin, admin.ModelAdmin):
    version_model = TrustVersion
    from .general_functions.membership import update_trust_attributes
    update_helper = staticmethod(update_trust_attributes)
    rename_helper = staticmethod(rename_trust)
    deactivate_helper = staticmethod(deactivate_trust)
    name_field = "name"

    list_display = ("ods_code", "name", "active")
    search_fields = ("ods_code", "name")
    list_filter = ("active",)
    ordering = ("-active", "name")
    list_per_page = 20
    inlines = [
        TrustVersionInline,
        TrustIntegratedCareBoardMembershipInline,
    ]


class LocalHealthBoardAdmin(AttributeEditAdminMixin, admin.ModelAdmin):
    version_model = LocalHealthBoardVersion
    from .general_functions.membership import update_local_health_board_attributes
    update_helper = staticmethod(update_local_health_board_attributes)

    list_display = ("ods_code", "name")
    search_fields = ("ods_code", "name")
    ordering = ("name",)
    list_per_page = 20


class IntegratedCareBoardAdmin(AttributeEditAdminMixin, admin.ModelAdmin):
    version_model = IntegratedCareBoardVersion
    from .general_functions.membership import update_integrated_care_board_attributes
    update_helper = staticmethod(update_integrated_care_board_attributes)

    list_display = ("ods_code", "name")
    search_fields = ("ods_code", "name")
    ordering = ("name",)
    list_per_page = 20


class NHSEnglandRegionAdmin(AttributeEditAdminMixin, admin.ModelAdmin):
    version_model = NHSEnglandRegionVersion
    from .general_functions.membership import update_nhs_england_region_attributes
    update_helper = staticmethod(update_nhs_england_region_attributes)

    list_display = ("region_code", "name")
    search_fields = ("region_code", "name")
    ordering = ("name",)
    list_per_page = 20


class PaediatricDiabetesNetworkAdmin(AttributeEditAdminMixin, admin.ModelAdmin):
    version_model = PaediatricDiabetesNetworkVersion
    from .general_functions.membership import update_paediatric_diabetes_network_attributes
    update_helper = staticmethod(update_paediatric_diabetes_network_attributes)

    list_display = ("pn_code", "name")
    search_fields = ("pn_code", "name")
    ordering = ("pn_code",)
    list_per_page = 20


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


admin.site.register(LocalHealthBoard, LocalHealthBoardAdmin)
admin.site.register(Organisation, OrganisationAdmin)
admin.site.register(PaediatricDiabetesUnit, PaediatricDiabetesUnitAdmin)
admin.site.register(PaediatricDiabetesNetwork, PaediatricDiabetesNetworkAdmin)
admin.site.register(Trust, TrustAdmin)

admin.site.register(IntegratedCareBoard, IntegratedCareBoardAdmin)
admin.site.register(NHSEnglandRegion, NHSEnglandRegionAdmin)

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
