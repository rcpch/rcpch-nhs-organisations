# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .organisation import Organisation
from .nhs_england_region import NHSEnglandRegion


class OrganisationNHSEnglandRegionMembership(TimeStampAbstractBaseClass):
    """
    Tracks which NHS England Region an Organisation belonged to over time.

    Append-only. Each row records that the Organisation was a member of the
    NHS England Region over [valid_from, valid_to). The current membership is
    the row with valid_to IS NULL.

    England only. An organisation can move NHS England region if its parent
    trust moves region on merger.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    organisation = models.ForeignKey(
        to=Organisation,
        on_delete=models.CASCADE,
        related_name="nhs_england_region_memberships",
        verbose_name="Organisation",
        help_text="The Organisation this membership records the NHS England Region of.",
    )
    nhs_england_region = models.ForeignKey(
        to=NHSEnglandRegion,
        on_delete=models.PROTECT,
        related_name="organisation_memberships",
        verbose_name="NHS England Region",
        help_text="The NHS England Region the Organisation was a member of over this interval.",
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
            models.Index(fields=["nhs_england_region", "valid_from"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Organisation–NHS England Region membership"
        verbose_name_plural = "Organisation–NHS England Region memberships"

    def __str__(self) -> str:
        return (
            f"{self.organisation.ods_code} → {self.nhs_england_region.region_code} "
            f"({self.valid_from} → {self.valid_to or 'now'})"
        )

    def is_current(self) -> bool:
        """True if this is the current (open) membership."""
        return self.valid_to is None
