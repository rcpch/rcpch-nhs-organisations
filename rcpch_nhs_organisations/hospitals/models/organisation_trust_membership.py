# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .organisation import Organisation
from .trust import Trust


class OrganisationTrustMembership(TimeStampAbstractBaseClass):
    """
    Tracks which Trust an Organisation belonged to over time.

    Append-only. Each row records that the Organisation was a member of the
    Trust over the half-open interval [valid_from, valid_to). The current
    membership is the row with valid_to IS NULL.

    This is the relationship layer of the temporal history design described
    in documentation/docs/developer/temporal-history.md. When a trust merger
    occurs, the current row is closed (valid_to set) and a new row opened
    pointing to the successor trust. The Organisation.trust FK on the main
    table is also updated to keep current-state queries working, but the
    historical record is preserved here.

    England only. Welsh organisations use OrganisationLocalHealthBoardMembership.
    """

    organisation = models.ForeignKey(
        to=Organisation,
        on_delete=models.CASCADE,
        related_name="trust_memberships",
        verbose_name="Organisation",
        help_text="The Organisation this membership records the parent Trust of.",
    )
    trust = models.ForeignKey(
        to=Trust,
        on_delete=models.PROTECT,  # don't let a trust vanish and lose history
        related_name="organisation_memberships",
        verbose_name="Trust",
        help_text="The Trust the Organisation was a member of over this interval.",
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
            models.Index(fields=["trust", "valid_from"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Organisation–Trust membership"
        verbose_name_plural = "Organisation–Trust memberships"

    def __str__(self) -> str:
        return (
            f"{self.organisation.ods_code} → {self.trust.ods_code} "
            f"({self.valid_from} → {self.valid_to or 'now'})"
        )

    def is_current(self) -> bool:
        """True if this is the current (open) membership."""
        return self.valid_to is None
