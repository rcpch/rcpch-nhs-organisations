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
    IntegratedCareBoard,
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
