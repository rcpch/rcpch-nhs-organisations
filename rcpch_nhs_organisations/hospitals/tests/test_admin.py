"""
Tests for the admin interface additions:

- the reassign trust admin action closes the old membership, opens a new one,
  and updates the denormalised FK
- the succession admin pages are registered and listable
- the history inlines are present on the Organisation, Trust, and PDU admin
  change pages
"""
import datetime

import pytest
from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import RequestFactory
from django.urls import reverse

from rcpch_nhs_organisations.hospitals.admin import (
    OrganisationAdmin,
    TrustAdmin,
    PaediatricDiabetesUnitAdmin,
    TrustSuccessionAdmin,
    OrganisationSuccessionAdmin,
    PaediatricDiabetesUnitSuccessionAdmin,
    LocalHealthBoardAdmin,
    IntegratedCareBoardAdmin,
    NHSEnglandRegionAdmin,
    PaediatricDiabetesNetworkAdmin,
)
from rcpch_nhs_organisations.hospitals.models import (
    Organisation,
    OrganisationTrustMembership,
    OrganisationVersion,
    Trust,
    TrustVersion,
    TrustSuccession,
    OrganisationSuccession,
    PaediatricDiabetesUnit,
    PaediatricDiabetesUnitSuccession,
    PaediatricDiabetesUnitVersion,
    IntegratedCareBoard,
    IntegratedCareBoardVersion,
    LocalHealthBoard,
    LocalHealthBoardVersion,
    NHSEnglandRegion,
    NHSEnglandRegionVersion,
    PaediatricDiabetesNetwork,
    PaediatricDiabetesNetworkVersion,
)

User = get_user_model()


def _square_geom(easting, northing, side=200):
    return MultiPolygon(
        Polygon(
            (
                (easting - side / 2, northing + side / 2),
                (easting - side / 2, northing - side / 2),
                (easting + side / 2, northing - side / 2),
                (easting + side / 2, northing + side / 2),
                (easting - side / 2, northing + side / 2),
            )
        )
    )


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="admin", email="admin@example.com", password="password"
    )


@pytest.fixture
def trust_a():
    return Trust.objects.create(ods_code="RAA", name="Trust A")


@pytest.fixture
def trust_b():
    return Trust.objects.create(ods_code="RBB", name="Trust B")


@pytest.fixture
def organisation(trust_a):
    return Organisation.objects.create(
        ods_code="RAA01",
        name="Test Org",
        active=True,
        trust=trust_a,
    )


@pytest.fixture
def organisation_with_baseline(organisation):
    OrganisationVersion.objects.create(
        organisation=organisation,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name=organisation.name,
        active=organisation.active,
    )
    OrganisationTrustMembership.objects.create(
        organisation=organisation,
        trust=organisation.trust,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
    )
    return organisation


# ---------------------------------------------------------------------------
# Reassign trust admin action
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_reassign_trust_action_is_registered():
    """The reassign_trust action appears in the OrganisationAdmin actions list."""
    organisation_admin = OrganisationAdmin(Organisation, AdminSite())
    assert "reassign_trust" in organisation_admin.actions


@pytest.mark.django_db
def test_reassign_trust_action_redirects_to_custom_view(
    superuser, organisation_with_baseline
):
    """Selecting the action and submitting the intermediate page redirects to
    the custom reassign-trust view."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)

    changelist_url = reverse("admin:hospitals_organisation_changelist")
    response = client.post(
        changelist_url,
        {
            "action": "reassign_trust",
            "_selected_action": [organisation_with_baseline.pk],
            "index": 0,
        },
    )
    # Django admin redirects to the custom view with the selected ids.
    assert response.status_code == 302
    assert "reassign-trust" in response.url


@pytest.mark.django_db
def test_reassign_trust_view_reassigns_on_post(
    superuser, organisation_with_baseline, trust_b
):
    """Submitting the reassign form closes the old membership and opens a new one."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)

    url = reverse("admin:hospitals_organisation_reassign_trust")
    response = client.post(
        url,
        {
            "new_trust": trust_b.pk,
            "effective_date": "2023-04-01",
            "ids": str(organisation_with_baseline.pk),
        },
    )
    assert response.status_code == 302

    organisation_with_baseline.refresh_from_db()
    assert organisation_with_baseline.trust == trust_b

    # Old membership closed, new one opened.
    old_membership = OrganisationTrustMembership.objects.get(
        organisation=organisation_with_baseline, trust__ods_code="RAA"
    )
    assert old_membership.valid_to == datetime.date(2023, 4, 1)

    new_membership = OrganisationTrustMembership.objects.get(
        organisation=organisation_with_baseline, valid_to__isnull=True
    )
    assert new_membership.trust == trust_b
    assert new_membership.valid_from == datetime.date(2023, 4, 1)


@pytest.mark.django_db
def test_reassign_trust_view_renders_form_on_get(
    superuser, organisation_with_baseline
):
    from django.test import Client

    client = Client()
    client.force_login(superuser)

    url = reverse("admin:hospitals_organisation_reassign_trust")
    response = client.get(url, {"ids": str(organisation_with_baseline.pk)})
    assert response.status_code == 200
    assert b"Reassign" in response.content


# ---------------------------------------------------------------------------
# History inlines
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_organisation_admin_has_history_inlines():
    organisation_admin = OrganisationAdmin(Organisation, AdminSite())
    inline_model_names = [inline.model.__name__ for inline in organisation_admin.inlines]
    assert "OrganisationVersion" in inline_model_names
    assert "OrganisationTrustMembership" in inline_model_names
    assert "OrganisationIntegratedCareBoardMembership" in inline_model_names
    assert "OrganisationPaediatricDiabetesUnitMembership" in inline_model_names


@pytest.mark.django_db
def test_trust_admin_has_history_inlines():
    trust_admin = TrustAdmin(Trust, AdminSite())
    inline_model_names = [inline.model.__name__ for inline in trust_admin.inlines]
    assert "TrustVersion" in inline_model_names
    assert "TrustIntegratedCareBoardMembership" in inline_model_names


@pytest.mark.django_db
def test_pdu_admin_has_history_inlines():
    pdu_admin = PaediatricDiabetesUnitAdmin(PaediatricDiabetesUnit, AdminSite())
    inline_model_names = [inline.model.__name__ for inline in pdu_admin.inlines]
    assert "PaediatricDiabetesUnitVersion" in inline_model_names
    assert "PaediatricDiabetesUnitNetworkMembership" in inline_model_names


# ---------------------------------------------------------------------------
# Succession admin pages
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_trust_succession_admin_registered():
    assert TrustSuccession in admin.site._registry
    assert isinstance(
        admin.site._registry[TrustSuccession], TrustSuccessionAdmin
    )


@pytest.mark.django_db
def test_organisation_succession_admin_registered():
    assert OrganisationSuccession in admin.site._registry
    assert isinstance(
        admin.site._registry[OrganisationSuccession], OrganisationSuccessionAdmin
    )


@pytest.mark.django_db
def test_pdu_succession_admin_registered():
    assert PaediatricDiabetesUnitSuccession in admin.site._registry
    assert isinstance(
        admin.site._registry[PaediatricDiabetesUnitSuccession],
        PaediatricDiabetesUnitSuccessionAdmin,
    )


@pytest.mark.django_db
def test_trust_succession_changelist_renders(superuser, trust_a, trust_b):
    from django.test import Client

    TrustSuccession.objects.create(
        predecessor=trust_a,
        successor=trust_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="acquisition",
    )
    client = Client()
    client.force_login(superuser)
    url = reverse("admin:hospitals_trustsuccession_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert b"Trust A" in response.content or b"RAA" in response.content


# ---------------------------------------------------------------------------
# Attribute-edit admin action (Layer 1 writes)
# ---------------------------------------------------------------------------


@pytest.fixture
def trust_with_baseline(trust_a):
    """Trust with a baseline TrustVersion row, so the attribute-edit action
    has a previous row to close."""
    TrustVersion.objects.create(
        trust=trust_a,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        name=trust_a.name,
        active=trust_a.active,
    )
    return trust_a


@pytest.fixture
def pdu_with_baseline():
    pdu = PaediatricDiabetesUnit.objects.create(pz_code="PZ999", unit_name="Old PDU")
    PaediatricDiabetesUnitVersion.objects.create(
        paediatric_diabetes_unit=pdu,
        valid_from=datetime.date(2020, 1, 1),
        valid_to=None,
        active=True,
    )
    return pdu


@pytest.mark.django_db
def test_attribute_edit_action_registered_on_trust():
    """The TrustAdmin has the attribute-edit mixin wired up."""
    trust_admin = TrustAdmin(Trust, AdminSite())
    assert trust_admin.version_model is TrustVersion
    assert trust_admin.update_helper is not None


@pytest.mark.django_db
def test_attribute_edit_view_renders_form_on_get(superuser, trust_with_baseline):
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse(
        "admin:hospitals_trust_edit_attributes",
        args=[trust_with_baseline.pk],
    )
    response = client.get(url)
    assert response.status_code == 200
    assert b"Edit" in response.content
    assert b"Effective date" in response.content


@pytest.mark.django_db
def test_attribute_edit_view_updates_on_post(superuser, trust_with_baseline):
    """Submitting the attribute-edit form closes the old version and opens a new one."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse(
        "admin:hospitals_trust_edit_attributes",
        args=[trust_with_baseline.pk],
    )
    response = client.post(
        url,
        {
            "name": "Trust A (renamed)",
            "active": "on",
            "effective_date": "2023-04-01",
        },
    )
    assert response.status_code == 302

    trust_with_baseline.refresh_from_db()
    assert trust_with_baseline.name == "Trust A (renamed)"

    # Old version closed, new one opened.
    old_version = TrustVersion.objects.get(
        trust=trust_with_baseline, name="Trust A"
    )
    assert old_version.valid_to == datetime.date(2023, 4, 1)

    new_version = TrustVersion.objects.get(
        trust=trust_with_baseline, valid_to__isnull=True
    )
    assert new_version.name == "Trust A (renamed)"
    assert new_version.valid_from == datetime.date(2023, 4, 1)

    # Single-current-version invariant holds.
    current_count = TrustVersion.objects.filter(
        trust=trust_with_baseline, valid_to__isnull=True
    ).count()
    assert current_count == 1


@pytest.mark.django_db
def test_attribute_edit_view_no_changes_is_noop(superuser, trust_with_baseline):
    """If no fields changed, the action reports no changes and writes nothing."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse(
        "admin:hospitals_trust_edit_attributes",
        args=[trust_with_baseline.pk],
    )
    # Submit with the same values that are already on the trust. The
    # `active` BooleanField must be submitted as "on" to match the current
    # value (an unchecked checkbox is absent from POST and reads as False).
    response = client.post(
        url,
        {
            "name": "Trust A",
            "active": "on",
            "effective_date": "2023-04-01",
        },
    )
    assert response.status_code == 302
    # No new version row created.
    assert TrustVersion.objects.filter(trust=trust_with_baseline).count() == 1


@pytest.mark.django_db
def test_attribute_edit_action_present_on_all_versioned_entity_admins():
    """Every versioned entity admin has the attribute-edit mixin wired up."""
    cases = [
        (OrganisationAdmin, Organisation, OrganisationVersion),
        (TrustAdmin, Trust, TrustVersion),
        (PaediatricDiabetesUnitAdmin, PaediatricDiabetesUnit, PaediatricDiabetesUnitVersion),
        (LocalHealthBoardAdmin, LocalHealthBoard, LocalHealthBoardVersion),
        (IntegratedCareBoardAdmin, IntegratedCareBoard, IntegratedCareBoardVersion),
        (NHSEnglandRegionAdmin, NHSEnglandRegion, NHSEnglandRegionVersion),
        (PaediatricDiabetesNetworkAdmin, PaediatricDiabetesNetwork, PaediatricDiabetesNetworkVersion),
    ]
    for admin_cls, model, version_model in cases:
        admin_instance = admin_cls(model, AdminSite())
        assert admin_instance.version_model is version_model, (
            f"{admin_cls.__name__} missing version_model"
        )
        assert admin_instance.update_helper is not None, (
            f"{admin_cls.__name__} missing update_helper"
        )


# ---------------------------------------------------------------------------
# Rename admin action (composite Layer 1 + Layer 3 write)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_rename_action_registered_on_trust():
    """The TrustAdmin has the rename mixin wired up."""
    trust_admin = TrustAdmin(Trust, AdminSite())
    assert trust_admin.rename_helper is not None
    assert trust_admin.name_field == "name"


@pytest.mark.django_db
def test_rename_action_registered_on_pdu():
    """The PDUAdmin has the rename mixin wired up."""
    pdu_admin = PaediatricDiabetesUnitAdmin(PaediatricDiabetesUnit, AdminSite())
    assert pdu_admin.rename_helper is not None
    assert pdu_admin.name_field == "unit_name"


@pytest.mark.django_db
def test_rename_view_renders_form_on_get(superuser, trust_with_baseline):
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse("admin:hospitals_trust_rename", args=[trust_with_baseline.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert b"Rename" in response.content
    assert b"New name" in response.content


@pytest.mark.django_db
def test_rename_view_writes_version_and_succession_on_post(
    superuser, trust_with_baseline
):
    """Submitting the rename form writes both a TrustVersion row and a
    TrustSuccession row with succession_type='rename'."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse("admin:hospitals_trust_rename", args=[trust_with_baseline.pk])
    response = client.post(
        url,
        {
            "new_name": "Trust A (renamed)",
            "effective_date": "2023-04-01",
            "notes": "NHS England rename",
        },
    )
    assert response.status_code == 302

    trust_with_baseline.refresh_from_db()
    assert trust_with_baseline.name == "Trust A (renamed)"

    # Layer 1: version row written.
    new_version = TrustVersion.objects.get(
        trust=trust_with_baseline, valid_to__isnull=True
    )
    assert new_version.name == "Trust A (renamed)"
    assert new_version.valid_from == datetime.date(2023, 4, 1)

    # Layer 3: succession row written, predecessor == successor == same trust.
    succession = TrustSuccession.objects.get(succession_date=datetime.date(2023, 4, 1))
    assert succession.predecessor_id == trust_with_baseline.pk
    assert succession.successor_id == trust_with_baseline.pk
    assert succession.succession_type == "rename"
    assert succession.notes == "NHS England rename"

    # Membership tables untouched.
    assert OrganisationTrustMembership.objects.filter(trust=trust_with_baseline).count() == 0


@pytest.mark.django_db
def test_rename_pdu_view_writes_version_and_succession_on_post(
    superuser, pdu_with_baseline
):
    """The PDU rename action writes both a PaediatricDiabetesUnitVersion row
    and a PaediatricDiabetesUnitSuccession row."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse("admin:hospitals_paediatricdiabetesunit_rename", args=[pdu_with_baseline.pk])
    response = client.post(
        url,
        {
            "new_name": "New PDU Name",
            "effective_date": "2023-04-01",
            "notes": "",
        },
    )
    assert response.status_code == 302

    pdu_with_baseline.refresh_from_db()
    assert pdu_with_baseline.unit_name == "New PDU Name"

    # Layer 1: version row written.
    new_version = PaediatricDiabetesUnitVersion.objects.get(
        paediatric_diabetes_unit=pdu_with_baseline, valid_to__isnull=True
    )
    assert new_version.unit_name == "New PDU Name"
    assert new_version.valid_from == datetime.date(2023, 4, 1)

    # Layer 3: succession row written.
    succession = PaediatricDiabetesUnitSuccession.objects.get(
        succession_date=datetime.date(2023, 4, 1)
    )
    assert succession.predecessor_id == pdu_with_baseline.pk
    assert succession.successor_id == pdu_with_baseline.pk
    assert succession.succession_type == "rename"


@pytest.mark.django_db
def test_rename_change_form_has_rename_button(superuser, trust_with_baseline):
    """The trust change page renders the Rename button."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse("admin:hospitals_trust_change", args=[trust_with_baseline.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert b"Rename" in response.content
    assert b"Edit attributes" in response.content


# ---------------------------------------------------------------------------
# Deactivate admin action (closure with no successor)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deactivate_action_registered_on_trust():
    """The TrustAdmin has the deactivate mixin wired up."""
    trust_admin = TrustAdmin(Trust, AdminSite())
    assert trust_admin.deactivate_helper is not None


@pytest.mark.django_db
def test_deactivate_action_registered_on_organisation():
    """The OrganisationAdmin has the deactivate mixin wired up."""
    organisation_admin = OrganisationAdmin(Organisation, AdminSite())
    assert organisation_admin.deactivate_helper is not None


@pytest.mark.django_db
def test_deactivate_action_registered_on_pdu():
    """The PDUAdmin has the deactivate mixin wired up."""
    pdu_admin = PaediatricDiabetesUnitAdmin(PaediatricDiabetesUnit, AdminSite())
    assert pdu_admin.deactivate_helper is not None


@pytest.mark.django_db
def test_deactivate_view_renders_form_on_get(superuser, trust_with_baseline):
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse("admin:hospitals_trust_deactivate", args=[trust_with_baseline.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert b"Deactivate" in response.content
    assert b"closure" in response.content
    # The confirmation checkbox is required.
    assert b"confirm" in response.content


@pytest.mark.django_db
def test_deactivate_view_writes_version_and_closure_succession_on_post(
    superuser, trust_with_baseline
):
    """Submitting the deactivate form writes a version row with active=False
    and a TrustSuccession row with succession_type='closure' and successor=None."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse("admin:hospitals_trust_deactivate", args=[trust_with_baseline.pk])
    response = client.post(
        url,
        {
            "effective_date": "2023-04-01",
            "notes": "Closed due to poor quality of care",
            "confirm": "on",
        },
    )
    assert response.status_code == 302

    trust_with_baseline.refresh_from_db()
    assert trust_with_baseline.active is False

    # Layer 1: version row written with active=False.
    new_version = TrustVersion.objects.get(
        trust=trust_with_baseline, valid_to__isnull=True
    )
    assert new_version.active is False
    assert new_version.valid_from == datetime.date(2023, 4, 1)

    # Layer 3: closure succession row written, successor is None.
    succession = TrustSuccession.objects.get(succession_date=datetime.date(2023, 4, 1))
    assert succession.predecessor_id == trust_with_baseline.pk
    assert succession.successor_id is None
    assert succession.succession_type == "closure"
    assert succession.notes == "Closed due to poor quality of care"


@pytest.mark.django_db
def test_deactivate_view_requires_confirmation(superuser, trust_with_baseline):
    """Submitting without the confirmation checkbox does not deactivate."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse("admin:hospitals_trust_deactivate", args=[trust_with_baseline.pk])
    response = client.post(
        url,
        {
            "effective_date": "2023-04-01",
            "notes": "",
            # confirm deliberately omitted
        },
    )
    # Form invalid — re-renders the page rather than redirecting.
    assert response.status_code == 200
    trust_with_baseline.refresh_from_db()
    assert trust_with_baseline.active is True
    assert TrustSuccession.objects.count() == 0


@pytest.mark.django_db
def test_deactivate_change_form_has_deactivate_button(superuser, trust_with_baseline):
    """The trust change page renders the Deactivate button (in red)."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse("admin:hospitals_trust_change", args=[trust_with_baseline.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert b"Deactivate" in response.content


@pytest.mark.django_db
def test_attribute_edit_form_excludes_active(superuser, trust_with_baseline):
    """The attribute-edit form must not include the `active` field —
    deactivation goes through the Deactivate… action, not the attribute form."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse(
        "admin:hospitals_trust_edit_attributes",
        args=[trust_with_baseline.pk],
    )
    response = client.get(url)
    assert response.status_code == 200
    # The form should not have an `active` field.
    assert b'name="active"' not in response.content


# ---------------------------------------------------------------------------
# Signposting banner on the change form
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_trust_change_form_has_signposting_banner(superuser, trust_with_baseline):
    """The trust change page shows the signposting banner directing users to
    the rename / edit-attributes / deactivate actions rather than editing the
    form directly. The merger-workflow note is NOT shown for trusts (it is
    organisation-specific)."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse("admin:hospitals_trust_change", args=[trust_with_baseline.pk])
    response = client.get(url)
    assert response.status_code == 200
    # The banner is present.
    assert b"Before editing this record directly" in response.content
    # Rename guidance (Trust has the rename action).
    assert b"Changing the name?" in response.content
    assert b"Rename" in response.content
    # Edit-attributes guidance.
    assert b"Changing an attribute from a specific date?" in response.content
    assert b"Edit attributes as of" in response.content
    # Deactivate guidance (Trust has the deactivate action).
    assert b"Closing this" in response.content
    assert b"Deactivate" in response.content
    # The "not date-dependent" guidance.
    assert b"not date-dependent" in response.content
    # Merger workflow note absent (Trust is not an organisation).
    assert b"merger work flow" not in response.content


@pytest.mark.django_db
def test_organisation_change_form_has_signposting_banner(
    superuser, organisation_with_baseline
):
    """The organisation change page shows the signposting banner. Organisation
    has the edit-attributes and deactivate actions but NOT the rename action
    (no rename succession table for organisations). It also shows the merger
    workflow note directing users to the Trust/LHB tab for merger-driven
    deactivations."""
    from django.test import Client

    client = Client()
    client.force_login(superuser)
    url = reverse(
        "admin:hospitals_organisation_change", args=[organisation_with_baseline.pk]
    )
    response = client.get(url)
    assert response.status_code == 200
    assert b"Before editing this record directly" in response.content
    # Edit-attributes guidance present.
    assert b"Changing an attribute from a specific date?" in response.content
    # Deactivate guidance present (Organisation has the deactivate action).
    assert b"Closing this" in response.content
    # Rename guidance absent (Organisation has no rename action).
    assert b"Changing the name?" not in response.content
    # Merger workflow note present (Organisation only).
    assert b"merger work flow" in response.content
    assert b"Trust/Local Health Board tab" in response.content


@pytest.mark.django_db
def test_icb_change_form_has_signposting_banner(superuser):
    """The ICB change page shows the signposting banner with edit-attributes
    guidance only — ICB has no rename or deactivate action."""
    from django.test import Client

    icb = IntegratedCareBoard.objects.create(
        boundary_identifier="E10000099",
        name="Test ICB",
        bng_e=400000,
        bng_n=400000,
        long=-1.0,
        lat=53.0,
        globalid="guid-icb-test",
        geom=_square_geom(400000, 400000),
        ods_code="A99",
    )
    client = Client()
    client.force_login(superuser)
    url = reverse("admin:hospitals_integratedcareboard_change", args=[icb.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert b"Before editing this record directly" in response.content
    # Edit-attributes guidance present.
    assert b"Changing an attribute from a specific date?" in response.content
    # Rename guidance absent.
    assert b"Changing the name?" not in response.content
    # Deactivate guidance absent.
    assert b"Closing this" not in response.content
