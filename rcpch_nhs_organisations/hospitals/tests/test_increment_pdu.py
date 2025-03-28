import pytest


@pytest.mark.django_db
def test_increment_pdu_version():
    """
    Test that the version of a Paediatric Diabetes Unit (PDU) increments correctly when saved.
    """
    from rcpch_nhs_organisations.hospitals.models import PaediatricDiabetesUnit

    # Create a new PDU
    pdu = PaediatricDiabetesUnit(pz_code="PDU001")
    pdu.save()

    # Check that the version is 1 after the first save
    assert pdu.version == 1

    # Save the PDU again and check that the version increments
    pdu.pz_code = "PDU002"
    pdu.save()
    assert pdu.version == 2
    # Save the PDU again and check that the version increments
