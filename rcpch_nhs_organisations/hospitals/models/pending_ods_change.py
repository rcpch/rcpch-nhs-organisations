# python imports

# django imports
from django.conf import settings
from django.contrib.gis.db import models

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .ods_sync_run import OdsSyncRun


class PendingOdsChange(TimeStampAbstractBaseClass):
    """
    A structural change detected against ODS that is queued for human review.

    The ``reconcile_ods`` engine never applies structural changes (mergers,
    acquisitions, splits, closures, re-parentings, superseded codes, roster
    additions, status flips) automatically — ODS succession semantics are
    ambiguous. Each detected structural delta is persisted here, and the admin
    review queue drives **Approve & apply** (which calls the existing
    merger-wizard functions and temporal helpers) or **Dismiss**.

    Attribute-only changes with no succession in the window are applied
    automatically by the engine and are *not* queued here.

    The dedup key is ``(level, ods_code, change_class, effective_date)`` so a
    monthly re-run does not re-queue an already-pending, already-applied, or
    already-dismissed change.

    See documentation/docs/developer/ods-sync.md.
    """

    LEVEL_ORGANISATION = "organisation"
    LEVEL_TRUST = "trust"
    LEVEL_LHB = "lhb"
    LEVEL_ICB = "icb"
    LEVEL_CHOICES = [
        (LEVEL_ORGANISATION, "Organisation"),
        (LEVEL_TRUST, "Trust"),
        (LEVEL_LHB, "Local Health Board"),
        (LEVEL_ICB, "Integrated Care Board"),
    ]

    CLASS_ATTRIBUTE = "attribute"
    CLASS_RELATIONSHIP = "relationship"
    CLASS_SUCCESSION = "succession"
    CLASS_SUPERSEDED_CODE = "superseded-code"
    CLASS_ROSTER_ADD = "roster-add"
    CLASS_RETIRE = "retire"
    CLASS_PARALLEL_CODE = "parallel-code"
    CHANGE_CLASS_CHOICES = [
        (CLASS_ATTRIBUTE, "Attribute change"),
        (CLASS_RELATIONSHIP, "Relationship (re-parenting)"),
        (CLASS_SUCCESSION, "Succession (merger/acquisition/split/closure)"),
        (CLASS_SUPERSEDED_CODE, "Superseded organisation code"),
        (CLASS_ROSTER_ADD, "Roster add (new entity in ODS)"),
        (CLASS_RETIRE, "Retire (closed/inactive in ODS)"),
        (CLASS_PARALLEL_CODE, "Parallel active code"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_APPLIED = "applied"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_APPLIED, "Applied"),
        (STATUS_DISMISSED, "Dismissed"),
    ]

    # Statuses that mean the row is settled and must not be re-queued or
    # re-touched by a subsequent detection run.
    TERMINAL_STATUSES = (STATUS_APPLIED, STATUS_DISMISSED)

    level = models.CharField(
        max_length=20,
        choices=LEVEL_CHOICES,
        verbose_name="Level",
        help_text="The geography level this change applies to.",
    )
    ods_code = models.CharField(
        max_length=20,
        verbose_name="ODS code",
        help_text="The ODS code of the entity the change applies to.",
    )
    change_class = models.CharField(
        max_length=20,
        choices=CHANGE_CLASS_CHOICES,
        verbose_name="Change class",
    )
    effective_date = models.DateField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Effective date",
        help_text=(
            "The ODS effective date of the change (used as part of the dedup "
            "key). Null for changes with no clean effective date."
        ),
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Payload",
        help_text=(
            "Old → new values, succession events, ODS legal/operational dates, "
            "and the successor code where applicable."
        ),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="Status",
    )
    detected_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Detected at",
    )
    source_run = models.ForeignKey(
        to=OdsSyncRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="pending_changes",
        verbose_name="Source run",
        help_text="The reconcile_ods run that first detected this change.",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="reviewed_ods_changes",
        verbose_name="Reviewed by",
    )
    reviewer_notes = models.TextField(
        blank=True,
        default="",
        verbose_name="Reviewer notes",
    )
    applied_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Applied at",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["level", "ods_code", "change_class", "effective_date"],
                name="unique_pending_ods_change",
            )
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["level", "change_class"]),
            models.Index(fields=["ods_code"]),
        ]
        ordering = ("-detected_at",)
        verbose_name = "Pending ODS change"
        verbose_name_plural = "Pending ODS changes"

    def __str__(self) -> str:
        return (
            f"{self.get_level_display()} {self.ods_code} — "
            f"{self.get_change_class_display()} ({self.get_status_display()})"
        )

    @property
    def is_terminal(self) -> bool:
        return self.status in self.TERMINAL_STATUSES
