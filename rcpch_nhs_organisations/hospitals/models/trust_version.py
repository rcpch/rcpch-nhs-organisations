# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .trust import Trust


class TrustVersion(TimeStampAbstractBaseClass):
    """
    Append-only snapshot of a Trust's mutable attributes over time.

    Each row represents a state of the Trust valid over [valid_from, valid_to).
    The current state is the row with valid_to IS NULL. The immutable identifier
    (ods_code) lives on the Trust itself.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    trust = models.ForeignKey(
        to=Trust,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="Trust",
        help_text="The Trust this version is a snapshot of.",
    )
    valid_from = models.DateField(
        verbose_name="Valid from",
        help_text="The date from which this state of the Trust was in force.",
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

    # Snapshot of mutable attributes (mirrors Trust, minus ods_code).
    name = models.CharField(max_length=100, null=True, blank=True, default=None)
    address_line_1 = models.CharField(
        max_length=100, null=True, blank=True, default=None
    )
    address_line_2 = models.CharField(max_length=100, blank=True, default="")
    town = models.CharField(max_length=100, null=True, blank=True, default=None)
    postcode = models.CharField(max_length=10, null=True, blank=True, default=None)
    country = models.CharField(max_length=50, null=True, blank=True, default=None)
    telephone = models.CharField(max_length=100, null=True, blank=True, default=None)
    website = models.CharField(max_length=100, null=True, blank=True, default=None)
    active = models.BooleanField(default=True)
    published_at = models.DateField(null=True, blank=True, default=None)

    class Meta:
        indexes = [
            models.Index(fields=["trust", "valid_from"]),
            models.Index(fields=["valid_to"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Trust version"
        verbose_name_plural = "Trust versions"

    def __str__(self) -> str:
        return f"{self.trust.ods_code} ({self.valid_from} → {self.valid_to or 'now'})"

    def is_current(self) -> bool:
        """True if this is the current (open) version of the Trust."""
        return self.valid_to is None
