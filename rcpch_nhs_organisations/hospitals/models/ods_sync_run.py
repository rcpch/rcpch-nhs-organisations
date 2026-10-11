# python imports

# django imports
from django.contrib.gis.db import models
from django.utils import timezone

# rcpch imports
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass


class OdsSyncRun(TimeStampAbstractBaseClass):
    """
    Records one execution of the ``reconcile_ods`` engine.

    The engine uses the most recent *successful* run to work out the window for
    the next incremental run — see ``synced_through``. A ``--since`` override on
    the command bypasses this and covers missed runs.

    See documentation/docs/developer/ods-sync.md.
    """

    MODE_INCREMENTAL = "incremental"
    MODE_BACKFILL = "backfill"
    MODE_CHOICES = [
        (MODE_INCREMENTAL, "Incremental (since last run)"),
        (MODE_BACKFILL, "Backfill (full history)"),
    ]

    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default=MODE_INCREMENTAL,
        verbose_name="Mode",
        help_text="Whether this was an incremental sync or a full history backfill.",
    )
    levels = models.CharField(
        max_length=100,
        default="",
        blank=True,
        verbose_name="Levels",
        help_text="Comma-separated list of levels reconciled (organisation, trust, lhb, icb).",
    )
    since = models.DateField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Window start",
        help_text="The LastChangeDate window start used for the /sync feed on this run.",
    )
    synced_through = models.DateField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Synced through",
        help_text=(
            "The date this run reconciled ODS through (normally the run date). "
            "The next incremental window starts from this date, minus a margin."
        ),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
        verbose_name="Status",
    )
    dry_run = models.BooleanField(
        default=True,
        verbose_name="Dry run",
        help_text="True if this run only detected changes and wrote nothing to the temporal layer.",
    )
    changes_detected = models.PositiveIntegerField(
        default=0,
        verbose_name="Changes detected",
        help_text="The number of structural deltas detected (PendingOdsChange rows touched).",
    )
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Started at",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Completed at",
    )
    report = models.TextField(
        blank=True,
        default="",
        verbose_name="Report",
        help_text="The categorised markdown report produced by this run.",
    )
    notes = models.TextField(
        blank=True,
        default="",
        verbose_name="Notes",
    )

    class Meta:
        indexes = [
            models.Index(fields=["status", "completed_at"]),
            models.Index(fields=["mode"]),
        ]
        ordering = ("-started_at",)
        verbose_name = "ODS sync run"
        verbose_name_plural = "ODS sync runs"

    def __str__(self) -> str:
        return (
            f"{self.get_mode_display()} run {self.started_at:%Y-%m-%d %H:%M} "
            f"({self.get_status_display()})"
        )

    @classmethod
    def last_successful(cls, mode=None):
        """Return the most recent successful run, optionally filtered by mode."""
        qs = cls.objects.filter(status=cls.STATUS_SUCCESS, dry_run=False)
        if mode is not None:
            qs = qs.filter(mode=mode)
        return qs.order_by("-synced_through", "-completed_at").first()
