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
    If the organisation did not exist on `on_date` (its first valid_from is
    after that date), walk the OrganisationSuccession chain backwards to find
    the predecessor that was in force on that date.
    """
    first_version = organisation.versions.order_by("valid_from").first()
    if first_version is None or first_version.valid_from <= on_date:
        return organisation

    # Walk backwards through succession links.
    current = organisation
    visited = set()
    while current.pk not in visited:
        visited.add(current.pk)
        link = current.succession_successor_links.first()
        if link is None:
            return None
        current = link.predecessor
        first_version = current.versions.order_by("valid_from").first()
        if first_version is None:
            return None
        if first_version.valid_from <= on_date:
            # Check the predecessor was still in force on on_date (valid_to
            # is null or after on_date).
            if first_version.valid_to is None or first_version.valid_to > on_date:
                return current
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
            "name": trust.name,
        } if trust else None,
        "local_health_board": {
            "ods_code": local_health_board.ods_code,
            "name": local_health_board.name,
        } if local_health_board else None,
        "integrated_care_board": {
            "ods_code": integrated_care_board.ods_code,
            "name": integrated_care_board.name,
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
    Returns a snapshot of an organisation and all its relationships as they
    were on a given date. If the organisation did not exist on that date but a
    predecessor (linked via OrganisationSuccession) did, the predecessor's
    state is returned with `predecessor_ods_code` populated.

    This is the endpoint used by national audits to report longitudinal data
    against the organisational geography that was in force at the time the
    data was collected.

    See documentation/docs/developer/temporal-history.md for the design.
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    "The date to snapshot. If omitted, returns the current "
                    "state. Format: YYYY-MM-DD."
                ),
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Organisation snapshot",
            ),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Organisation not found, or no state exists for the given date.",
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
