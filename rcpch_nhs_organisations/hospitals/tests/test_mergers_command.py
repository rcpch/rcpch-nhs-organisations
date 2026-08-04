"""
Tests for the refactored mergers management command.

Covers:
- --dry-run flag is accepted and passed through to create/delete
- organisation creation creates baseline temporal rows (version + memberships)
- the command rejects --create and --delete together
- the command rejects no organisations

The ODS Spine lookup is mocked so the tests are offline.
"""
import datetime
from io import StringIO
from unittest.mock import patch

import pytest
from django.apps import apps
from django.core.management import call_command
from django.contrib.gis.geos import Point

Organisation = apps.get_model("hospitals", "Organisation")
OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")
OrganisationTrustMembership = apps.get_model(
    "hospitals", "OrganisationTrustMembership"
)
OrganisationIntegratedCareBoardMembership = apps.get_model(
    "hospitals", "OrganisationIntegratedCareBoardMembership"
)
Trust = apps.get_model("hospitals", "Trust")
IntegratedCareBoard = apps.get_model("hospitals", "IntegratedCareBoard")


@pytest.fixture
def trust():
    return Trust.objects.create(ods_code="RAA", name="Test Trust")


@pytest.fixture
def icb():
    from django.contrib.gis.geos import MultiPolygon, Polygon

    return IntegratedCareBoard.objects.create(
        boundary_identifier="E10000001",
        name="Test ICB",
        bng_e=400000,
        bng_n=400000,
        long=-1.0,
        lat=53.0,
        globalid="guid",
        geom=MultiPolygon(
            Polygon(
                (
                    (399900, 400100),
                    (399900, 399900),
                    (400100, 399900),
                    (400100, 400100),
                    (399900, 400100),
                )
            )
        ),
        ods_code="A01",
    )


@pytest.fixture
def sibling_organisation(trust, icb):
    """A sibling organisation under the same trust, so create_organisations
    can inherit ICB / region / etc. from it (the existing lookup pattern)."""
    return Organisation.objects.create(
        ods_code="RAA00",
        name="Sibling Hospital",
        active=True,
        trust=trust,
        integrated_care_board=icb,
    )


# A fake Spine record for a new organisation under trust RAA.
SPINE_RESULT = {
    "OrgId": {"extension": "RAA01"},
    "Name": "New Hospital",
    "Status": "Active",
    "GeoLoc": {
        "Location": {
            "AddrLn1": "1 Hospital St",
            "Town": "Hospitaltown",
            "County": "Hospitalshire",
            "PostCode": "HS1 1AA",
        }
    },
    "Rels": {
        "Rel": [
            {
                "Target": {
                    "OrgId": {"extension": "RAA"},
                }
            }
        ]
    },
    "Date": [{"Start": "2023-01-01"}],
}


def _patch_spine(monkeypatch, spine_result=None):
    """Patch the Spine lookup and postcode lookup used by create_organisations.

    The imports in create_organisations.py pull these names from the
    general_functions package, so we patch them there. Also patches input()
    to auto-confirm the OPENUK / PDU prompts.
    """
    import rcpch_nhs_organisations.hospitals.general_functions as gf
    import builtins
    monkeypatch.setattr(
        gf,
        "fetch_organisation_by_ods_code",
        lambda ods_code: spine_result or SPINE_RESULT,
    )
    monkeypatch.setattr(
        gf,
        "fetch_by_postcode",
        lambda postcode: {"longitude": -1.0, "latitude": 53.0},
    )
    monkeypatch.setattr(builtins, "input", lambda *args, **kwargs: "y")


@pytest.mark.django_db
def test_dry_run_flag_accepted_for_create(monkeypatch, trust, icb, sibling_organisation):
    _patch_spine(monkeypatch)
    out = StringIO()
    # Should not raise, and should not create the organisation.
    call_command(
        "mergers",
        "--organisations",
        "RAA01",
        "--create",
        "--dry-run",
        stdout=out,
        stderr=StringIO(),
    )
    assert "Dry run" in out.getvalue()
    assert not Organisation.objects.filter(ods_code="RAA01").exists()


@pytest.mark.django_db
def test_create_creates_baseline_temporal_rows(
    monkeypatch, trust, icb, sibling_organisation
):
    """Creating an organisation also creates baseline version and membership rows."""
    _patch_spine(monkeypatch)
    call_command(
        "mergers",
        "--organisations",
        "RAA01",
        "--create",
        stdout=StringIO(),
        stderr=StringIO(),
    )

    org = Organisation.objects.get(ods_code="RAA01")
    # Baseline version row.
    version = OrganisationVersion.objects.get(organisation=org, valid_to__isnull=True)
    assert version.name == "New Hospital"
    assert version.address1 == "1 Hospital St"

    # Baseline trust membership.
    trust_membership = OrganisationTrustMembership.objects.get(
        organisation=org, valid_to__isnull=True
    )
    assert trust_membership.trust == trust

    # Baseline ICB membership (inherited from the sibling).
    icb_membership = OrganisationIntegratedCareBoardMembership.objects.get(
        organisation=org, valid_to__isnull=True
    )
    assert icb_membership.integrated_care_board == icb


@pytest.mark.django_db
def test_create_and_delete_rejected_together(monkeypatch):
    out = StringIO()
    call_command(
        "mergers",
        "--organisations",
        "RAA01",
        "--create",
        "--delete",
        stdout=out,
        stderr=StringIO(),
    )
    assert "Cannot use both" in out.getvalue()


@pytest.mark.django_db
def test_no_create_or_delete_rejected(monkeypatch):
    out = StringIO()
    call_command(
        "mergers",
        "--organisations",
        "RAA01",
        stdout=out,
        stderr=StringIO(),
    )
    assert "Must provide either --create or --delete" in out.getvalue()


@pytest.mark.django_db
def test_no_organisations_rejected(monkeypatch):
    out = StringIO()
    call_command(
        "mergers",
        "--create",
        stdout=out,
        stderr=StringIO(),
    )
    assert "requires one or more organisations" in out.getvalue()
