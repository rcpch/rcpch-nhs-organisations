# python imports
import datetime

# django imports
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
    OpenApiResponse,
    OpenApiExample,
)

# RCPCH imports
from ..models import (
    Organisation,
    OrganisationVersion,
    OrganisationTrustMembership,
    OrganisationLocalHealthBoardMembership,
    OrganisationIntegratedCareBoardMembership,
    OrganisationNHSEnglandRegionMembership,
    OrganisationOPENUKNetworkMembership,
    OrganisationPaediatricDiabetesUnitMembership,
    OrganisationSuccession,
)
from ..serializers import OrganisationSerializer


def _as_of(queryset, on_date):
    """Filter a temporal queryset to the row in force on the given date."""
    from django.db.models import Q

    return queryset.filter(
        valid_from__lte=on_date,
    ).filter(Q(valid_to__gt=on_date) | Q(valid_to__isnull=True))


def _resolve_predecessor(organisation, on_date):
    """
    Walk the OrganisationSuccession chain backwards to find the entity that
    was in force as the audit code on `on_date`.

    Two cases trigger the walk:

    1. **Strict succession** — the successor did not exist on `on_date` (its
       first ``valid_from`` is after `on_date`). The walk finds the
       predecessor that was open then. Example: querying RJZ30 before 2013
       walks to RYQ30.

    2. **Parallel code** — the successor pre-existed at `on_date` but a
       succession link records that the predecessor was the live audit code
       before the succession date (``succession_date > on_date``). The walk
       returns the predecessor because that was the code the audit would
       have used at `on_date`. Example: querying RAL27 at 2020 walks to
       RAPNM, because RAPNM was the live code under RAP trust until it
       closed on 2024-12-31 and followed to RAL27.
    """
    current = organisation
    visited = set()
    while current.pk not in visited:
        visited.add(current.pk)
        first_version = current.versions.order_by("valid_from").first()

        # Did the entity's history start by on_date? (The first version's
        # valid_from is at or before on_date — the _as_of query will find
        # the right version row, whether it's this one or a later one.)
        history_started = (
            first_version is not None and first_version.valid_from <= on_date
        )

        # Is there a successor-side link whose succession_date is after
        # on_date? For parallel codes, the predecessor was the live audit
        # code before the succession date, so we walk to it.
        parallel_link = current.succession_successor_links.filter(
            succession_date__gt=on_date
        ).first()

        if parallel_link is not None:
            # Walk to the predecessor — it was the live code at on_date.
            current = parallel_link.predecessor
            continue

        if history_started:
            return current

        # History didn't start by on_date and no parallel link — try the
        # regular walk (strict succession where the successor didn't exist).
        link = current.succession_successor_links.first()
        if link is None:
            return None
        current = link.predecessor
    return None


def organisation_snapshot(organisation, on_date):
    """
    Assemble a snapshot dict of the organisation's attributes and relationships
    as they were on `on_date`. Returns None if the organisation (or any
    predecessor) did not exist on that date.
    """
    resolved = _resolve_predecessor(organisation, on_date)
    if resolved is None:
        return None

    version = _as_of(resolved.versions, on_date).first()
    if version is None:
        return None

    def _parent(membership_qs, parent_attr):
        row = _as_of(membership_qs, on_date).first()
        return getattr(row, parent_attr, None) if row else None

    trust = _parent(resolved.trust_memberships, "trust")
    local_health_board = _parent(resolved.local_health_board_memberships, "local_health_board")
    integrated_care_board = _parent(resolved.integrated_care_board_memberships, "integrated_care_board")
    nhs_england_region = _parent(resolved.nhs_england_region_memberships, "nhs_england_region")
    openuk_network = _parent(resolved.openuk_network_memberships, "openuk_network")
    paediatric_diabetes_unit = _parent(resolved.paediatric_diabetes_unit_memberships, "paediatric_diabetes_unit")

    # Parent entity names are read from their *Version rows as-of the snapshot
    # date, not the denormalised entity row, so a pre-rename date returns the
    # historical name (e.g. "Salford Royal" before 2021-10-01, not the current
    # "Northern Care Alliance"). Each falls back to the current entity.name
    # when no version row covers the date (e.g. before the baseline migration,
    # or an entity with no version history at all).
    trust_version = _as_of(trust.versions, on_date).first() if trust else None
    lhb_version = (
        _as_of(local_health_board.versions, on_date).first()
        if local_health_board
        else None
    )
    icb_version = (
        _as_of(integrated_care_board.versions, on_date).first()
        if integrated_care_board
        else None
    )

    return {
        "ods_code": resolved.ods_code,
        "snapshot_date": on_date.isoformat(),
        "name": version.name,
        "address1": version.address1,
        "address2": version.address2,
        "address3": version.address3,
        "telephone": version.telephone,
        "city": version.city,
        "county": version.county,
        "postcode": version.postcode,
        "latitude": version.latitude,
        "longitude": version.longitude,
        "active": version.active,
        "published_at": version.published_at.isoformat() if version.published_at else None,
        "trust": {
            "ods_code": trust.ods_code,
            "name": trust_version.name if trust_version is not None else trust.name,
        } if trust else None,
        "local_health_board": {
            "ods_code": local_health_board.ods_code,
            "name": (
                lhb_version.name
                if lhb_version is not None
                else local_health_board.name
            ),
        } if local_health_board else None,
        "integrated_care_board": {
            "ods_code": integrated_care_board.ods_code,
            "name": (
                icb_version.name
                if icb_version is not None
                else integrated_care_board.name
            ),
        } if integrated_care_board else None,
        "nhs_england_region": {
            "region_code": nhs_england_region.region_code,
            "name": nhs_england_region.name,
        } if nhs_england_region else None,
        "openuk_network": {
            "boundary_identifier": openuk_network.boundary_identifier,
            "name": openuk_network.name,
        } if openuk_network else None,
        "paediatric_diabetes_unit": {
            "pz_code": paediatric_diabetes_unit.pz_code,
        } if paediatric_diabetes_unit else None,
        "predecessor_ods_code": (
            resolved.ods_code
            if resolved.pk != organisation.pk
            else None
        ),
    }


class OrganisationSnapshotView(APIView):
    """
    **Give me everything about this organisation as it was on date X.**

    Returns a snapshot of an organisation and all its relationships as they
    were on a given date — its name/address/active state plus every parent
    relationship (trust, Local Health Board, Integrated Care Board, NHS
    England region, OPEN UK network, Paediatric Diabetes Unit) as they were
    on that date.

    This is the endpoint used by national audits to compare current
    performance against past performance: the audit queries the **current**
    ODS code with a historical date and gets back the organisational
    geography that was in force when the historical data was collected.

    **Predecessor walk.** If the queried ODS code was not the live audit code
    on that date (because of a merger, split, or parallel-code succession),
    the endpoint walks the `OrganisationSuccession` chain backwards to the
    predecessor that was in force then, and returns that predecessor's state
    with `predecessor_ods_code` populated. Two cases:

    1. *Strict succession* — the successor did not exist at the queried date
       (e.g. querying `RJZ30` at 2012 walks to `RYQ30`, Princess Royal under
       South London Healthcare before the 2013 split).
    2. *Parallel code* — the successor pre-existed at the queried date, but a
       succession link records that the predecessor was the live audit code
       before the succession date (e.g. querying `RAL27` at 2020 walks to
       `RAPNM`, North Middlesex under North Middlesex University Hospital
       NHS Trust `RAP` before it closed on 2024-12-31 and followed to `RAL27`).

    Returns 404 if no entity (the queried code or any predecessor) covered
    the date, or if the queried ODS code does not exist in the database.

    See documentation/docs/developer/temporal-history.md for the design and
    documentation/docs/developer/ods-sync.md for the predecessor walk.
    """

    @extend_schema(
        summary="Snapshot of an organisation as it was on a given date",
        tags=["Organisations"],
        parameters=[
            OpenApiParameter(
                name="date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    "The date to snapshot the organisation at. Returns the "
                    "organisation's name/address/active state and every parent "
                    "relationship (trust, LHB, ICB, NHS England region, OPENUK, "
                    "PDU) as they were on that date. If the queried ODS code "
                    "was not the live audit code on that date, walks the "
                    "succession chain backwards to the predecessor that was. "
                    "If omitted, returns the current state. Format: YYYY-MM-DD."
                ),
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description=(
                    "Everything about this organisation as it was on the "
                    "given date — its attributes plus every parent "
                    "relationship. If a predecessor was returned, "
                    "`predecessor_ods_code` is populated."
                ),
            ),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description=(
                    "The organisation (or any predecessor in the succession "
                    "chain) did not exist on the given date, or the queried "
                    "ODS code is not in the database."
                ),
            ),
        },
    )
    def get(self, request, ods_code):
        organisation = get_object_or_404(Organisation, ods_code=ods_code)
        date_str = request.query_params.get("date")
        if date_str:
            try:
                on_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            on_date = datetime.date.today()

        snapshot = organisation_snapshot(organisation, on_date)
        if snapshot is None:
            return Response(
                {
                    "detail": (
                        f"No state found for organisation {ods_code} on "
                        f"{on_date.isoformat()}. The organisation may not "
                        "have existed on that date, or the temporal history "
                        "layer was not yet recording changes."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(snapshot)
