from django.apps import apps
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework import serializers

from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema_serializer,
    OpenApiExample,
)

from ..models import (
    Organisation,
    IntegratedCareBoard,
    LocalHealthBoard,
    LondonBorough,
    NHSEnglandRegion,
    Trust,
    PaediatricDiabetesUnit,
)

from .country import CountryLimitedSerializer
from .integrated_care_board import (
    IntegratedCareBoardLimitedSerializer,
)
from .local_authority_district import LocalAuthorityDistrictSerializer
from .local_health_board import (
    LocalHealthBoardSerializer,
    LocalHealthBoardLimitedSerializer,
)
from .london_borough import LondonBoroughLimitedSerializer
from .lower_layer_super_output_area import LowerLayerSuperOutputAreaSerializer
from .nhs_england_region import (
    NHSEnglandRegionLimitedSerializer,
)
from .openuk_network import OPENUKNetworkSerializer
from .paediatric_diabetes_unit import (
    PaediatricDiabetesUnitWIthNestedPaediatricDiabetesNetworkSerializer,
)
from .trust import TrustSerializer, LimitedTrustSerializer


class OrganisationGeoJSONSerializer(GeoFeatureModelSerializer):
    # Serializes an organisation, nest in all related parent details (without boundaries)
    trust = TrustSerializer()
    local_health_board = LocalHealthBoardLimitedSerializer()
    integrated_care_board = IntegratedCareBoardLimitedSerializer()
    nhs_england_region = NHSEnglandRegionLimitedSerializer()
    openuk_network = OPENUKNetworkSerializer()
    paediatric_diabetes_unit = (
        PaediatricDiabetesUnitWIthNestedPaediatricDiabetesNetworkSerializer()
    )
    london_borough = LondonBoroughLimitedSerializer()
    country = CountryLimitedSerializer()
    lower_layer_super_output_area = LowerLayerSuperOutputAreaSerializer()
    local_authority_district = LocalAuthorityDistrictSerializer()

    class Meta:
        model = Organisation
        geo_field = "geocode_coordinates"
        fields = [
            "ods_code",
            "name",
            "website",
            "address1",
            "address2",
            "address3",
            "telephone",
            "city",
            "county",
            "latitude",
            "longitude",
            "postcode",
            "geocode_coordinates",
            "active",
            "published_at",
            "local_authority_district",
            "lower_layer_super_output_area",
            "paediatric_diabetes_unit",
            "trust",
            "local_health_board",
            "integrated_care_board",
            "nhs_england_region",
            "openuk_network",
            "london_borough",
            "country",
        ]
        depth = 1


class OrganisationSerializer(serializers.ModelSerializer):
    # Serializes an organisation, nest in all related parent details (without boundaries)
    trust = TrustSerializer()
    local_health_board = LocalHealthBoardLimitedSerializer()
    integrated_care_board = IntegratedCareBoardLimitedSerializer()
    nhs_england_region = NHSEnglandRegionLimitedSerializer()
    openuk_network = OPENUKNetworkSerializer()
    paediatric_diabetes_unit = (
        PaediatricDiabetesUnitWIthNestedPaediatricDiabetesNetworkSerializer()
    )
    london_borough = LondonBoroughLimitedSerializer()
    country = CountryLimitedSerializer()
    lower_layer_super_output_area = LowerLayerSuperOutputAreaSerializer()
    local_authority_district = LocalAuthorityDistrictSerializer()

    class Meta:
        model = Organisation
        fields = [
            "ods_code",
            "name",
            "website",
            "address1",
            "address2",
            "address3",
            "telephone",
            "city",
            "county",
            "latitude",
            "longitude",
            "postcode",
            "geocode_coordinates",
            "active",
            "published_at",
            "local_authority_district",
            "lower_layer_super_output_area",
            "paediatric_diabetes_unit",
            "trust",
            "local_health_board",
            "integrated_care_board",
            "nhs_england_region",
            "openuk_network",
            "london_borough",
            "country",
        ]
        depth = 1


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/organisation/limited/1/",
            value={
                "ods_code": "RGT01",
                "name": "ADDENBROOKE'S HOSPITAL",
            },
            response_only=True,
        )
    ]
)
class OrganisationNoParentsSerializer(serializers.ModelSerializer):
    # used to serialize all child organisations in the TrustSerializer
    # returns only ods_code and name
    class Meta:
        model = Organisation
        fields = [
            "ods_code",
            "name",
        ]


class OrganisationTrustLHBParentSerializer(serializers.ModelSerializer):
    # used to serialize all child organisations and associated parent details
    # returns only ods_code and name
    class Meta:
        model = Organisation
        fields = ["ods_code", "name", "trust", "local_health_board"]
        depth = 1


class TrustWithNestedOrganisationsSerializer(serializers.ModelSerializer):
    # used to return all Trust fields as well as all related child organisations
    # nested in
    organisations = OrganisationNoParentsSerializer(
        many=True, read_only=True, source="trust_organisations"
    )

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
            "organisations",
        ]


class IntegratedCareBoardWithNestedOrganisationsSerializer(serializers.ModelSerializer):
    # used to return key ICB fields as well as all related child organisation names and ods_codes
    # nested in
    organisations = OrganisationNoParentsSerializer(
        many=True, read_only=True, source="integrated_care_board_organisations"
    )

    class Meta:
        model = IntegratedCareBoard
        # depth = 1
        fields = [
            "boundary_identifier",
            "name",
            "ods_code",
            "publication_date",
            "organisations",
        ]


class NHSEnglandRegionWithNestedOrganisationsSerializer(serializers.ModelSerializer):
    # used to return key ICB fields as well as all related child organisation names and ods_codes
    # nested in
    organisations = OrganisationNoParentsSerializer(
        many=True, read_only=True, source="nhs_england_region_organisations"
    )

    class Meta:
        model = NHSEnglandRegion
        # depth = 1
        fields = [
            "region_code",
            "publication_date",
            "boundary_identifier",
            "name",
            "organisations",
        ]


class NHSEnglandRegionWithNestedTrustsSerializer(serializers.ModelSerializer):
    # Used to return all Trusts within an NHS England Region
    # Note the use of distinct() to avoid duplicate Trusts since the middle table is Organisation
    # which can have multiple entries for the same Trust
    trusts = serializers.SerializerMethodField()

    class Meta:
        model = NHSEnglandRegion
        fields = [
            "region_code",
            "publication_date",
            "boundary_identifier",
            "name",
            "trusts",
        ]

    def get_trusts(self, obj):
        trusts = Trust.objects.filter(
            trust_organisations__nhs_england_region=obj
        ).distinct()
        return LimitedTrustSerializer(trusts, many=True).data


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/london_borough/1/organisation",
            value={
                "name": "",
                "gss_code": "",
            },
            response_only=True,
        )
    ]
)
class LondonBoroughWithNestedOrganisationsSerializer(serializers.ModelSerializer):
    organisations = OrganisationNoParentsSerializer(
        many=True, read_only=True, source="london_borough_organisations"
    )

    class Meta:
        model = LondonBorough
        fields = ["name", "gss_code", "organisations"]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/local_health_board/1/organisations",
            value={
                "ods_code": "",
                "boundary_identifier": "",
                "name": "",
            },
            response_only=True,
        )
    ]
)
class LocalHealthBoardOrganisationsSerializer(serializers.ModelSerializer):
    # returns local health boards with only ods_code and name and nested organisations
    organisations = OrganisationNoParentsSerializer(
        many=True, read_only=True, source="local_health_board_organisations"
    )

    class Meta:
        model = LocalHealthBoard
        # depth = 1
        fields = [
            "ods_code",
            "boundary_identifier",
            "name",
            "organisations",
        ]


class OrganisationWithLSOAAndLADSerializer(serializers.ModelSerializer):
    # serializes an organisation with its LSOA and LAD

    lower_layer_super_output_area = serializers.SerializerMethodField()
    local_authority_district = serializers.SerializerMethodField()

    def get_lower_layer_super_output_area(self, obj):
        if obj.lower_layer_super_output_area is not None:
            return LowerLayerSuperOutputAreaSerializer(
                obj.lower_layer_super_output_area
            ).data
        else:
            return None

    def get_local_authority_district(self, obj):
        if obj.local_authority_district is not None:
            return LocalAuthorityDistrictSerializer(obj.local_authority_district).data
        else:
            return None

    class Meta:
        model = Organisation
        fields = [
            "ods_code",
            "name",
            "lower_layer_super_output_area",
            "local_authority_district",
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/paediatric_diabetes_unit/1/organisations",
            value={"pz_code": "", "organisations": []},
            response_only=True,
        )
    ]
)
class PaediatricDiabetesUnitWithNestedOrganisationSerializer(
    serializers.ModelSerializer
):
    organisations = OrganisationWithLSOAAndLADSerializer(
        many=True, read_only=True
    )

    class Meta:
        model = PaediatricDiabetesUnit
        fields = ["pz_code", "organisations", "active", "updated_at", "name"]


# Returns an organisation with its parent LHB or Trust details
@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "/paediatric_diabetes_unit/1/organisations",
            value={"ods_code": "", "parent": "Trust/Local Health Board"},
            response_only=True,
        )
    ]
)
class OrganisationWithParentSerializer(GeoFeatureModelSerializer):
    parent = serializers.SerializerMethodField()

    class Meta:
        geo_field = "geom"
        model = Organisation
        fields = ["ods_code", "name", "parent"]

    def get_parent(self, obj):
        if obj.trust is not None:
            return TrustSerializer(obj.trust).data
        elif obj.local_health_board is not None:
            return LocalHealthBoardSerializer(obj.local_health_board).data
        else:
            return None


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "paediatric_diabetes_units/sibling-organisations/RGT01/",
            value={"pz_code": "", "organisations": []},
            response_only=True,
        )
    ]
)
class PaediatricDiabetesUnitWithNestedOrganisationAndParentSerializer(
    GeoFeatureModelSerializer
):
    organisations = OrganisationWithParentSerializer(
        many=True, read_only=True
    )

    class Meta:
        geo_field = "geom"
        model = PaediatricDiabetesUnit
        fields = ["pz_code", "organisations", "active", "updated_at", "name"]
