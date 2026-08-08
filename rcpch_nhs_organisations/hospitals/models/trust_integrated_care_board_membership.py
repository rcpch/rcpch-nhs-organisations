# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .trust import Trust
from .integrated_care_board import IntegratedCareBoard


class TrustIntegratedCareBoardMembership(TimeStampAbstractBaseClass):
    """
    Tracks which Integrated Care Board a Trust belonged to over time.

    Append-only. Each row records that the Trust was a member of the ICB
    over [valid_from, valid_to). The current membership is the row with
    valid_to IS NULL.

    A trust can move ICB on merger (the successor trust may sit in a different
    ICB to its predecessors). Versioning this relationship directly avoids
    having to traverse the organisation layer for 'which ICB was Trust X
    under on date Y' queries.

    England only.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    trust = models.ForeignKey(
        to=Trust,
        on_delete=models.CASCADE,
        related_name="integrated_care_board_memberships",
        verbose_name="Trust",
        help_text="The Trust this membership records the parent ICB of.",
    )
    integrated_care_board = models.ForeignKey(
        to=IntegratedCareBoard,
        on_delete=models.PROTECT,
        related_name="trust_memberships",
        verbose_name="Integrated Care Board",
        help_text="The ICB the Trust was a member of over this interval.",
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
            models.Index(fields=["trust", "valid_to"]),
            models.Index(fields=["integrated_care_board", "valid_from"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Trust–Integrated Care Board membership"
        verbose_name_plural = "Trust–Integrated Care Board memberships"

    def __str__(self) -> str:
        return (
            f"{self.trust.ods_code} → {self.integrated_care_board.ods_code} "
            f"({self.valid_from} → {self.valid_to or 'now'})"
        )

    def is_current(self) -> bool:
        """True if this is the current (open) membership."""
        return self.valid_to is None
