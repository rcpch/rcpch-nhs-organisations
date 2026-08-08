# python imports

# django imports
from django.contrib.gis.db import models
from django.db.models import CharField, BooleanField, DateField, ForeignKey

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .paediatric_diabetes_unit import PaediatricDiabetesUnit


class PaediatricDiabetesUnitVersion(TimeStampAbstractBaseClass):
    """
    Append-only snapshot of a PaediatricDiabetesUnit's mutable attributes over time.

    Each row represents a state of the PaediatricDiabetesUnit valid over
    [valid_from, valid_to). The current state is the row with valid_to IS NULL.
    The immutable identifier (pz_code) lives on the PaediatricDiabetesUnit itself.

    The paediatric_diabetes_network FK is snapshotted here as an id reference
    because the network relationship itself is versioned separately in
    PaediatricDiabetesUnitNetworkMembership (see design doc). The id stored
    here is the network that was in force at valid_from.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    paediatric_diabetes_unit = ForeignKey(
        to=PaediatricDiabetesUnit,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="Paediatric Diabetes Unit",
        help_text="The Paediatric Diabetes Unit this version is a snapshot of.",
    )
    valid_from = DateField(
        verbose_name="Valid from",
        help_text="The date from which this state of the PDU was in force.",
    )
    valid_to = DateField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Valid to",
        help_text=(
            "The date on which this state ceased to be in force. "
            "NULL means this is the current state."
        ),
    )

    # Snapshot of mutable attributes. The pz_code is the immutable identifier
    # and lives on the PaediatricDiabetesUnit itself.
    unit_name = CharField(max_length=255, null=True, blank=True, default=None)
    active = BooleanField(default=True)
    # Snapshot of name_source at this point in time. See PaediatricDiabetesUnit.
    name_source = CharField(
        max_length=30,
        choices=PaediatricDiabetesUnit.NAME_SOURCE_CHOICES,
        default=PaediatricDiabetesUnit.NAME_SOURCE_LEAD_ORGANISATION,
        verbose_name="Name source (snapshot)",
        help_text=(
            "How the PDU's display name was derived at valid_from. See "
            "PaediatricDiabetesUnit.name_source."
        ),
    )
    # Snapshot of the lead organisation FK at this point in time. The
    # relationship itself is versioned via the denormalised FK on
    # PaediatricDiabetesUnit; this field is a convenience for as-of queries
    # that only need the lead org id.
    lead_organisation = ForeignKey(
        to="hospitals.Organisation",
        on_delete=models.SET_NULL,
        related_name="pdu_versions_as_lead",
        null=True,
        blank=True,
        default=None,
        verbose_name="Lead organisation (snapshot)",
        help_text=(
            "The lead organisation for this PDU at valid_from. See "
            "PaediatricDiabetesUnit.lead_organisation."
        ),
    )
    # Snapshot of the network FK id at this point in time. The relationship
    # itself is versioned in PaediatricDiabetesUnitNetworkMembership; this
    # field is a convenience for as-of queries that only need the network id.
    paediatric_diabetes_network_id = ForeignKey(
        to="PaediatricDiabetesNetwork",
        on_delete=models.PROTECT,
        related_name="pdu_versions",
        null=True,
        blank=True,
        default=None,
        verbose_name="Paediatric Diabetes Network (snapshot)",
        help_text=(
            "The network the PDU was associated with at valid_from. "
            "For full relationship history use PaediatricDiabetesUnitNetworkMembership."
        ),
    )

    class Meta:
        indexes = [
            models.Index(fields=["paediatric_diabetes_unit", "valid_from"]),
            models.Index(fields=["valid_to"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Paediatric Diabetes Unit version"
        verbose_name_plural = "Paediatric Diabetes Unit versions"

    def __str__(self) -> str:
        return f"{self.paediatric_diabetes_unit.pz_code} ({self.valid_from} → {self.valid_to or 'now'})"

    def is_current(self) -> bool:
        """True if this is the current (open) version of the Paediatric Diabetes Unit."""
        return self.valid_to is None
