# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .organisation import Organisation
from .paediatric_diabetes_unit import PaediatricDiabetesUnit


class OrganisationPaediatricDiabetesUnitMembership(TimeStampAbstractBaseClass):
    """
    Tracks which Paediatric Diabetes Unit an Organisation belonged to over time.

    Append-only. Each row records that the Organisation was a member of the
    PDU over [valid_from, valid_to). The current membership is the row with
    valid_to IS NULL.

    PDU affiliation can change if an organisation is reassigned to a different
    PDU, or if PDUs merge (see PaediatricDiabetesUnitSuccession).

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    organisation = models.ForeignKey(
        to=Organisation,
        on_delete=models.CASCADE,
        related_name="paediatric_diabetes_unit_memberships",
        verbose_name="Organisation",
        help_text="The Organisation this membership records the PDU of.",
    )
    paediatric_diabetes_unit = models.ForeignKey(
        to=PaediatricDiabetesUnit,
        on_delete=models.PROTECT,
        related_name="organisation_memberships",
        verbose_name="Paediatric Diabetes Unit",
        help_text="The PDU the Organisation was a member of over this interval.",
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
            models.Index(fields=["organisation", "valid_to"]),
            models.Index(fields=["paediatric_diabetes_unit", "valid_from"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Organisation–Paediatric Diabetes Unit membership"
        verbose_name_plural = "Organisation–Paediatric Diabetes Unit memberships"

    def __str__(self) -> str:
        return (
            f"{self.organisation.ods_code} → {self.paediatric_diabetes_unit.pz_code} "
            f"({self.valid_from} → {self.valid_to or 'now'})"
        )

    def is_current(self) -> bool:
        """True if this is the current (open) membership."""
        return self.valid_to is None
