# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .organisation import Organisation
from .lower_layer_super_output_area import LowerLayerSuperOutputArea


class OrganisationLowerLayerSuperOutputAreaMembership(TimeStampAbstractBaseClass):
    """
    Tracks which Lower Layer Super Output Area an Organisation belonged to over time.

    Append-only. Each row records that the Organisation was a member of the
    LSOA over [valid_from, valid_to). The current membership is the row with
    valid_to IS NULL.

    LSOA boundaries were redrawn in 2021 (the 2011 boundaries used here are
    the current ones in the database, but a 2021 refresh is anticipated — see
    the note in lower_layer_super_output_area.py). Versioning this
    relationship lets audit data be reported against the LSOA that was in
    force at the time, even after a boundary refresh.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    organisation = models.ForeignKey(
        to=Organisation,
        on_delete=models.CASCADE,
        related_name="lower_layer_super_output_area_memberships",
        verbose_name="Organisation",
        help_text="The Organisation this membership records the LSOA of.",
    )
    lower_layer_super_output_area = models.ForeignKey(
        to=LowerLayerSuperOutputArea,
        on_delete=models.PROTECT,
        related_name="organisation_memberships",
        verbose_name="Lower Layer Super Output Area",
        help_text="The LSOA the Organisation was a member of over this interval.",
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
            models.Index(fields=["lower_layer_super_output_area", "valid_from"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Organisation–Lower Layer Super Output Area membership"
        verbose_name_plural = (
            "Organisation–Lower Layer Super Output Area memberships"
        )

    def __str__(self) -> str:
        return (
            f"{self.organisation.ods_code} → "
            f"{self.lower_layer_super_output_area.lsoa11cd} "
            f"({self.valid_from} → {self.valid_to or 'now'})"
        )

    def is_current(self) -> bool:
        """True if this is the current (open) membership."""
        return self.valid_to is None
