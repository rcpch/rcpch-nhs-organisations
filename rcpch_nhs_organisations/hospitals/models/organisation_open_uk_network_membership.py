# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .organisation import Organisation
from .open_uk_network import OPENUKNetwork


class OrganisationOPENUKNetworkMembership(TimeStampAbstractBaseClass):
    """
    Tracks which OPEN UK Network an Organisation belonged to over time.

    Append-only. Each row records that the Organisation was a member of the
    OPEN UK Network over [valid_from, valid_to). The current membership is
    the row with valid_to IS NULL.

    OPEN UK network affiliation can change if an organisation is reassigned
    to a different network, or if a trust merger results in the successor
    trust being allocated to a different network.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    organisation = models.ForeignKey(
        to=Organisation,
        on_delete=models.CASCADE,
        related_name="openuk_network_memberships",
        verbose_name="Organisation",
        help_text="The Organisation this membership records the OPEN UK Network of.",
    )
    openuk_network = models.ForeignKey(
        to=OPENUKNetwork,
        on_delete=models.PROTECT,
        related_name="organisation_memberships",
        verbose_name="OPEN UK Network",
        help_text="The OPEN UK Network the Organisation was a member of over this interval.",
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
            models.Index(fields=["openuk_network", "valid_from"]),
        ]
        ordering = ("-valid_from",)
        verbose_name = "Organisation–OPEN UK Network membership"
        verbose_name_plural = "Organisation–OPEN UK Network memberships"

    def __str__(self) -> str:
        return (
            f"{self.organisation.ods_code} → {self.openuk_network.boundary_identifier} "
            f"({self.valid_from} → {self.valid_to or 'now'})"
        )

    def is_current(self) -> bool:
        """True if this is the current (open) membership."""
        return self.valid_to is None
