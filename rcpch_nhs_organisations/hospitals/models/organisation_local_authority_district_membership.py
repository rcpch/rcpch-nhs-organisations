# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .organisation import Organisation
from .local_authority import LocalAuthorityDistrict


class OrganisationLocalAuthorityDistrictMembership(TimeStampAbstractBaseClass):
    """
    Tracks which Local Authority District an Organisation belonged to over time.

    Append-only. Each row records that the Organisation was a member of the
    LAD over [valid_from, valid_to). The current membership is the row with
    valid_to IS NULL.

    LAD boundaries change (the codes were refreshed in 2024: LAD24CD), so
    this relationship is versioned.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    organisation = models.ForeignKey(
        to=Organisation,
        on_delete=models.CASCADE,
        related_name="local_authority_district_memberships",
        verbose_name="Organisation",
        help_text="The Organisation this membership records the LAD of.",
    )
    local_authority_district = models.ForeignKey(
        to=LocalAuthorityDistrict,
        on_delete=models.PROTECT,
        related_name="organisation_memberships",
        verbose_name="Local Authority District",
        help_text="The LAD the Organisation was a member of over this interval.",
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
            models.Index(fields=["local_authority_district", "valid_from"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Organisation–Local Authority District membership"
        verbose_name_plural = "Organisation–Local Authority District memberships"

    def __str__(self) -> str:
        return (
            f"{self.organisation.ods_code} → "
            f"{self.local_authority_district.lad24cd} "
            f"({self.valid_from} → {self.valid_to or 'now'})"
        )

    def is_current(self) -> bool:
        """True if this is the current (open) membership."""
        return self.valid_to is None
