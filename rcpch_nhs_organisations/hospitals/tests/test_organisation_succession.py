"""
Tests for the OrganisationSuccession table.

These mirror the TrustSuccession / PaediatricDiabetesUnitSuccession tests but
add coverage for the organisation-specific `code_change` succession type and
for the South London Healthcare (RYQ) split scenario described in
documentation/docs/developer/merger-handling.md.
"""
import datetime

import pytest
from django.apps import apps
from django.db.models import ProtectedError

Trust = apps.get_model("hospitals", "Trust")
Organisation = apps.get_model("hospitals", "Organisation")
OrganisationSuccession = apps.get_model("hospitals", "OrganisationSuccession")


@pytest.fixture
def trust_a():
    return Trust.objects.create(ods_code="RAA", name="Trust A")


@pytest.fixture
def trust_b():
    return Trust.objects.create(ods_code="RBB", name="Trust B")


@pytest.fixture
def org_a(trust_a):
    return Organisation.objects.create(
        ods_code="RAA01", name="Org A", active=True, trust=trust_a
    )


@pytest.fixture
def org_b(trust_b):
    return Organisation.objects.create(
        ods_code="RBB01", name="Org B", active=True, trust=trust_b
    )


@pytest.mark.django_db
def test_organisation_succession_creation(org_a, org_b):
    succession = OrganisationSuccession.objects.create(
        predecessor=org_a,
        successor=org_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="split",
        notes="Org A split, this part moved to Trust B",
    )
    assert succession.predecessor == org_a
    assert succession.successor == org_b
    assert succession.get_succession_type_display() == "Split"
    assert "RAA01" in str(succession) and "RBB01" in str(succession)


@pytest.mark.django_db
def test_organisation_succession_protects_predecessor(org_a, org_b):
    OrganisationSuccession.objects.create(
        predecessor=org_a,
        successor=org_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="split",
    )
    with pytest.raises(ProtectedError):
        org_a.delete()


@pytest.mark.django_db
def test_organisation_succession_protects_successor(org_a, org_b):
    OrganisationSuccession.objects.create(
        predecessor=org_a,
        successor=org_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="split",
    )
    with pytest.raises(ProtectedError):
        org_b.delete()


@pytest.mark.django_db
def test_organisation_succession_all_types(org_a, org_b):
    """All six succession_type choices are accepted, including code_change."""
    for stype in [
        "merger",
        "acquisition",
        "rename",
        "closure",
        "split",
        "code_change",
    ]:
        OrganisationSuccession.objects.create(
            predecessor=org_a,
            successor=org_b,
            succession_date=datetime.date(2023, 4, 1),
            succession_type=stype,
        )
    assert OrganisationSuccession.objects.count() == 6


@pytest.mark.django_db
def test_organisation_succession_chain_walkable(org_a, org_b):
    """An organisation can be both a successor (of A) and a predecessor (of B)."""
    OrganisationSuccession.objects.create(
        predecessor=org_a,
        successor=org_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="split",
    )
    # org_a's successors: successions where org_a is the PREDECESSOR
    assert list(
        org_a.succession_predecessor_links.values_list("successor__ods_code", flat=True)
    ) == ["RBB01"]
    # org_b's predecessors: successions where org_b is the SUCCESSOR
    assert list(
        org_b.succession_successor_links.values_list(
            "predecessor__ods_code", flat=True
        )
    ) == ["RAA01"]


@pytest.mark.django_db
def test_south_london_healthcare_split_scenario():
    """
    Worked example from documentation/docs/developer/merger-handling.md:
    South London Healthcare NHS Trust (RYQ) was dissolved in 2013 and its
    children split between King's College Hospital (RJZ) and Lewisham & Greenwich
    (RJ2). Princess Royal (RYQ30) became RJZ30; Queen Elizabeth Woolwich
    (RYQ01) became RJ201.

    This test verifies that the OrganisationSuccession rows let us walk from
    the new ODS code back to the old one, which is what audit reports need.
    """
    ryq = Trust.objects.create(ods_code="RYQ", name="South London Healthcare NHS Trust")
    rjz = Trust.objects.create(ods_code="RJZ", name="King's College Hospital NHS FT")
    rj2 = Trust.objects.create(ods_code="RJ2", name="Lewisham and Greenwich NHS Trust")

    ryq30 = Organisation.objects.create(
        ods_code="RYQ30", name="Princess Royal University Hospital", active=False, trust=ryq
    )
    ryq01 = Organisation.objects.create(
        ods_code="RYQ01", name="Queen Elizabeth Hospital Woolwich", active=False, trust=ryq
    )
    rjz30 = Organisation.objects.create(
        ods_code="RJZ30", name="Princess Royal University Hospital", active=True, trust=rjz
    )
    rj201 = Organisation.objects.create(
        ods_code="RJ201", name="Queen Elizabeth Hospital Woolwich", active=True, trust=rj2
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

    # Audit query: "What was Princess Royal University Hospital's ODS code
    # before it became RJZ30?"
    predecessor = rjz30.succession_successor_links.get().predecessor
    assert predecessor.ods_code == "RYQ30"

    # Audit query: "What was Queen Elizabeth Hospital's ODS code before it
    # became RJ201?"
    predecessor = rj201.succession_successor_links.get().predecessor
    assert predecessor.ods_code == "RYQ01"
