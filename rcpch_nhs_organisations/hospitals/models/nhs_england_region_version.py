# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .nhs_england_region import NHSEnglandRegion


class NHSEnglandRegionVersion(TimeStampAbstractBaseClass):
    """
    Append-only snapshot of an NHSEnglandRegion's mutable attributes over time.

    Each row represents a state of the NHSEnglandRegion valid over
    [valid_from, valid_to). The current state is the row with valid_to IS NULL.
    The immutable identifier (region_code) lives on the NHSEnglandRegion itself.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    nhs_england_region = models.ForeignKey(
        to=NHSEnglandRegion,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="NHS England Region",
        help_text="The NHS England Region this version is a snapshot of.",
    )
    valid_from = models.DateField(
        verbose_name="Valid from",
        help_text="The date from which this state of the NHS England Region was in force.",
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

    # Snapshot of mutable attributes. The boundary_identifier and region_code
    # are the immutable identifiers and live on the NHSEnglandRegion itself.
    name = models.CharField(max_length=24, null=True, blank=True, default=None)
    bng_e = models.BigIntegerField(null=True, blank=True, default=None)
    bng_n = models.BigIntegerField(null=True, blank=True, default=None)
    long = models.FloatField(null=True, blank=True, default=None)
    lat = models.FloatField(null=True, blank=True, default=None)
    globalid = models.CharField(max_length=38, null=True, blank=True, default=None)
    geom = models.MultiPolygonField(srid=27700, null=True, blank=True, default=None)
    publication_date = models.DateField(null=True, blank=True, default=None)

    class Meta:
        indexes = [
            models.Index(fields=["nhs_england_region", "valid_from"]),
            models.Index(fields=["valid_to"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "NHS England Region version"
        verbose_name_plural = "NHS England Region versions"

    def __str__(self) -> str:
        return f"{self.nhs_england_region.region_code} ({self.valid_from} → {self.valid_to or 'now'})"

    def is_current(self) -> bool:
        """True if this is the current (open) version of the NHS England Region."""
        return self.valid_to is None
