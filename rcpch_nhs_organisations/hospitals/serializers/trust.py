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
    name = serializers.SerializerMethodField()

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
        # there are deprecated PDUs that don't have an organisation
        if PaediatricDiabetesUnit.objects.filter(pz_code=obj.pz_code).exists():
            pdu = PaediatricDiabetesUnit.objects.get(pz_code=obj.pz_code)
        else:
            return None

        try:
            # all related organisations for that PaediatricDiabetesUnit should have the same parent
            # so we can just get the first one
            organisation = Organisation.objects.filter(
                paediatric_diabetes_unit=pdu
            ).first()
        except Organisation.DoesNotExist:
            return None

        if not organisation:  # No related organisations found
            return None

        trust = getattr(organisation, "trust", None)
        local_health_board = getattr(organisation, "local_health_board", None)

        if trust and organisation.country.boundary_identifier in [
            "E92000001",
            "E92000003",
        ]:  # England / Jersey
            return TrustSerializer(trust).data
        elif (
            local_health_board
            and organisation.country.boundary_identifier == "W92000004"
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

        return OrganisationNoParentsSerializer(obj.primary_organisation).data

    def get_name(self, obj):
        return obj.name or obj.primary_organisation.name

    def to_representation(self, instance):
        # Avoid multiple queries for primary organisation
        instance.primary_organisation = self._get_primary_organisation(instance)

        return super().to_representation(instance)

    def _get_primary_organisation(self, obj):
        organisations = Organisation.objects.filter(paediatric_diabetes_unit=obj).all()

        if not organisations.exists():
            return None

        if organisations.count() > 1:
            if obj.pz_code == "PZ024":
                # RPF01 is the parent organisation for PZ024 (William Harvey Hospital, Ashford)
                return organisations.filter(ods_code="RVV01").get()
            elif obj.pz_code == "PZ050":
                # RPF01 is the parent organisation for PZ024 (Queen Mary's Hospital for Children, Carshalton)
                return organisations.filter(ods_code="RVR07").get()
            elif obj.pz_code == "PZ099":
                # RPF01 is the parent organisation for PZ099 (Lister Hospital, Stevenage)
                return organisations.filter(ods_code="RWH01").get()
            elif obj.pz_code == "PZ136":
                # RPF01 is the parent organisation for PZ099 (Manchester Children's Hospital)
                return organisations.filter(ods_code="R0A03").get()
            elif obj.pz_code == "PZ206":
                # RM401 is the parent organisation for PZ206 (Trafford General Hospital)
                return organisations.filter(ods_code="RM321").get()
            elif obj.pz_code == "PZ230":
                # RM230 is the parent organisation for PZ230 (Conquest Hospital, Hastings)
                return organisations.filter(ods_code="RXC01").get()
            elif obj.pz_code == "PZ249":
                # PZ249 is South Tees Hospital NHS Foundation Trust
                return organisations.filter(ods_code="RTRAT").get()
            elif obj.pz_code == "PZ250":
                #  PZ250 is Sunderland Royal Hospital (R0B01) and South Tyneside District General Hospital (R0B0Q)
                return organisations.filter(ods_code="R0B01").get()  # Sunderland Royal Hospital
            elif obj.pz_code == "PZ242":
                # PZ242 is GLOUCESTERSHIRE HOSPITALS NHS FOUNDATION TRUST
                #  - RTE01	CHELTENHAM GENERAL HOSPITAL 
                #  - RTE03	GLOUCESTERSHIRE ROYAL HOSPITAL (lead)
                return organisations.filter(ods_code="RTE03").get()  # GLOUCESTERSHIRE ROYAL HOSPITAL
            else:
                return organisations.first()
        else:
            return organisations.get()


class LimitedTrustSerializer(serializers.ModelSerializer):

    class Meta:
        model = Trust
        fields = [
            "ods_code",
            "name",
        ]
