# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .organisation import Organisation
from .london_borough import LondonBorough


class OrganisationLondonBoroughMembership(TimeStampAbstractBaseClass):
    """
    Tracks which London Borough an Organisation belonged to over time.

    Append-only. Each row records that the Organisation was a member of the
    London Borough over [valid_from, valid_to). The current membership is the
    row with valid_to IS NULL.

    London Borough boundaries can change (e.g. on local government
    reorganisation), so this relationship is versioned even though it is
    administrative rather than health-structural.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    organisation = models.ForeignKey(
        to=Organisation,
        on_delete=models.CASCADE,
        related_name="london_borough_memberships",
        verbose_name="Organisation",
        help_text="The Organisation this membership records the London Borough of.",
    )
    london_borough = models.ForeignKey(
        to=LondonBorough,
        on_delete=models.PROTECT,
        related_name="organisation_memberships",
        verbose_name="London Borough",
        help_text="The London Borough the Organisation was a member of over this interval.",
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
            models.Index(fields=["london_borough", "valid_from"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Organisation–London Borough membership"
        verbose_name_plural = "Organisation–London Borough memberships"

    def __str__(self) -> str:
        return (
            f"{self.organisation.ods_code} → {self.london_borough.gss_code} "
            f"({self.valid_from} → {self.valid_to or 'now'})"
        )

    def is_current(self) -> bool:
        """True if this is the current (open) membership."""
        return self.valid_to is None
