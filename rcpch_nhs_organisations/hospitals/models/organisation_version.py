# python imports

# django imports
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .organisation import Organisation


class OrganisationVersion(TimeStampAbstractBaseClass):
    """
    Append-only snapshot of an Organisation's mutable attributes over time.

    Each row represents a state of the Organisation that was valid over the
    half-open interval [valid_from, valid_to). The current state is the row
    with valid_to IS NULL. The immutable identifier (ods_code) lives on the
    Organisation itself; this table only snapshots the attributes that can
    change (name, address, active flag, etc.).

    This table is the entity-attribute layer of the temporal history design
    described in documentation/docs/developer/temporal-history.md. Relationship
    changes (e.g. org -> trust) are tracked separately in membership tables.
    """

    organisation = models.ForeignKey(
        to=Organisation,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="Organisation",
        help_text="The Organisation this version is a snapshot of.",
    )
    valid_from = models.DateField(
        verbose_name="Valid from",
        help_text="The date from which this state of the Organisation was in force.",
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

    # Snapshot of mutable attributes (mirrors Organisation, minus ods_code
    # which is the immutable identifier and lives on Organisation).
    name = models.CharField(max_length=100, null=True, blank=True, default=None)
    website = models.CharField(max_length=100, null=True, blank=True, default=None)
    address1 = models.CharField(max_length=100, null=True, blank=True, default=None)
    address2 = models.CharField(max_length=100, null=True, blank=True, default=None)
    address3 = models.CharField(max_length=100, null=True, blank=True, default=None)
    telephone = models.CharField(max_length=100, null=True, blank=True, default=None)
    city = models.CharField(max_length=100, null=True, blank=True, default=None)
    county = models.CharField(max_length=100, null=True, blank=True, default=None)
    latitude = models.FloatField(max_length=100, null=True, blank=True, default=None)
    longitude = models.FloatField(null=True, blank=True, default=None)
    postcode = models.CharField(max_length=10, null=True, blank=True, default=None)
    geocode_coordinates = models.PointField(
        null=True, blank=True, default=None, srid=4326
    )
    active = models.BooleanField(default=True)
    published_at = models.DateField(null=True, blank=True, default=None)

    class Meta:
        indexes = [
            models.Index(fields=["organisation", "valid_from"]),
            models.Index(fields=["valid_to"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Organisation version"
        verbose_name_plural = "Organisation versions"

    def __str__(self) -> str:
        return f"{self.organisation.ods_code} ({self.valid_from} → {self.valid_to or 'now'})"

    def is_current(self) -> bool:
        """True if this is the current (open) version of the Organisation."""
        return self.valid_to is None
