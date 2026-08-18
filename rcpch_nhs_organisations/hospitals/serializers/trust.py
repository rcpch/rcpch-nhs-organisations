import logging

# Django
from django.apps import apps

# Third-party
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from .local_health_board import LocalHealthBoardLimitedSerializer

Organisation = apps.get_model("hospitals", "Organisation")
PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")
Trust = apps.get_model("hospitals", "Trust")

logger = logging.getLogger(__name__)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/trust/1/",
            value={
                "ods_code": "",
                "name": "",
                "address_line_1": "",
                "address_line_2": "",
                "town": "",
                "postcode": "",
                "country": "",
                "telephone": "",
                "website": "",
                "active": "",
                "published_at": "",
            },
            response_only=True,
        )
    ]
)
class TrustSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trust
        # depth = 1
        fields = [
            "ods_code",
            "name",
            "address_line_1",
            "address_line_2",
            "town",
            "postcode",
            "country",
            "telephone",
            "website",
            "active",
            "published_at",
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "paediatric_diabetes_units/parent/",
            value={
                "pz_code": "PZ002",
                "paediatric_diabetes_network": {
                    "pn_code": "PN06",
                    "name": "East of England",
                },
                "parent": {
                    "ods_code": "RM1",
                    "name": "NORFOLK AND NORWICH UNIVERSITY HOSPITALS NHS FOUNDATION TRUST",
                    "address_line_1": "COLNEY LANE",
                    "address_line_2": "COLNEY",
                    "town": "NORWICH",
                    "postcode": "NR4 7UY",
                    "country": "ENGLAND",
                    "telephone": None,
                    "website": None,
                    "active": True,
                    "published_at": None,
                },
                "primary_organisation": {
                    "ods_code": "RM102",
                    "name": "NORFOLK & NORWICH UNIVERSITY HOSPITAL",
                },
            },
            response_only=True,
        )
    ]
)
class PaediatricDiabetesUnitWithNestedParentSerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()
    primary_organisation = serializers.SerializerMethodField()
    paediatric_diabetes_network = serializers.SerializerMethodField()

    class Meta:
        model = PaediatricDiabetesUnit
        fields = [
            "pz_code",
            "paediatric_diabetes_network",
            "parent",
            "primary_organisation",
            "updated_at",
            "active",
            "name"
        ]

    def get_parent(self, obj):
        try:
            pdu = PaediatricDiabetesUnit.objects.get(pz_code=obj.pz_code)
        except PaediatricDiabetesUnit.DoesNotExist:
            return None

        # Inactive predecessor PDUs whose child organisations have been
        # reassigned to a successor trust. The historical parent is looked up
        # directly by ODS code because the organisations may now be linked to a
        # different trust and have not changed ODS code.
        #
        # NOTE: this is a stop-gap pending the temporal history layer. Once
        # the predecessor PDUs and their OrganisationPaediatricDiabetesUnit-
        # Membership rows exist in the history layer, the parent for an
        # inactive PDU can be resolved as-of its last active date via the
        # membership tables, and this hardcoded map can be removed. Until
        # then, leave it in place — removing it would return the wrong parent
        # (or null) for these inactive PDUs.
        inactive_pdu_to_trust_mapping = {
            # PZ003 was split into PZ251 (Pinderfields General Hospital) and PZ252 (Pontefract General Infirmary) on 05/04/2025
            "PZ003": "RXF",
            # PZ216 (THE TUNBRIDGE WELLS HOSPITAL) merged into PZ253 MAIDSTONE AND TUNBRIDGE WELLS NHS TRUST (Jan 25)
            "PZ216": "RWF",
            # PZ125 (THE MAIDSTONE HOSPITAL) merged into PZ253 MAIDSTONE AND TUNBRIDGE WELLS NHS TRUST (Jan 25)
            "PZ125": "RWF",
            # PZ080 (SUNDERLAND ROYAL HOSPITAL) merged into PZ250 SOUTH TYNESIDE AND SUNDERLAND NHS FOUNDATION TRUST (Mar 25)
            "PZ080": "R0B",
            # PZ141 (SOUTH TYNESIDE DISTRICT GENERAL HOSPITAL) merged into PZ250 SOUTH TYNESIDE AND SUNDERLAND NHS FOUNDATION TRUST (Mar 25)
            "PZ141": "R0B",
        }

        if obj.pz_code in inactive_pdu_to_trust_mapping:
            trust_ods_code = inactive_pdu_to_trust_mapping[obj.pz_code]
            trust = Trust.objects.get(ods_code=trust_ods_code)
            return TrustSerializer(trust).data

        # Derive the parent from the PDU's lead/primary organisation, not an
        # arbitrary .first() child. A PDU's child organisations can span
        # multiple trusts after a split (e.g. PZ247 has sites under both R0A
        # Manchester University and RM3 Northern Care Alliance); picking the
        # first child in default ordering returned whichever happened to sort
        # first, which was wrong. The lead_organisation FK is the source of
        # truth for which site identifies the PDU, and is exposed as
        # primary_organisation on this same endpoint.
        primary = pdu.primary_organisation
        if primary is None:
            return None

        trust = getattr(primary, "trust", None)
        local_health_board = getattr(primary, "local_health_board", None)

        if trust and primary.country.boundary_identifier in [
            "E92000001",
            "JEY",
            "M83000003",
        ]:  # England / Jersey / Isle of Man
            return TrustSerializer(trust).data
        elif (
            local_health_board
            and primary.country.boundary_identifier == "W92000004"
        ):  # Wales
            return LocalHealthBoardLimitedSerializer(local_health_board).data

        return None

    def get_paediatric_diabetes_network(self, obj):
        # prevents circular import
        from rcpch_nhs_organisations.hospitals.serializers.paediatric_diabetes_network import (
            PaediatricDiabetesNetworkSerializer,
        )

        network = obj.paediatric_diabetes_network
        if network:
            return PaediatricDiabetesNetworkSerializer(network).data
        return None

    def get_primary_organisation(self, obj):
         # prevents circular import
        from rcpch_nhs_organisations.hospitals.serializers.organisation import (
            OrganisationNoParentsSerializer,
        )

        primary_organisation = obj.primary_organisation
        if primary_organisation:
            return OrganisationNoParentsSerializer(primary_organisation).data


class LimitedTrustSerializer(serializers.ModelSerializer):

    class Meta:
        model = Trust
        fields = [
            "ods_code",
            "name",
        ]
