from rest_framework import serializers
from django.apps import apps

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from .local_health_board import LocalHealthBoardLimitedSerializer

Organisation = apps.get_model("hospitals", "Organisation")
PaediatricDiabetesUnit = apps.get_model("hospitals", "PaediatricDiabetesUnit")
Trust = apps.get_model("hospitals", "Trust")


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
            "paediatric_diabetes_units/trust/",
            value={"pz_code": "", "trust": []},
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
        ]

    def get_parent(self, obj):
        try:
            # all related organisations for that PaediatricDiabetesUnit should have the same parent
            # so we can just get the first one
            organisation = Organisation.objects.filter(
                paediatric_diabetes_unit=obj
            ).first()
        except Organisation.DoesNotExist:
            return None

        if organisation.trust:
            return TrustSerializer(organisation.trust).data
        elif organisation.local_health_board:
            return LocalHealthBoardLimitedSerializer(
                organisation.local_health_board
            ).data
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

        try:
            organisations = Organisation.objects.filter(
                paediatric_diabetes_unit=obj
            ).all()
        except Organisation.DoesNotExist:
            return None

        if organisations.count() > 1:
            if obj.pz_code == "PZ024":
                # RPF01 is the parent organisation for PZ024 (William Harvey Hospital, Ashford)
                return OrganisationNoParentsSerializer(
                    organisations.filter(ods_code="RVV01").get()
                ).data
            elif obj.pz_code == "PZ050":
                # RPF01 is the parent organisation for PZ024 (Queen Mary's Hospital for Children, Carshalton)
                return OrganisationNoParentsSerializer(
                    organisations.filter(ods_code="RVR07").get()
                ).data
            elif obj.pz_code == "PZ099":
                # RPF01 is the parent organisation for PZ099 (Lister Hospital, Stevenage)
                return OrganisationNoParentsSerializer(
                    organisations.filter(ods_code="RWH01").get()
                ).data
            elif obj.pz_code == "PZ136":
                # RPF01 is the parent organisation for PZ099 (Manchester Children's Hospital)
                return OrganisationNoParentsSerializer(
                    organisations.filter(ods_code="R0A03").get()
                ).data
            elif obj.pz_code == "PZ206":
                # RM401 is the parent organisation for PZ206 (Trafford General Hospital)
                return OrganisationNoParentsSerializer(
                    organisations.filter(ods_code="RM321").get()
                ).data
            elif obj.pz_code == "PZ230":
                # RM230 is the parent organisation for PZ230 (Conquest Hospital, Hastings)
                return OrganisationNoParentsSerializer(
                    organisations.filter(ods_code="RXC01").get()
                ).data
            else:
                return OrganisationNoParentsSerializer(organisations.first()).data
        else:
            return OrganisationNoParentsSerializer(organisations.get()).data
