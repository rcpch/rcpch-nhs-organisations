# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .paediatric_diabetes_unit import PaediatricDiabetesUnit


class PaediatricDiabetesUnitSuccession(TimeStampAbstractBaseClass):
    """
    Records the business relationship between two Paediatric Diabetes Unit
    rows when a merger, acquisition, rename, closure, or split occurs.

    The membership tables (OrganisationPaediatricDiabetesUnitMembership,
    PaediatricDiabetesUnitNetworkMembership) record *what* changed; this
    table records *why* — the link between a predecessor PDU and its
    successor, with a date and a type.

    Populated manually via the admin (per the resolved open question in the
    design doc), not automatically from the ODS Rels block, because ODS
    succession semantics are occasionally ambiguous.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    predecessor = models.ForeignKey(
        to=PaediatricDiabetesUnit,
        on_delete=models.PROTECT,
        related_name="succession_predecessor_links",
        verbose_name="Predecessor",
        help_text="The PDU that ceased to exist (or was renamed) on the succession date.",
    )
    successor = models.ForeignKey(
        to=PaediatricDiabetesUnit,
        on_delete=models.PROTECT,
        related_name="succession_successor_links",
        verbose_name="Successor",
        null=True,
        blank=True,
        default=None,
        help_text=(
            "The PDU that took over from the predecessor on the succession date. "
            "Leave blank for a closure (no successor)."
        ),
    )
    succession_date = models.DateField(
        verbose_name="Succession date",
        help_text="The date on which the succession took effect.",
    )
    succession_type = models.CharField(
        max_length=20,
        choices=[
            ("merger", "Merger"),
            ("acquisition", "Acquisition"),
            ("rename", "Rename"),
            ("closure", "Closure"),
            ("split", "Split"),
        ],
        verbose_name="Succession type",
        help_text="The nature of the succession.",
    )
    notes = models.TextField(
        blank=True,
        default="",
        verbose_name="Notes",
        help_text="Optional free-text notes about the succession.",
    )

    class Meta:
        indexes = [models.Index(fields=["succession_date"])]
        verbose_name = "Paediatric Diabetes Unit succession"
        verbose_name_plural = "Paediatric Diabetes Unit successions"

    def __str__(self) -> str:
        successor = self.successor.pz_code if self.successor else "(closed)"
        return (
            f"{self.predecessor.pz_code} → {successor} "
            f"({self.succession_date}, {self.get_succession_type_display()})"
        )
