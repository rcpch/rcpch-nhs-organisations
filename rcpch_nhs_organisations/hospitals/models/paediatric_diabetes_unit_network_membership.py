# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .paediatric_diabetes_unit import PaediatricDiabetesUnit
from .paediatric_diabetes_network import PaediatricDiabetesNetwork


class PaediatricDiabetesUnitNetworkMembership(TimeStampAbstractBaseClass):
    """
    Tracks which Paediatric Diabetes Network a PDU belonged to over time.

    Append-only. Each row records that the PDU was a member of the network
    over [valid_from, valid_to). The current membership is the row with
    valid_to IS NULL.

    A PDU can be reassigned to a different network, or can be unaffiliated
    (RCPCH has a PZ code but no PN code). This membership table records the
    full history of those changes.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    paediatric_diabetes_unit = models.ForeignKey(
        to=PaediatricDiabetesUnit,
        on_delete=models.CASCADE,
        related_name="network_memberships",
        verbose_name="Paediatric Diabetes Unit",
        help_text="The PDU this membership records the network of.",
    )
    paediatric_diabetes_network = models.ForeignKey(
        to=PaediatricDiabetesNetwork,
        on_delete=models.PROTECT,
        related_name="pdu_memberships",
        verbose_name="Paediatric Diabetes Network",
        help_text="The network the PDU was a member of over this interval.",
    )
    valid_from = models.DateField(
        verbose_name="Valid from",
        help_text="The date from which this membership was in force.",
    )
    valid_to = models.DateField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Valid to",
        help_text=(
            "The date on which this membership ceased to be in force. "
            "NULL means this is the current membership."
        ),
    )

    class Meta:
        indexes = [
            models.Index(fields=["paediatric_diabetes_unit", "valid_to"]),
            models.Index(fields=["paediatric_diabetes_network", "valid_from"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Paediatric Diabetes Unit–Network membership"
        verbose_name_plural = "Paediatric Diabetes Unit–Network memberships"

    def __str__(self) -> str:
        return (
            f"{self.paediatric_diabetes_unit.pz_code} → "
            f"{self.paediatric_diabetes_network.pn_code} "
            f"({self.valid_from} → {self.valid_to or 'now'})"
        )

    def is_current(self) -> bool:
        """True if this is the current (open) membership."""
        return self.valid_to is None
