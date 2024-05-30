# django
from django.contrib.gis.db import models
from django.contrib.gis.db.models import (
    PointField,
    CharField,
    FloatField,
    BooleanField,
)

# 3rd party
from .time_and_user_abstract_base_classes import TimeStampAbstractBaseClass
from .country import Country
from .paediatric_diabetes_unit import PaediatricDiabetesUnit
from .trust import Trust
from .local_health_board import LocalHealthBoard
from .integrated_care_board import IntegratedCareBoard
from .nhs_england_region import NHSEnglandRegion
from .open_uk_network import OPENUKNetwork
from .london_borough import LondonBorough


class Organisation(TimeStampAbstractBaseClass):
    """
    This class details information about organisations.
    It represents a list of organisations that can be looked up
    """

    ods_code = CharField(max_length=100, unique=True, null=False, blank=False)
    name = CharField(max_length=100, null=True, blank=True, default=None)
    website = CharField(max_length=100, null=True, blank=True, default=None)
    address1 = CharField(max_length=100, null=True, blank=True, default=None)
    address2 = CharField(max_length=100, null=True, blank=True, default=None)
    address3 = CharField(max_length=100, null=True, blank=True, default=None)
    telephone = CharField(max_length=100, null=True, blank=True, default=None)
    city = CharField(max_length=100, null=True, blank=True, default=None)
    county = CharField(max_length=100, null=True, blank=True, default=None)
    latitude = FloatField(max_length=100, null=True, blank=True, default=None)
    longitude = FloatField(null=True, blank=True, default=None)
    postcode = CharField(max_length=10, null=True, blank=True, default=None)
    geocode_coordinates = PointField(null=True, blank=True, default=None, srid=27700)

    active = BooleanField(
        default=True
    )  # a boolean representing if this Organisation is still operational

    published_at = models.DateField(
        null=True, blank=True, default=None
    )  # date this Organisation was last amended according to the ORD

    paediatric_diabetes_unit = models.ForeignKey(
        to=PaediatricDiabetesUnit,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name="paediatric_diabetes_unit_organisations",
    )

    trust = models.ForeignKey(
        to=Trust,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name="trust_organisations",
    )
    local_health_board = models.ForeignKey(
        to=LocalHealthBoard,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name="local_health_board_organisations",
    )
    integrated_care_board = models.ForeignKey(
        to=IntegratedCareBoard,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name="integrated_care_board_organisations",
    )
    nhs_england_region = models.ForeignKey(
        to=NHSEnglandRegion,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name="nhs_england_region_organisations",
    )
    openuk_network = models.ForeignKey(
        to=OPENUKNetwork,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name="openuk_network_organisations",
    )
    # administrative regions
    london_borough = models.ForeignKey(
        to=LondonBorough,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name="london_borough_organisations",
    )

    country = models.ForeignKey(
        to=Country,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="country_organisations",
    )

    @property
    def _history_user(self):
        return self.updated_by

    @_history_user.setter
    def _history_user(self, value):
        self.updated_by = value

    class Meta:
        indexes = [models.Index(fields=["name"])]
        verbose_name = "Organisation"
        verbose_name_plural = "Organisations"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name
