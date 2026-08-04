# python imports

# django imports
from django.contrib.gis.db import models
from django.db.models import CharField

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .paediatric_diabetes_network import PaediatricDiabetesNetwork


class PaediatricDiabetesNetworkVersion(TimeStampAbstractBaseClass):
    """
    Append-only snapshot of a PaediatricDiabetesNetwork's mutable attributes over time.

    Each row represents a state of the PaediatricDiabetesNetwork valid over
    [valid_from, valid_to). The current state is the row with valid_to IS NULL.
    The immutable identifier (pn_code) lives on the PaediatricDiabetesNetwork itself.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    paediatric_diabetes_network = models.ForeignKey(
        to=PaediatricDiabetesNetwork,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="Paediatric Diabetes Network",
        help_text="The Paediatric Diabetes Network this version is a snapshot of.",
    )
    valid_from = models.DateField(
        verbose_name="Valid from",
        help_text="The date from which this state of the network was in force.",
    )
    valid_to = models.DateField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Valid to",
        help_text=(
            "The date on which this state ceased to be in force. "
            "NULL means this is the current state."
        ),
    )

    # Snapshot of mutable attributes. The pn_code is the immutable identifier
    # and lives on the PaediatricDiabetesNetwork itself.
    name = CharField(max_length=255, null=True, blank=True, default=None)

    class Meta:
        indexes = [
            models.Index(fields=["paediatric_diabetes_network", "valid_from"]),
            models.Index(fields=["valid_to"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Paediatric Diabetes Network version"
        verbose_name_plural = "Paediatric Diabetes Network versions"

    def __str__(self) -> str:
        return f"{self.paediatric_diabetes_network.pn_code} ({self.valid_from} → {self.valid_to or 'now'})"

    def is_current(self) -> bool:
        """True if this is the current (open) version of the network."""
        return self.valid_to is None
