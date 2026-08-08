# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .integrated_care_board import IntegratedCareBoard


class IntegratedCareBoardSuccession(TimeStampAbstractBaseClass):
    """
    Records the business relationship between two IntegratedCareBoard rows when
    a merger, acquisition, rename, closure, or split occurs.

    The membership tables (OrganisationIntegratedCareBoardMembership, etc.)
    record *what* changed; this table records *why* — the link between a
    predecessor Integrated Care Board and its successor, with a date and a type.

    Populated manually via the admin (per the resolved open question in the
    design doc), not automatically from the ODS Rels block, because ODS
    succession semantics are occasionally ambiguous.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    predecessor = models.ForeignKey(
        to=IntegratedCareBoard,
        on_delete=models.PROTECT,
        related_name="succession_predecessor_links",
        verbose_name="Predecessor",
        help_text="The Integrated Care Board that ceased to exist (or was renamed) on the succession date.",
    )
    successor = models.ForeignKey(
        to=IntegratedCareBoard,
        on_delete=models.PROTECT,
        related_name="succession_successor_links",
        verbose_name="Successor",
        null=True,
        blank=True,
        default=None,
        help_text=(
            "The Integrated Care Board that took over from the predecessor on the succession date. "
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
        verbose_name = "Integrated Care Board succession"
        verbose_name_plural = "Integrated Care Board successions"

    def __str__(self) -> str:
        successor = self.successor.ods_code if self.successor else "(closed)"
        return (
            f"{self.predecessor.ods_code} → {successor} "
            f"({self.succession_date}, {self.get_succession_type_display()})"
        )
