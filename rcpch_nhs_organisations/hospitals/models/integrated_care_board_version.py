# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .integrated_care_board import IntegratedCareBoard


class IntegratedCareBoardVersion(TimeStampAbstractBaseClass):
    """
    Append-only snapshot of an IntegratedCareBoard's mutable attributes over time.

    Each row represents a state of the IntegratedCareBoard valid over
    [valid_from, valid_to). The current state is the row with valid_to IS NULL.
    The immutable identifier (ods_code) lives on the IntegratedCareBoard itself.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    integrated_care_board = models.ForeignKey(
        to=IntegratedCareBoard,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="Integrated Care Board",
        help_text="The Integrated Care Board this version is a snapshot of.",
    )
    valid_from = models.DateField(
        verbose_name="Valid from",
        help_text="The date from which this state of the Integrated Care Board was in force.",
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

    # Snapshot of mutable attributes. The boundary_identifier and ods_code are
    # the immutable identifiers and live on the IntegratedCareBoard itself.
    name = models.CharField(max_length=77, null=True, blank=True, default=None)
    bng_e = models.BigIntegerField(null=True, blank=True, default=None)
    bng_n = models.BigIntegerField(null=True, blank=True, default=None)
    long = models.FloatField(null=True, blank=True, default=None)
    lat = models.FloatField(null=True, blank=True, default=None)
    globalid = models.CharField(max_length=38, null=True, blank=True, default=None)
    geom = models.MultiPolygonField(srid=27700, null=True, blank=True, default=None)
    publication_date = models.DateField(null=True, blank=True, default=None)

    class Meta:
        indexes = [
            models.Index(fields=["integrated_care_board", "valid_from"]),
            models.Index(fields=["valid_to"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Integrated Care Board version"
        verbose_name_plural = "Integrated Care Board versions"

    def __str__(self) -> str:
        return f"{self.integrated_care_board.ods_code} ({self.valid_from} → {self.valid_to or 'now'})"

    def is_current(self) -> bool:
        """True if this is the current (open) version of the Integrated Care Board."""
        return self.valid_to is None
