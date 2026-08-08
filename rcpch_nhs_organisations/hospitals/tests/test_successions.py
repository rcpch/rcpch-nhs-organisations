"""
Tests for the TrustSuccession and PaediatricDiabetesUnitSuccession tables.

These tables record the *why* of a merger/acquisition/rename/closure/split:
the link between a predecessor and a successor, with a date and a type.
They are populated manually via the admin (per the design doc), so these
tests cover creation, the choice-field display, PROTECT on delete, and the
ability to walk the succession chain.
"""
import datetime

import pytest
from django.apps import apps
from django.db.models import ProtectedError

Trust = apps.get_model("hospitals", "Trust")
TrustSuccession = apps.get_model("hospitals", "TrustSuccession")
PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")
PaediatricDiabetesUnitSuccession = apps.get_model(
    "hospitals", "PaediatricDiabetesUnitSuccession"
)


@pytest.fixture
def trust_a():
    return Trust.objects.create(ods_code="RAA", name="Trust A")


@pytest.fixture
def trust_b():
    return Trust.objects.create(ods_code="RBB", name="Trust B")


@pytest.fixture
def trust_c():
    return Trust.objects.create(ods_code="RCC", name="Trust C")


@pytest.fixture
def pdu_a():
    return PaediatricDiabetesUnit.objects.create(pz_code="PZA")


@pytest.fixture
def pdu_b():
    return PaediatricDiabetesUnit.objects.create(pz_code="PZB")


@pytest.mark.django_db
def test_trust_succession_creation(trust_a, trust_b):
    succession = TrustSuccession.objects.create(
        predecessor=trust_a,
        successor=trust_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="merger",
        notes="Trust A absorbed into Trust B",
    )
    assert succession.predecessor == trust_a
    assert succession.successor == trust_b
    assert succession.get_succession_type_display() == "Merger"
    assert "RAA" in str(succession) and "RBB" in str(succession)


@pytest.mark.django_db
def test_trust_succession_protects_predecessor(trust_a, trust_b):
    TrustSuccession.objects.create(
        predecessor=trust_a,
        successor=trust_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="merger",
    )
    with pytest.raises(ProtectedError):
        trust_a.delete()


@pytest.mark.django_db
def test_trust_succession_protects_successor(trust_a, trust_b):
    TrustSuccession.objects.create(
        predecessor=trust_a,
        successor=trust_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="merger",
    )
    with pytest.raises(ProtectedError):
        trust_b.delete()


@pytest.mark.django_db
def test_trust_succession_chain_walkable(trust_a, trust_b, trust_c):
    """A trust can be both a successor (of A) and a predecessor (of C)."""
    TrustSuccession.objects.create(
        predecessor=trust_a,
        successor=trust_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="merger",
    )
    TrustSuccession.objects.create(
        predecessor=trust_b,
        successor=trust_c,
        succession_date=datetime.date(2024, 4, 1),
        succession_type="merger",
    )
    # trust_b's predecessors: successions where trust_b is the SUCCESSOR
    assert list(trust_b.succession_successor_links.values_list("predecessor__ods_code", flat=True)) == ["RAA"]
    # trust_b's successors: successions where trust_b is the PREDECESSOR
    assert list(trust_b.succession_predecessor_links.values_list("successor__ods_code", flat=True)) == ["RCC"]


@pytest.mark.django_db
def test_trust_succession_all_types(trust_a, trust_b):
    """All five succession_type choices are accepted."""
    for stype in ["merger", "acquisition", "rename", "closure", "split"]:
        TrustSuccession.objects.create(
            predecessor=trust_a,
            successor=trust_b,
            succession_date=datetime.date(2023, 4, 1),
            succession_type=stype,
        )
    assert TrustSuccession.objects.count() == 5


@pytest.mark.django_db
def test_pdu_succession_creation(pdu_a, pdu_b):
    succession = PaediatricDiabetesUnitSuccession.objects.create(
        predecessor=pdu_a,
        successor=pdu_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="merger",
        notes="PDU A merged into PDU B",
    )
    assert succession.predecessor == pdu_a
    assert succession.successor == pdu_b
    assert succession.get_succession_type_display() == "Merger"
    assert "PZA" in str(succession) and "PZB" in str(succession)


@pytest.mark.django_db
def test_pdu_succession_protects_predecessor(pdu_a, pdu_b):
    PaediatricDiabetesUnitSuccession.objects.create(
        predecessor=pdu_a,
        successor=pdu_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="merger",
    )
    with pytest.raises(ProtectedError):
        pdu_a.delete()


@pytest.mark.django_db
def test_pdu_succession_protects_successor(pdu_a, pdu_b):
    PaediatricDiabetesUnitSuccession.objects.create(
        predecessor=pdu_a,
        successor=pdu_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="merger",
    )
    with pytest.raises(ProtectedError):
        pdu_b.delete()


@pytest.mark.django_db
def test_pdu_succession_chain_walkable(pdu_a, pdu_b):
    PaediatricDiabetesUnitSuccession.objects.create(
        predecessor=pdu_a,
        successor=pdu_b,
        succession_date=datetime.date(2023, 4, 1),
        succession_type="merger",
    )
    # pdu_a's successors: successions where pdu_a is the PREDECESSOR
    assert list(pdu_a.succession_predecessor_links.values_list("successor__pz_code", flat=True)) == ["PZB"]
    # pdu_b's predecessors: successions where pdu_b is the SUCCESSOR
    assert list(pdu_b.succession_successor_links.values_list("predecessor__pz_code", flat=True)) == ["PZA"]
