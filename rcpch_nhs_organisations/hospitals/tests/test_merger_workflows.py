"""
Integration tests for the full merger workflows described in
documentation/docs/developer/merger-handling.md.

These exercise the temporal layer end-to-end through the helper functions,
covering:

1. Trust acquisition (Barnet / Royal Free: RVL -> RAL, 2014)
2. Full merger (Ipswich + Colchester -> RJL, 2018)
3. Dissolution with split (South London Healthcare: RYQ -> RJZ + RJ2,
   with organisation succession RYQ30 -> RJZ30)
4. PDU merger (PZ216 + PZ125 -> PZ253, January 2026)

Each test verifies that the audit query (as-of snapshot) returns the correct
parent at a date before and after the merger.
"""
import datetime

import pytest
from django.apps import apps

from rcpch_nhs_organisations.hospitals.general_functions.membership import (
    reassign_organisation_trust,
    reassign_organisation_paediatric_diabetes_unit,
    update_trust_attributes,
)
from rcpch_nhs_organisations.hospitals.views.snapshot import organisation_snapshot

Organisation = apps.get_model("hospitals", "Organisation")
OrganisationVersion = apps.get_model("hospitals", "OrganisationVersion")
OrganisationTrustMembership = apps.get_model(
    "hospitals", "OrganisationTrustMembership"
)
OrganisationPaediatricDiabetesUnitMembership = apps.get_model(
    "hospitals", "OrganisationPaediatricDiabetesUnitMembership"
)
OrganisationSuccession = apps.get_model("hospitals", "OrganisationSuccession")
Trust = apps.get_model("hospitals", "Trust")
TrustVersion = apps.get_model("hospitals", "TrustVersion")
TrustSuccession = apps.get_model("hospitals", "TrustSuccession")
PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")
PaediatricDiabetesUnitVersion = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitVersion"
)
PaediatricDiabetesUnitSuccession = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitSuccession"
)


def _baseline_org_version(org, valid_from):
    OrganisationVersion.objects.create(
        organisation=org,
        valid_from=valid_from,
        valid_to=None,
        name=org.name,
        address1=org.address1,
        city=org.city,
        postcode=org.postcode,
        active=org.active,
    )


def _baseline_trust_version(trust, valid_from):
    TrustVersion.objects.create(
        trust=trust,
        valid_from=valid_from,
        valid_to=None,
        name=trust.name,
        active=trust.active,
    )


def _baseline_trust_membership(org, trust, valid_from):
    OrganisationTrustMembership.objects.create(
        organisation=org,
        trust=trust,
        valid_from=valid_from,
        valid_to=None,
    )


def _baseline_pdu_version(pdu, valid_from):
    PaediatricDiabetesUnitVersion.objects.create(
        paediatric_diabetes_unit=pdu,
        valid_from=valid_from,
        valid_to=None,
        active=pdu.active,
    )


def _baseline_pdu_membership(org, pdu, valid_from):
    OrganisationPaediatricDiabetesUnitMembership.objects.create(
        organisation=org,
        paediatric_diabetes_unit=pdu,
        valid_from=valid_from,
        valid_to=None,
    )


# ---------------------------------------------------------------------------
# 1. Acquisition: RVL -> RAL (Barnet / Royal Free, 2014)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_trust_acquisition_workflow():
    rvl = Trust.objects.create(
        ods_code="RVL",
        name="Barnet & Chase Farm Hospitals NHS Trust",
        active=True,
    )
    ral = Trust.objects.create(
        ods_code="RAL",
        name="Royal Free London NHS Foundation Trust",
        active=True,
    )
    barnet = Organisation.objects.create(
        ods_code="RVL01",
        name="Barnet Hospital",
        active=True,
        trust=rvl,
    )
    _baseline_trust_version(rvl, datetime.date(2010, 1, 1))
    _baseline_trust_version(ral, datetime.date(2010, 1, 1))
    _baseline_org_version(barnet, datetime.date(2010, 1, 1))
    _baseline_trust_membership(barnet, rvl, datetime.date(2010, 1, 1))

    # The acquisition: RVL is dissolved, Barnet moves to RAL on 2014-04-01.
    update_trust_attributes(
        rvl, effective_date=datetime.date(2014, 4, 1), active=False
    )
    reassign_organisation_trust(
        barnet, ral, effective_date=datetime.date(2014, 4, 1)
    )
    TrustSuccession.objects.create(
        predecessor=rvl,
        successor=ral,
        succession_date=datetime.date(2014, 4, 1),
        succession_type="acquisition",
    )

    # Audit query before the merger: Barnet was under RVL.
    snapshot_2013 = organisation_snapshot(barnet, datetime.date(2013, 6, 1))
    assert snapshot_2013["trust"]["ods_code"] == "RVL"

    # Audit query after the merger: Barnet is under RAL.
    snapshot_2015 = organisation_snapshot(barnet, datetime.date(2015, 6, 1))
    assert snapshot_2015["trust"]["ods_code"] == "RAL"


# ---------------------------------------------------------------------------
# 2. Full merger: RGQ + RDE -> RJL (Ipswich + Colchester, 2018)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_full_merger_workflow():
    rgq = Trust.objects.create(
        ods_code="RGQ",
        name="Ipswich Hospital NHS Trust",
        active=True,
    )
    rde = Trust.objects.create(
        ods_code="RDE",
        name="Colchester University Hospitals NHS Foundation Trust",
        active=True,
    )
    rjl = Trust.objects.create(
        ods_code="RJL",
        name="East Suffolk and North Essex NHS Foundation Trust",
        active=True,
    )
    ipswich_hospital = Organisation.objects.create(
        ods_code="RGQ01",
        name="Ipswich Hospital",
        active=True,
        trust=rgq,
    )
    colchester_hospital = Organisation.objects.create(
        ods_code="RDE01",
        name="Colchester Hospital",
        active=True,
        trust=rde,
    )
    for trust in (rgq, rde, rjl):
        _baseline_trust_version(trust, datetime.date(2010, 1, 1))
    _baseline_org_version(ipswich_hospital, datetime.date(2010, 1, 1))
    _baseline_org_version(colchester_hospital, datetime.date(2010, 1, 1))
    _baseline_trust_membership(ipswich_hospital, rgq, datetime.date(2010, 1, 1))
    _baseline_trust_membership(colchester_hospital, rde, datetime.date(2010, 1, 1))

    # The merger: both predecessors dissolved, children move to RJL on 2018-07-01.
    for predecessor in (rgq, rde):
        update_trust_attributes(
            predecessor, effective_date=datetime.date(2018, 7, 1), active=False
        )
        TrustSuccession.objects.create(
            predecessor=predecessor,
            successor=rjl,
            succession_date=datetime.date(2018, 7, 1),
            succession_type="merger",
        )
    reassign_organisation_trust(
        ipswich_hospital, rjl, effective_date=datetime.date(2018, 7, 1)
    )
    reassign_organisation_trust(
        colchester_hospital, rjl, effective_date=datetime.date(2018, 7, 1)
    )

    # Audit queries before the merger.
    assert organisation_snapshot(ipswich_hospital, datetime.date(2017, 6, 1))["trust"]["ods_code"] == "RGQ"
    assert organisation_snapshot(colchester_hospital, datetime.date(2017, 6, 1))["trust"]["ods_code"] == "RDE"

    # Audit queries after the merger.
    assert organisation_snapshot(ipswich_hospital, datetime.date(2019, 6, 1))["trust"]["ods_code"] == "RJL"
    assert organisation_snapshot(colchester_hospital, datetime.date(2019, 6, 1))["trust"]["ods_code"] == "RJL"


# ---------------------------------------------------------------------------
# 3. Dissolution with split: RYQ -> RJZ + RJ2 (South London Healthcare, 2013)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dissolution_with_split_workflow():
    ryq = Trust.objects.create(
        ods_code="RYQ",
        name="South London Healthcare NHS Trust",
        active=True,
    )
    rjz = Trust.objects.create(
        ods_code="RJZ",
        name="King's College Hospital NHS Foundation Trust",
        active=True,
    )
    rj2 = Trust.objects.create(
        ods_code="RJ2",
        name="Lewisham and Greenwich NHS Trust",
        active=True,
    )
    # Predecessor organisations (old ODS codes).
    ryq30 = Organisation.objects.create(
        ods_code="RYQ30",
        name="Princess Royal University Hospital",
        address1="Old Address",
        active=True,
        trust=ryq,
    )
    ryq01 = Organisation.objects.create(
        ods_code="RYQ01",
        name="Queen Elizabeth Hospital Woolwich",
        address1="Old Address",
        active=True,
        trust=ryq,
    )
    # Successor organisations (new ODS codes).
    rjz30 = Organisation.objects.create(
        ods_code="RJZ30",
        name="Princess Royal University Hospital",
        address1="New Address",
        active=True,
        trust=rjz,
    )
    rj201 = Organisation.objects.create(
        ods_code="RJ201",
        name="Queen Elizabeth Hospital Woolwich",
        address1="New Address",
        active=True,
        trust=rj2,
    )
    for trust in (ryq, rjz, rj2):
        _baseline_trust_version(trust, datetime.date(2010, 1, 1))
    # Predecessor orgs existed from 2010; successor orgs from the merger date.
    _baseline_org_version(ryq30, datetime.date(2010, 1, 1))
    _baseline_org_version(ryq01, datetime.date(2010, 1, 1))
    _baseline_org_version(rjz30, datetime.date(2013, 1, 1))
    _baseline_org_version(rj201, datetime.date(2013, 1, 1))
    _baseline_trust_membership(ryq30, ryq, datetime.date(2010, 1, 1))
    _baseline_trust_membership(ryq01, ryq, datetime.date(2010, 1, 1))
    _baseline_trust_membership(rjz30, rjz, datetime.date(2013, 1, 1))
    _baseline_trust_membership(rj201, rj2, datetime.date(2013, 1, 1))

    # The dissolution: RYQ dissolved, children split on 2013-01-01.
    update_trust_attributes(
        ryq, effective_date=datetime.date(2013, 1, 1), active=False
    )
    # Close the old org versions and mark inactive.
    from rcpch_nhs_organisations.hospitals.general_functions.membership import (
        update_organisation_attributes,
    )
    update_organisation_attributes(
        ryq30, effective_date=datetime.date(2013, 1, 1), active=False
    )
    update_organisation_attributes(
        ryq01, effective_date=datetime.date(2013, 1, 1), active=False
    )
    # Record the successions.
    TrustSuccession.objects.create(
        predecessor=ryq,
        successor=rjz,
        succession_date=datetime.date(2013, 1, 1),
        succession_type="split",
    )
    TrustSuccession.objects.create(
        predecessor=ryq,
        successor=rj2,
        succession_date=datetime.date(2013, 1, 1),
        succession_type="split",
    )
    OrganisationSuccession.objects.create(
        predecessor=ryq30,
        successor=rjz30,
        succession_date=datetime.date(2013, 1, 1),
        succession_type="split",
    )
    OrganisationSuccession.objects.create(
        predecessor=ryq01,
        successor=rj201,
        succession_date=datetime.date(2013, 1, 1),
        succession_type="split",
    )

    # Audit query: query the successor (RJZ30) at a date before it existed.
    # The snapshot should walk the succession chain to the predecessor (RYQ30)
    # and return RYQ as the trust.
    snapshot_2012 = organisation_snapshot(rjz30, datetime.date(2012, 6, 1))
    assert snapshot_2012["ods_code"] == "RYQ30"
    assert snapshot_2012["predecessor_ods_code"] == "RYQ30"
    assert snapshot_2012["trust"]["ods_code"] == "RYQ"

    # Audit query: query the successor (RJZ30) after the merger.
    snapshot_2014 = organisation_snapshot(rjz30, datetime.date(2014, 6, 1))
    assert snapshot_2014["ods_code"] == "RJZ30"
    assert snapshot_2014["predecessor_ods_code"] is None
    assert snapshot_2014["trust"]["ods_code"] == "RJZ"

    # Same for Queen Elizabeth Woolwich.
    snapshot_2012_qe = organisation_snapshot(rj201, datetime.date(2012, 6, 1))
    assert snapshot_2012_qe["ods_code"] == "RYQ01"
    assert snapshot_2012_qe["trust"]["ods_code"] == "RYQ"

    snapshot_2014_qe = organisation_snapshot(rj201, datetime.date(2014, 6, 1))
    assert snapshot_2014_qe["trust"]["ods_code"] == "RJ2"


# ---------------------------------------------------------------------------
# 4. PDU merger: PZ216 + PZ125 -> PZ253 (January 2026)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pdu_merger_workflow():
    pz216 = PaediatricDiabetesUnit.objects.create(pz_code="PZ216", active=True)
    pz125 = PaediatricDiabetesUnit.objects.create(pz_code="PZ125", active=True)
    pz253 = PaediatricDiabetesUnit.objects.create(pz_code="PZ253", active=True)

    # Child organisations under the predecessor PDUs.
    tunbridge_wells = Organisation.objects.create(
        ods_code="RWFTW",
        name="Tunbridge Wells Hospital",
        active=True,
    )
    maidstone = Organisation.objects.create(
        ods_code="RWF03",
        name="Maidstone Hospital",
        active=True,
    )
    _baseline_pdu_version(pz216, datetime.date(2020, 1, 1))
    _baseline_pdu_version(pz125, datetime.date(2020, 1, 1))
    _baseline_pdu_version(pz253, datetime.date(2026, 1, 1))
    _baseline_pdu_membership(tunbridge_wells, pz216, datetime.date(2020, 1, 1))
    _baseline_pdu_membership(maidstone, pz125, datetime.date(2020, 1, 1))

    # The merger: PZ216 and PZ125 dissolved, children move to PZ253 on 2026-01-01.
    from rcpch_nhs_organisations.hospitals.general_functions.membership import (
        update_paediatric_diabetes_unit_attributes,
    )
    update_paediatric_diabetes_unit_attributes(
        pz216, effective_date=datetime.date(2026, 1, 1), active=False
    )
    update_paediatric_diabetes_unit_attributes(
        pz125, effective_date=datetime.date(2026, 1, 1), active=False
    )
    PaediatricDiabetesUnitSuccession.objects.create(
        predecessor=pz216,
        successor=pz253,
        succession_date=datetime.date(2026, 1, 1),
        succession_type="merger",
    )
    PaediatricDiabetesUnitSuccession.objects.create(
        predecessor=pz125,
        successor=pz253,
        succession_date=datetime.date(2026, 1, 1),
        succession_type="merger",
    )
    reassign_organisation_paediatric_diabetes_unit(
        tunbridge_wells, pz253, effective_date=datetime.date(2026, 1, 1)
    )
    reassign_organisation_paediatric_diabetes_unit(
        maidstone, pz253, effective_date=datetime.date(2026, 1, 1)
    )

    # Audit query before the merger: Tunbridge Wells was under PZ216.
    membership_before = OrganisationPaediatricDiabetesUnitMembership.objects.filter(
        organisation=tunbridge_wells,
        valid_from__lte=datetime.date(2025, 6, 1),
    ).filter(
        valid_to__gt=datetime.date(2025, 6, 1),
    ).get()
    assert membership_before.paediatric_diabetes_unit.pz_code == "PZ216"

    # Audit query after the merger: Tunbridge Wells is under PZ253.
    membership_after = OrganisationPaediatricDiabetesUnitMembership.objects.filter(
        organisation=tunbridge_wells,
        valid_from__lte=datetime.date(2026, 6, 1),
    ).filter(
        valid_to__isnull=True,
    ).get()
    assert membership_after.paediatric_diabetes_unit.pz_code == "PZ253"

    # Same for Maidstone.
    membership_maidstone_before = OrganisationPaediatricDiabetesUnitMembership.objects.filter(
        organisation=maidstone,
        valid_from__lte=datetime.date(2025, 6, 1),
    ).filter(
        valid_to__gt=datetime.date(2025, 6, 1),
    ).get()
    assert membership_maidstone_before.paediatric_diabetes_unit.pz_code == "PZ125"

    membership_maidstone_after = OrganisationPaediatricDiabetesUnitMembership.objects.filter(
        organisation=maidstone,
        valid_from__lte=datetime.date(2026, 6, 1),
    ).filter(
        valid_to__isnull=True,
    ).get()
    assert membership_maidstone_after.paediatric_diabetes_unit.pz_code == "PZ253"
