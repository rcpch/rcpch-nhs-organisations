# python imports

# django imports
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .organisation import Organisation


class OrganisationSuccession(TimeStampAbstractBaseClass):
    """
    Records the business relationship between two Organisation rows when an
    organisation's ODS code changes — typically because its parent trust was
    dissolved or merged and the ODS reissued the organisation's code with a
    new parent stem.

    Example: Princess Royal University Hospital was RYQ30 under South London
    Healthcare NHS Trust (RYQ). When RYQ was dissolved in 2013, the hospital
    moved to King's College Hospital NHS Foundation Trust (RJZ) and became
    RJZ30. An OrganisationSuccession row links RYQ30 → RJZ30 so that
    longitudinal audit data can follow the hospital across the code change.

    The membership tables (OrganisationTrustMembership, etc.) record *what*
    changed; this table records *why* — the link between a predecessor
    organisation and its successor, with a date and a type.

    Populated manually via the admin (per the resolved open question in the
    design doc), not automatically from the ODS Rels block, because ODS
    succession semantics are occasionally ambiguous.

    See documentation/docs/developer/merger-handling.md for the full
    description of how each merger type is handled.

    Part of the temporal history layer described in
    documentation/docs/developer/temporal-history.md.
    """

    predecessor = models.ForeignKey(
        to=Organisation,
        on_delete=models.PROTECT,
        related_name="succession_predecessor_links",
        verbose_name="Predecessor",
        help_text=(
            "The Organisation that ceased to exist (or was renamed / recoded) "
            "on the succession date."
        ),
    )
    successor = models.ForeignKey(
        to=Organisation,
        on_delete=models.PROTECT,
        related_name="succession_successor_links",
        verbose_name="Successor",
        null=True,
        blank=True,
        default=None,
        help_text=(
            "The Organisation that took over from the predecessor on the "
            "succession date. This is usually a newly created Organisation "
            "row with the new ODS code. Leave blank for a closure (no successor)."
        ),
    )
    succession_date = models.DateField(
        verbose_name="Succession date",
        help_text="The date on which the succession took effect.",
    )
    succession_type = models.CharField(
        max_length=20,
        choices=[
            ("merger", "Merger"),
            ("acquisition", "Acquisition"),
            ("rename", "Rename"),
            ("closure", "Closure"),
            ("split", "Split"),
            ("code_change", "ODS code change"),
        ],
        verbose_name="Succession type",
        help_text=(
            "The nature of the succession. Use 'ODS code change' when the "
            "organisation remains under the same parent trust but its ODS "
            "code was reissued."
        ),
    )
    notes = models.TextField(
        blank=True,
        default="",
        verbose_name="Notes",
        help_text="Optional free-text notes about the succession.",
    )

    class Meta:
        indexes = [models.Index(fields=["succession_date"])]
        verbose_name = "Organisation succession"
        verbose_name_plural = "Organisation successions"

    def __str__(self) -> str:
        successor = self.successor.ods_code if self.successor else "(closed)"
        return (
            f"{self.predecessor.ods_code} → {successor} "
            f"({self.succession_date}, {self.get_succession_type_display()})"
        )
