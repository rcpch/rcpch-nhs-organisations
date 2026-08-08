# python imports

# django imports
from django.contrib.gis.db import models
from django.db.models import CharField

from .paediatric_diabetes_network import PaediatricDiabetesNetwork

class PaediatricDiabetesUnit(models.Model):
    pz_code = CharField("Paediatric Diabetes Unit PZ Number", max_length=5, unique=True)

    unit_name = CharField(
        "Name for the unit if different from the primary organisation for the parent",
        max_length=255,
        null=True,
        blank=True,
        default=None
    )

    # How the PDU's display name is derived when unit_name is not set.
    # lead_organisation: use the lead organisation's name (the default for
    #   most PDUs — the diabetes service is identified by the hospital it
    #   runs in).
    # trust: use the lead organisation's parent trust name (for PDUs that
    #   span multiple sites and identify themselves by the parent trust
    #   rather than any single site, e.g. PZ024 East Kent).
    # local_health_board: use the lead organisation's parent LHB name (for
    #   Welsh PDUs, e.g. PZ244).
    # This is modelled rather than hardcoded so that new PDUs created by
    # mergers get a name source at creation time. See
    # documentation/docs/developer/merger-handling.md.
    NAME_SOURCE_LEAD_ORGANISATION = "lead_organisation"
    NAME_SOURCE_TRUST = "trust"
    NAME_SOURCE_LOCAL_HEALTH_BOARD = "local_health_board"
    NAME_SOURCE_CHOICES = (
        (NAME_SOURCE_LEAD_ORGANISATION, "Lead organisation"),
        (NAME_SOURCE_TRUST, "Parent trust"),
        (NAME_SOURCE_LOCAL_HEALTH_BOARD, "Parent local health board"),
    )
    name_source = CharField(
        max_length=30,
        choices=NAME_SOURCE_CHOICES,
        default=NAME_SOURCE_LEAD_ORGANISATION,
        verbose_name="Name source",
        help_text=(
            "How the PDU's display name is derived when unit_name is not "
            "set. 'Lead organisation' (default) uses the lead organisation's "
            "name; 'Parent trust' uses the lead organisation's parent trust "
            "name (for multi-site PDUs that identify by trust); 'Parent "
            "local health board' uses the LHB name (for Welsh PDUs)."
        ),
    )

    class Meta:
        verbose_name = "Paediatric Diabetes Unit"
        verbose_name_plural = "Paediatric Diabetes Units"
        ordering = ("pz_code",)

    def __str__(self) -> str:
        return f"{self.pz_code}"

    paediatric_diabetes_network = models.ForeignKey(  # it is possible for a PaediatricDiabetesUnit to not be associated with a PaediatricDiabetesNetwork (eg RCPCH has a PZ code but no PN code)
        to=PaediatricDiabetesNetwork,
        on_delete=models.CASCADE,
        verbose_name="Paediatric Diabetes Network",
        related_name="paediatric_diabetes_units",
        blank=True,
        null=True,
    )

    updated_at = models.DateTimeField(
        "Last Updated",
        auto_now=True,
    )

    active = models.BooleanField(
        "Active",
        default=True,
    )

    # The lead/primary organisation for this PDU. This is a denormalised FK
    # (current state) — the temporal history of which org was lead is
    # recorded in PaediatricDiabetesUnitVersion.lead_organisation. Set to
    # NULL when the lead org is reassigned away from this PDU; the operator
    # (or the acquisition/merger wizard) must set a new lead. Exposed via
    # the /paediatric_diabetes_units/{pz_code}/parent/ endpoint as
    # primary_organisation. See
    # documentation/docs/developer/merger-handling.md.
    lead_organisation = models.ForeignKey(
        to="hospitals.Organisation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="lead_pdu_set",
        verbose_name="Lead organisation",
        help_text=(
            "The lead/primary organisation for this PDU. Exposed via the "
            "/paediatric_diabetes_units/{pz_code}/parent/ endpoint as "
            "primary_organisation."
        ),
    )

    @property
    def organisations(self):
        # The hardcoded special cases for inactive predecessor PDUs
        # (PZ003, PZ216, PZ125, PZ080, PZ141) have been removed. Their
        # membership history is now held in the temporal layer
        # (OrganisationPaediatricDiabetesUnitMembership), so the default
        # query returns the correct set of organisations for both active
        # and inactive PDUs. See
        # documentation/docs/developer/merger-handling.md.
        return self.paediatric_diabetes_unit_organisations.all()

    @property
    def primary_organisation(self):
        # The lead/primary organisation is modelled as a FK on the PDU
        # (current state) and snapshotted on PaediatricDiabetesUnitVersion
        # (temporal history). The hardcoded if/elif block that was here has
        # been removed. See documentation/docs/developer/merger-handling.md.
        if self.lead_organisation_id:
            return self.lead_organisation
        # No lead FK set. For a single-org PDU the lead is unambiguous.
        organisations = self.organisations
        if not organisations.exists():
            return None
        if organisations.count() == 1:
            return organisations.get()
        # No lead FK and multiple orgs — ambiguous. Return None rather
        # than an arbitrary org, so the API surfaces the gap instead of
        # hiding it. Run `python manage.py backfill_pdu_lead_organisations`
        # to set the lead_organisation FKs, or set it via the admin.
        return None

    @property
    def name(self):
        if self.unit_name:
            return self.unit_name

        primary = self.primary_organisation
        if primary is None:
            return self.pz_code

        if self.name_source == self.NAME_SOURCE_TRUST:
            return primary.trust.name if primary.trust else primary.name
        if self.name_source == self.NAME_SOURCE_LOCAL_HEALTH_BOARD:
            return (
                primary.local_health_board.name
                if primary.local_health_board
                else primary.name
            )
        # Default: lead organisation's name.
        return primary.name