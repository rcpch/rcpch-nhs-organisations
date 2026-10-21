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


def _resolve_as_of(organisation, on_date):
    """
    Walk the OrganisationSuccession chain to find the entity that was in
    force as the audit code on `on_date`. Walks backwards (to a predecessor)
    or forwards (to a successor) as needed.

    Three cases trigger a walk:

    1. **Backward — strict succession** — the successor did not exist on
       `on_date` (its first ``valid_from`` is after `on_date`). The walk
       finds the predecessor that was open then. Example: querying RJZ30
       before 2013 walks to RYQ30.

    2. **Backward — parallel code** — the successor pre-existed at
       `on_date` but a succession link records that the predecessor was
       the live audit code before the succession date
       (``succession_date > on_date``). The walk returns the predecessor
       because that was the code the audit would have used at `on_date`.
       Example: querying RAL27 at 2020 walks to RAPNM, because RAPNM was
       the live code under RAP trust until it closed on 2024-12-31 and
       followed to RAL27.

    3. **Forward** — the predecessor's history ended before `on_date` (no
       version row covers `on_date`) OR the predecessor is inactive
       (``active=False``) with a successor. A succession link records that
       the successor took over on or before `on_date`
       (``succession_date <= on_date``). The walk returns the successor
       because that is the code the audit would use at `on_date`. Example:
       querying RVY02 at today walks to RBN52, because RVY02 closed on
       2023-07-01 and was succeeded by RBN52. Only walks if there is
       exactly one distinct successor — a split (multiple distinct
       successors) returns None because walking to an arbitrary successor
       would return the wrong site's geography. Duplicate succession rows
       to the same successor (e.g. from re-running the backfill with
       different effective dates) are treated as one successor.
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

        # Backward walk — parallel code: the predecessor was the live audit
        # code before the succession date, so walk to it.
        parallel_link = current.succession_successor_links.filter(
            succession_date__gt=on_date
        ).first()
        if parallel_link is not None:
            current = parallel_link.predecessor
            continue

        if not history_started:
            # Backward walk — strict succession: the successor didn't exist
            # at on_date. Walk to the predecessor.
            link = current.succession_successor_links.first()
            if link is None:
                return None
            current = link.predecessor
            continue

        # History started by on_date. Check whether a version row actually
        # covers on_date, and whether it is active.
        version = _as_of(current.versions, on_date).first()
        if version is not None and version.active:
            return current

        # No active version covering on_date — the entity is either closed
        # (no version row) or inactive (active=False, e.g. a predecessor
        # created by `mergers --create` with an open-ended baseline version).
        # Try the forward walk.
        forward_links = current.succession_predecessor_links.filter(
            succession_date__lte=on_date,
            successor__isnull=False,
        )
        # Count distinct successors, not rows — duplicate succession rows
        # to the same successor (e.g. from re-running the backfill with
        # different effective dates) should be treated as one.
        distinct_successor_ids = set(
            forward_links.values_list("successor_id", flat=True)
        )
        if len(distinct_successor_ids) == 1:
            current = forward_links.first().successor
            continue

        # No forward walk possible. If we have an inactive version covering
        # on_date (a closure with no successor), return the entity itself —
        # the consumer gets its final state. If no version covers on_date,
        # or the entity was split (multiple distinct successors), return
        # None (404).
        if version is not None:
            return current

        return None

    return None


def organisation_snapshot(organisation, on_date):
    """
    Assemble a snapshot dict of the organisation's attributes and relationships
    as they were on `on_date`. Returns None if the organisation (or any
    predecessor) did not exist on that date.
    """
    resolved = _resolve_as_of(organisation, on_date)
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

    # Chain fields: the resolved entity's immediate neighbours in the
    # OrganisationSuccession chain, regardless of whether a walk happened.
    # Scalar — null if zero or multiple distinct entities (a split or a
    # closure). Duplicate succession rows to the same entity (e.g. from
    # re-running the backfill with different effective dates) are treated
    # as one. The consumer detects a walk by comparing `ods_code` to
    # their queried code.
    predecessor_links = resolved.succession_successor_links.all()
    successor_links = resolved.succession_predecessor_links.filter(
        successor__isnull=False
    )
    distinct_predecessor_ids = set(
        predecessor_links.values_list("predecessor_id", flat=True)
    )
    distinct_successor_ids = set(
        successor_links.values_list("successor_id", flat=True)
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
            predecessor_links.first().predecessor.ods_code
            if len(distinct_predecessor_ids) == 1
            else None
        ),
        "successor_ods_code": (
            successor_links.first().successor.ods_code
            if len(distinct_successor_ids) == 1
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

    **Succession walk.** If the queried ODS code was not the live audit code
    on that date (because of a merger, split, or parallel-code succession),
    the endpoint walks the `OrganisationSuccession` chain to the entity that
    was in force then, and returns that entity's state. The walk goes in
    either direction:

    1. *Backward — strict succession* — the successor did not exist at the
       queried date (e.g. querying `RJZ30` at 2012 walks to `RYQ30`, Princess
       Royal under South London Healthcare before the 2013 split).
    2. *Backward — parallel code* — the successor pre-existed at the queried
       date, but a succession link records that the predecessor was the live
       audit code before the succession date (e.g. querying `RAL27` at 2020
       walks to `RAPNM`, North Middlesex under North Middlesex University
       Hospital NHS Trust `RAP` before it closed on 2024-12-31 and followed
       to `RAL27`).
    3. *Forward* — the predecessor's history ended before the queried date
       (e.g. querying `RVY02` at today walks to `RBN52`, because RVY02
       closed on 2023-07-01 and was succeeded by RBN52). Only walks if
       there is exactly one successor — a split returns 404.

    **Chain fields.** `predecessor_ods_code` and `successor_ods_code` are
    the resolved entity's immediate neighbours in the `OrganisationSuccession`
    chain, regardless of whether a walk happened. Both are scalars (null if
    zero or multiple links). The consumer detects a walk by comparing
    `ods_code` in the response to the queried code.

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
                    "succession chain (backward or forward) to the entity that "
                    "was. If omitted, returns the current state. "
                    "Format: YYYY-MM-DD."
                ),
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description=(
                    "Everything about this organisation as it was on the "
                    "given date — its attributes plus every parent "
                    "relationship. `predecessor_ods_code` and "
                    "`successor_ods_code` are the resolved entity's "
                    "immediate neighbours in the OrganisationSuccession "
                    "chain."
                ),
                examples=[
                    OpenApiExample(
                        "No walk — current code at today",
                        summary="Query the live audit code at today",
                        description=(
                            "The resolved entity is the queried code. "
                            "`predecessor_ods_code` is populated if the "
                            "entity succeeded another; `successor_ods_code` "
                            "is null (the entity is still live)."
                        ),
                        value={
                            "ods_code": "RBN52",
                            "snapshot_date": "2026-10-20",
                            "name": "ORMSKIRK AND DISTRICT GENERAL HOSPITAL",
                            "address1": "WIGAN ROAD",
                            "address2": None,
                            "address3": None,
                            "telephone": None,
                            "city": "ORMSKIRK",
                            "county": "LANCASHIRE",
                            "postcode": "L39 2AZ",
                            "latitude": None,
                            "longitude": None,
                            "active": True,
                            "published_at": None,
                            "trust": {
                                "ods_code": "RBN",
                                "name": "MERSEY AND WEST LANCASHIRE TEACHING HOSPITALS NHS TRUST",
                            },
                            "local_health_board": None,
                            "integrated_care_board": {
                                "ods_code": "QYG",
                                "name": "NHS CHESHIRE AND MERSEYSIDE INTEGRATED CARE BOARD",
                            },
                            "nhs_england_region": {
                                "region_code": "Y62",
                                "name": "North West",
                            },
                            "openuk_network": {
                                "boundary_identifier": "EPIC",
                                "name": "Mersey and North Wales network 'Epilepsy In Childhood' interest group",
                            },
                            "paediatric_diabetes_unit": {"pz_code": "PZ110"},
                            "predecessor_ods_code": "RVY02",
                            "successor_ods_code": None,
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        "Backward walk — successor queried before succession date",
                        summary="Query the current code at a date before the succession",
                        description=(
                            "The resolved entity is the predecessor. "
                            "`predecessor_ods_code` is null (the resolved "
                            "predecessor has no predecessor of its own); "
                            "`successor_ods_code` is the queried code. "
                            "The consumer detects a walk by comparing "
                            "`ods_code` to the queried code."
                        ),
                        value={
                            "ods_code": "RVY02",
                            "snapshot_date": "2022-01-01",
                            "name": "ORMSKIRK & DISTRICT GENERAL HOSPITAL",
                            "address1": "WIGAN ROAD",
                            "address2": None,
                            "address3": None,
                            "telephone": None,
                            "city": "ORMSKIRK",
                            "county": "LANCASHIRE",
                            "postcode": "L39 2AZ",
                            "latitude": None,
                            "longitude": None,
                            "active": True,
                            "published_at": None,
                            "trust": {
                                "ods_code": "RVY",
                                "name": "SOUTHPORT AND ORMSKIRK HOSPITAL NHS TRUST",
                            },
                            "local_health_board": None,
                            "integrated_care_board": {
                                "ods_code": "QYG",
                                "name": "NHS CHESHIRE AND MERSEYSIDE INTEGRATED CARE BOARD",
                            },
                            "nhs_england_region": {
                                "region_code": "Y62",
                                "name": "North West",
                            },
                            "openuk_network": {
                                "boundary_identifier": "EPIC",
                                "name": "Mersey and North Wales network 'Epilepsy In Childhood' interest group",
                            },
                            "paediatric_diabetes_unit": {"pz_code": "PZ110"},
                            "predecessor_ods_code": None,
                            "successor_ods_code": "RBN52",
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        "Forward walk — predecessor queried after succession date",
                        summary="Query the old code at a date after the succession",
                        description=(
                            "The resolved entity is the successor. "
                            "`predecessor_ods_code` is the queried code; "
                            "`successor_ods_code` is null (the resolved "
                            "successor is still live). The consumer detects "
                            "a walk by comparing `ods_code` to the queried "
                            "code."
                        ),
                        value={
                            "ods_code": "RBN52",
                            "snapshot_date": "2024-01-01",
                            "name": "ORMSKIRK AND DISTRICT GENERAL HOSPITAL",
                            "address1": "WIGAN ROAD",
                            "address2": None,
                            "address3": None,
                            "telephone": None,
                            "city": "ORMSKIRK",
                            "county": "LANCASHIRE",
                            "postcode": "L39 2AZ",
                            "latitude": None,
                            "longitude": None,
                            "active": True,
                            "published_at": None,
                            "trust": {
                                "ods_code": "RBN",
                                "name": "MERSEY AND WEST LANCASHIRE TEACHING HOSPITALS NHS TRUST",
                            },
                            "local_health_board": None,
                            "integrated_care_board": {
                                "ods_code": "QYG",
                                "name": "NHS CHESHIRE AND MERSEYSIDE INTEGRATED CARE BOARD",
                            },
                            "nhs_england_region": {
                                "region_code": "Y62",
                                "name": "North West",
                            },
                            "openuk_network": {
                                "boundary_identifier": "EPIC",
                                "name": "Mersey and North Wales network 'Epilepsy In Childhood' interest group",
                            },
                            "paediatric_diabetes_unit": {"pz_code": "PZ110"},
                            "predecessor_ods_code": "RVY02",
                            "successor_ods_code": None,
                        },
                        response_only=True,
                    ),
                ],
            ),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description=(
                    "The organisation (or any entity in the succession "
                    "chain) did not exist on the given date, the queried "
                    "ODS code is not in the database, or the queried code "
                    "was split into multiple successors (ambiguous — use "
                    "the detail endpoint's `successors` array to pick)."
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
