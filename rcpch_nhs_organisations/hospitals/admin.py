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
    backfill_organisation_attributes,
    backfill_trust_attributes,
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
    verbose_name_plural = (
        "Attribute history (record of changes to this organisation's "
        "attributes — name, address, telephone, website, active flag, etc.)"
    )

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
    verbose_name_plural = (
        "Attribute history (record of changes to this trust's attributes — "
        "name, address, telephone, website, active flag, etc.)"
    )

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
    verbose_name_plural = (
        "Attribute history (record of changes to this PDU's attributes — "
        "name, active flag, etc.)"
    )

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
# Read-only succession-history inlines
# ---------------------------------------------------------------------------
#
# The *Version inlines above record *what* changed about an entity's
# attributes (name, address, telephone, website, active flag, …). They do
# NOT record mergers, acquisitions, renames, splits, or closures — those live
# in the *Succession tables. To make the link visible without leaving the
# entity's change page, each versioned entity admin gets two read-only
# inlines, one per direction:
#
#   - "Predecessors" — rows where this entity is the *successor* (the trusts
#     that merged to form it). Shown for an active trust formed by a merger.
#   - "Successor" — rows where this entity is the *predecessor* (what it
#     became). Shown for a closed/merged trust.
#
# Each inline follows a single FK (`fk_name`), so Django's built-in queryset
# filtering does the work and no custom `Q`-union is needed. Empty sections
# are hidden by `get_inline_instances` on the concrete admin classes, so an
# active trust doesn't see an empty "Successor" header.


class _PredecessorsInlineBase(admin.TabularInline):
    """Read-only inline showing the predecessors of this entity — i.e. the
    *Succession rows where this entity is the successor (the entities that
    merged to form it).

    Concrete subclasses must set `model` to the *Succession model class.
    """

    extra = 0
    can_delete = False
    fk_name = "successor"
    fields = ("predecessor", "succession_date", "succession_type", "notes")
    readonly_fields = fields
    ordering = ("-succession_date",)
    verbose_name = "Predecessor"
    verbose_name_plural = "Predecessors (the entities that merged to form this one)"

    def has_add_permission(self, request, obj=None):
        return False


class _SuccessorInlineBase(admin.TabularInline):
    """Read-only inline showing the successor of this entity — i.e. the
    *Succession rows where this entity is the predecessor (what it became
    on closure / merger / acquisition).

    Concrete subclasses must set `model` to the *Succession model class.
    """

    extra = 0
    can_delete = False
    fk_name = "predecessor"
    fields = ("successor", "succession_date", "succession_type", "notes")
    readonly_fields = fields
    ordering = ("-succession_date",)
    verbose_name = "Successor"
    verbose_name_plural = "Successor (what this entity became on closure / merger)"

    def has_add_permission(self, request, obj=None):
        return False


class TrustPredecessorsInline(_PredecessorsInlineBase):
    model = TrustSuccession


class TrustSuccessorInline(_SuccessorInlineBase):
    model = TrustSuccession


class OrganisationPredecessorsInline(_PredecessorsInlineBase):
    model = OrganisationSuccession


class OrganisationSuccessorInline(_SuccessorInlineBase):
    model = OrganisationSuccession


class PaediatricDiabetesUnitPredecessorsInline(_PredecessorsInlineBase):
    model = PaediatricDiabetesUnitSuccession


class PaediatricDiabetesUnitSuccessorInline(_SuccessorInlineBase):
    model = PaediatricDiabetesUnitSuccession


class HideEmptySuccessionInlinesMixin:
    """Hides the Predecessors / Successor inlines when they have no rows for
    the entity being viewed.

    An active trust formed by a merger has predecessors but no successor, so
    showing an empty "Successor" section would be noise. This mixin filters
    the inline list to only those that have at least one row for the parent
    object. It only inspects inlines that subclass `_PredecessorsInlineBase`
    or `_SuccessorInlineBase`; all other inlines (version history, membership
    history) are always shown.
    """

    def get_inline_instances(self, request, obj=None):
        instances = super().get_inline_instances(request, obj)
        if obj is None:
            return instances
        shown = []
        for inline in instances:
            if isinstance(inline, (_PredecessorsInlineBase, _SuccessorInlineBase)):
                # Django's inline `get_queryset` does not filter by the parent
                # object until the formset is built, so filter explicitly here
                # using the inline's `fk_name` ("successor" for the Predecessors
                # inline, "predecessor" for the Successor inline).
                if not inline.model.objects.filter(
                    **{inline.fk_name: obj}
                ).exists():
                    continue
            shown.append(inline)
        return shown


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
        widget=forms.DateInput(attrs={"type": "date"}),
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
        widget=forms.DateInput(attrs={"type": "date"}),
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
        widget=forms.DateInput(attrs={"type": "date"}),
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
# Mixin: "Backfill attributes…" action (historical state, two dates)
# ---------------------------------------------------------------------------


def _build_backfill_attribute_form(version_model):
    """Build a Django Form class for backfilling a historical state.

    Unlike the attribute-edit form (which has one effective_date and snapshots
    the current entity row), the backfill form has valid_from and valid_to and
    lets the operator enter explicit historical values. The `active` field is
    included here (unlike the attribute-edit form) because a backfill may need
    to record that an entity was active in the past.
    """
    from .general_functions.membership import _snapshot_fields

    field_dict = {}
    for field in _snapshot_fields(version_model):
        form_field = field.formfield()
        if form_field is not None:
            field_dict[field.name] = form_field
    field_dict["valid_from"] = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Valid from",
        help_text="The date this historical state began.",
    )
    field_dict["valid_to"] = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Valid to",
        help_text=(
            "The date this historical state ended (the date of the next "
            "change). Leave blank if this is the current state."
        ),
    )
    return type("BackfillAttributeForm", (forms.Form,), field_dict)


_backfill_attribute_form_cache = {}


def _get_backfill_attribute_form(version_model):
    key = version_model.__name__
    if key not in _backfill_attribute_form_cache:
        _backfill_attribute_form_cache[key] = _build_backfill_attribute_form(version_model)
    return _backfill_attribute_form_cache[key]


class BackfillAttributesAdminMixin:
    """Adds a "Backfill attributes…" action to a ModelAdmin.

    This is for recording a historical state that was overwritten before the
    temporal layer was installed — e.g. a trust's pre-merger name, or an
    organisation's old address. Unlike the attribute-edit action (which is
    forward-looking and snapshots the current entity row), the backfill action
    lets the operator enter explicit historical values with a
    [valid_from, valid_to) interval.

    Concrete admins must set:
        version_model      — the *Version model class (e.g. TrustVersion)
        backfill_helper    — the backfill_<entity>_attributes callable
    """

    version_model = None
    backfill_helper = None

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/backfill-attributes/",
                self.admin_site.admin_view(self.backfill_attributes_view),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_backfill_attributes",
            ),
        ]
        return custom_urls + urls

    def backfill_attributes_view(self, request, object_id):
        from django.shortcuts import get_object_or_404

        obj = get_object_or_404(self.model, pk=object_id)
        FormClass = _get_backfill_attribute_form(self.version_model)
        opts = self.model._meta

        if request.method == "POST":
            form = FormClass(request.POST)
            if form.is_valid():
                valid_from = form.cleaned_data.pop("valid_from")
                valid_to = form.cleaned_data.pop("valid_to")
                # Only pass fields that have a value.
                fields = {
                    k: v for k, v in form.cleaned_data.items() if v is not None
                }
                self.backfill_helper(
                    obj, valid_from=valid_from, valid_to=valid_to, **fields
                )
                self.message_user(
                    request,
                    f"Backfilled {opts.verbose_name} attributes "
                    f"({valid_from} → {valid_to or 'now'}).",
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
            form = FormClass(initial=initial)

        return render(
            request,
            "admin/hospitals/backfill_attributes.html",
            {
                "form": form,
                "object": obj,
                "opts": opts,
            },
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["has_backfill_attributes_action"] = True
        return super().changeform_view(request, object_id, form_url, extra_context)


# ---------------------------------------------------------------------------
# Mixin: "Backfill trust membership…" action (Organisation only)
# ---------------------------------------------------------------------------


class BackfillTrustMembershipForm(forms.Form):
    trust = forms.ModelChoiceField(
        queryset=Trust.objects.all(),
        label="Trust",
        help_text="The trust the organisation was affiliated to during this period.",
    )
    valid_from = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Valid from",
        help_text="The date the affiliation began.",
    )
    valid_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Valid to",
        help_text=(
            "The date the affiliation ended (the date of the reassignment). "
            "Leave blank if this is the current affiliation."
        ),
    )


class BackfillTrustMembershipAdminMixin:
    """Adds a "Backfill trust membership…" action to the Organisation admin.

    This is for recording a historical trust affiliation that was overwritten
    before the temporal layer was installed — e.g. an organisation that was
    in Pennine Acute (RW6) before it moved to Northern Care Alliance (RM3)
    on 2021-10-01.
    """

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/backfill-trust-membership/",
                self.admin_site.admin_view(self.backfill_trust_membership_view),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_backfill_trust_membership",
            ),
        ]
        return custom_urls + urls

    def backfill_trust_membership_view(self, request, object_id):
        from django.shortcuts import get_object_or_404
        from .general_functions.membership import backfill_organisation_trust_membership

        obj = get_object_or_404(self.model, pk=object_id)
        opts = self.model._meta

        if request.method == "POST":
            form = BackfillTrustMembershipForm(request.POST)
            if form.is_valid():
                trust = form.cleaned_data["trust"]
                valid_from = form.cleaned_data["valid_from"]
                valid_to = form.cleaned_data["valid_to"]
                backfill_organisation_trust_membership(
                    obj, trust=trust, valid_from=valid_from, valid_to=valid_to
                )
                self.message_user(
                    request,
                    f"Backfilled trust membership: {obj} → {trust} "
                    f"({valid_from} → {valid_to or 'now'}).",
                )
                return redirect(
                    f"admin:{opts.app_label}_{opts.model_name}_change",
                    object_id,
                )
        else:
            form = BackfillTrustMembershipForm()

        return render(
            request,
            "admin/hospitals/backfill_trust_membership.html",
            {
                "form": form,
                "object": obj,
                "opts": opts,
            },
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["has_backfill_trust_membership_action"] = True
        return super().changeform_view(request, object_id, form_url, extra_context)


# ---------------------------------------------------------------------------
# Mixin: "Backfill merger…" wizard (Trust only)
# ---------------------------------------------------------------------------


class BackfillMergerForm(forms.Form):
    predecessor_ods_code = forms.CharField(
        max_length=10,
        label="Predecessor ODS code",
        help_text=(
            "The ODS code of the trust that was absorbed / closed / renamed. "
            "This trust may or may not be in the database."
        ),
    )
    predecessor_name = forms.CharField(
        max_length=100,
        label="Predecessor name",
        help_text=(
            "The predecessor's name at the time of the merger. If the "
            "predecessor is in the database, this will be backfilled as a "
            "historical version row. If not, it will be used to create the "
            "predecessor row."
        ),
    )
    predecessor_established_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Predecessor established date",
        help_text=(
            "The date the predecessor was established (for backfilling its "
            "historical name). Leave blank if unknown — the name backfill "
            "will be skipped."
        ),
    )
    successor = forms.ModelChoiceField(
        queryset=Trust.objects.all(),
        label="Successor",
        help_text="The trust that took over from the predecessor.",
    )
    succession_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Succession date",
        help_text="The date the merger / acquisition / split took effect.",
    )
    succession_type = forms.ChoiceField(
        choices=[
            ("merger", "Merger"),
            ("acquisition", "Acquisition"),
            ("split", "Split"),
            ("closure", "Closure"),
            ("rename", "Rename"),
        ],
        initial="merger",
        label="Succession type",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Notes",
        help_text="Optional free-text notes about the merger.",
    )


class BackfillMergerAdminMixin:
    """Adds a "Backfill merger…" wizard to the Trust admin.

    This is for recording a historical merger, acquisition, or split that
    happened before the temporal layer was installed. It performs the
    following writes in one transaction:

    1. Creates the predecessor Trust row if it does not already exist (with
       active=False and a baseline version row).
    2. If the predecessor exists, backfills its historical name (if provided)
       and its closure (active=False from the succession date).
    3. Creates a TrustSuccession row linking predecessor → successor.

    It does NOT backfill child organisation memberships — the operator must
    record those separately using the "Backfill trust membership…" action on
    each organisation. A banner in the UI reminds the operator of this.

    The "Validate ODS code" button fetches the predecessor's ODS record to
    pre-fill the name and confirm the code exists. This is informational —
    the operator is the source of truth for the historical name.
    """

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/backfill-merger/",
                self.admin_site.admin_view(self.backfill_merger_view),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_backfill_merger",
            ),
        ]
        return custom_urls + urls

    def backfill_merger_view(self, request, object_id):
        import datetime
        from django.shortcuts import get_object_or_404
        from django.db import transaction
        from .general_functions.membership import backfill_trust_attributes
        from .general_functions.ods_update import get_organisation

        obj = get_object_or_404(self.model, pk=object_id)
        opts = self.model._meta
        ods_validation = None

        if request.method == "POST":
            form = BackfillMergerForm(request.POST)
            if form.is_valid():
                # "Fetch from ODS" button: fetch the predecessor's full ODS
                # record and pre-fill the form fields (name, established
                # date, succession date, successor). Do not perform the
                # backfill.
                if "fetch_ods" in request.POST:
                    pred_code = form.cleaned_data["predecessor_ods_code"]
                    try:
                        ord_record = get_organisation(
                            f"https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations/{pred_code}"
                        )
                        ods_name = ord_record.get("Name", "")
                        # Extract the legal start date (when the predecessor
                        # was established) and legal end date (when it was
                        # dissolved).
                        legal_start = None
                        legal_end = None
                        for d in ord_record.get("Date", []):
                            if d.get("Type") == "Legal":
                                legal_start = d.get("Start")
                                legal_end = d.get("End")
                                break
                        # Extract the succession date from the Succs block —
                        # the first Successor event's Legal.Start.
                        succ_date_str = None
                        successor_code = None
                        for succ in ord_record.get("Succs", {}).get("Succ", []):
                            if succ.get("Type") == "Successor":
                                for d in succ.get("Date", []):
                                    if d.get("Type") == "Legal":
                                        succ_date_str = d.get("Start")
                                        break
                                successor_code = succ.get("Target", {}).get("OrgId", {}).get("extension")
                                break
                        # Try to match the successor ODS code to a Trust in
                        # our database.
                        successor_obj = None
                        if successor_code:
                            successor_obj = Trust.objects.filter(ods_code=successor_code).first()
                        # Build the pre-filled form.
                        initial = dict(form.cleaned_data)
                        initial["predecessor_name"] = ods_name
                        if legal_start:
                            initial["predecessor_established_date"] = legal_start
                        if succ_date_str:
                            initial["succession_date"] = succ_date_str
                        if successor_obj:
                            initial["successor"] = successor_obj
                        form = BackfillMergerForm(initial=initial)
                        ods_validation = {
                            "status": "found",
                            "ods_code": pred_code,
                            "message": (
                                f"Fetched from ODS: {ods_name}. "
                                f"Legal dates: {legal_start or 'unknown'} → {legal_end or 'unknown'}."
                                + (f" Successor: {successor_code}." if successor_code else "")
                                + (
                                    f" Successor matched in database: {successor_obj}." if successor_obj else ""
                                )
                                + "\nWARNING: the name shown is the ODS current name, "
                                "which may differ from the name at the time of the "
                                "merger. Verify before backfilling."
                            ),
                        }
                    except Exception as e:
                        ods_validation = {
                            "status": "not-found",
                            "ods_code": pred_code,
                            "message": (
                                "Not found in ODS, or the ODS API returned an "
                                "error. You can still proceed — enter the "
                                "historical name and dates manually."
                            ),
                        }
                elif "backfill" in request.POST:
                    # Perform the backfill.
                    pred_code = form.cleaned_data["predecessor_ods_code"]
                    pred_name = form.cleaned_data["predecessor_name"]
                    pred_established = form.cleaned_data.get("predecessor_established_date")
                    successor = form.cleaned_data["successor"]
                    succ_date = form.cleaned_data["succession_date"]
                    succ_type = form.cleaned_data["succession_type"]
                    notes = form.cleaned_data.get("notes", "")

                    predecessor = Trust.objects.filter(ods_code=pred_code).first()

                    with transaction.atomic():
                        if predecessor is None:
                            # Create the predecessor trust row.
                            predecessor = Trust.objects.create(
                                ods_code=pred_code,
                                name=pred_name,
                                active=False,
                            )
                            # If we know when the predecessor was established,
                            # create a historical name version row too.
                            if pred_established:
                                TrustVersion.objects.create(
                                    trust=predecessor,
                                    valid_from=pred_established,
                                    valid_to=succ_date,
                                    name=pred_name,
                                    active=True,
                                )
                            # Closure version row: inactive from the
                            # succession date forward.
                            TrustVersion.objects.create(
                                trust=predecessor,
                                valid_from=succ_date,
                                valid_to=None,
                                name=pred_name,
                                active=False,
                            )
                        else:
                            # Predecessor exists — backfill the historical
                            # name (if we know when it was established) and
                            # the closure.
                            if pred_established:
                                backfill_trust_attributes(
                                    predecessor,
                                    valid_from=pred_established,
                                    valid_to=succ_date,
                                    name=pred_name,
                                    active=True,
                                )
                            # Backfill the closure (inactive from the
                            # succession date forward).
                            backfill_trust_attributes(
                                predecessor,
                                valid_from=succ_date,
                                valid_to=None,
                                active=False,
                            )
                            predecessor.active = False
                            predecessor.save(update_fields=["active"])

                        # Create the succession row.
                        TrustSuccession.objects.create(
                            predecessor=predecessor,
                            successor=successor,
                            succession_date=succ_date,
                            succession_type=succ_type,
                            notes=notes,
                        )

                    self.message_user(
                        request,
                        f"Backfilled merger: {predecessor} → {successor} "
                        f"({succ_type}, {succ_date}). Remember to backfill "
                        f"child organisation memberships separately.",
                        level="WARNING",
                    )
                    return redirect(
                        f"admin:{opts.app_label}_{opts.model_name}_change",
                        object_id,
                    )
        else:
            # Default the successor to the current trust.
            form = BackfillMergerForm(initial={"successor": obj.pk})

        return render(
            request,
            "admin/hospitals/backfill_merger.html",
            {
                "form": form,
                "object": obj,
                "opts": opts,
                "ods_validation": ods_validation,
            },
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["has_backfill_merger_action"] = True
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
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Effective date",
        help_text="The date the reassignment takes effect.",
    )


class OrganisationAdmin(HideEmptySuccessionInlinesMixin, AttributeEditAdminMixin, DeactivateAdminMixin, BackfillAttributesAdminMixin, BackfillTrustMembershipAdminMixin, admin.ModelAdmin):
    version_model = OrganisationVersion
    from .general_functions.membership import update_organisation_attributes
    update_helper = staticmethod(update_organisation_attributes)
    deactivate_helper = staticmethod(deactivate_organisation)
    backfill_helper = staticmethod(backfill_organisation_attributes)

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
        OrganisationPredecessorsInline,
        OrganisationSuccessorInline,
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
    HideEmptySuccessionInlinesMixin,
    AttributeEditAdminMixin,
    RenameAdminMixin,
    DeactivateAdminMixin,
    admin.ModelAdmin,
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
        PaediatricDiabetesUnitPredecessorsInline,
        PaediatricDiabetesUnitSuccessorInline,
    ]


class TrustAdmin(HideEmptySuccessionInlinesMixin, AttributeEditAdminMixin, RenameAdminMixin, DeactivateAdminMixin, BackfillAttributesAdminMixin, BackfillMergerAdminMixin, admin.ModelAdmin):
    version_model = TrustVersion
    from .general_functions.membership import update_trust_attributes
    update_helper = staticmethod(update_trust_attributes)
    rename_helper = staticmethod(rename_trust)
    deactivate_helper = staticmethod(deactivate_trust)
    backfill_helper = staticmethod(backfill_trust_attributes)
    name_field = "name"

    list_display = ("ods_code", "name", "active")
    search_fields = ("ods_code", "name")
    list_filter = ("active",)
    ordering = ("-active", "name")
    list_per_page = 20
    inlines = [
        TrustVersionInline,
        TrustIntegratedCareBoardMembershipInline,
        TrustPredecessorsInline,
        TrustSuccessorInline,
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
