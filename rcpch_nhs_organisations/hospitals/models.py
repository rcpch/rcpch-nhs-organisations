from django.db import models
from django.utils.translation import gettext_lazy as _


class Geocode:
    def __init__(self, type, coordinates, crs):
        self.type = type
        self.coordinates = coordinates
        self.crs = crs

    def to_dict(self):
        return {
            "type": self.type,
            "coordinates": self.coordinates,
            "crs": self.crs,
        }


class GeocodeField(models.Field):
    def from_db_value(self, value, expression, connection):
        db_val = super().from_db_value(value, expression, connection)

        if db_val is None:
            return db_val

        return Geocode(**db_val)

    def get_prep_value(self, value):
        dict_value = value.to_dict()
        prep_value = super().get_prep_value(dict_value)
        return prep_value


class ParentOrganisation:
    def __init__(self, ODSCode, OrganisationName):
        self.ODSCode = ODSCode
        self.OrganisationName = OrganisationName

    def to_dict(self):
        return {
            "ODSCode": self.ODSCode,
            "OrganisationName": self.OrganisationName,
        }


class ParentOrganisationField(models.Field):
    def from_db_value(self, value, expression, connection):
        db_val = super().from_db_value(value, expression, connection)

        if db_val is None:
            return db_val

        return ParentOrganisation(**db_val)

    def get_prep_value(self, value):
        dict_value = value.to_dict()
        prep_value = super().get_prep_value(dict_value)
        return prep_value


class AcceptingPatients:
    def __init__(self, GP, Dentist):
        self.GP = GP
        self.Dentist = Dentist

    def to_dict(self):
        return {
            "ODSCode": self.ODSCode,
            "OrganisationName": self.OrganisationName,
        }


class AcceptingPatientsField(models.Field):
    def from_db_value(self, value, expression, connection):
        db_val = super().from_db_value(value, expression, connection)

        if db_val is None:
            return db_val

        return AcceptingPatients(**db_val)

    def get_prep_value(self, value):
        dict_value = value.to_dict()
        prep_value = super().get_prep_value(dict_value)
        return prep_value


class LastUpdatedDates:
    def __init__(
        self,
        OpeningTimes,
        BankHolidayOpeningTimes,
        DentistsAcceptingPatients,
        Facilities,
        HospitalDepartment,
        Services,
        ContactDetails,
        AcceptingPatients,
    ):
        self.OpeningTimes = OpeningTimes
        self.BankHolidayOpeningTimes = BankHolidayOpeningTimes
        self.DentistsAcceptingPatients = DentistsAcceptingPatients
        self.Facilities = Facilities
        self.HospitalDepartment = HospitalDepartment
        self.Services = Services
        self.ContactDetails = ContactDetails
        self.AcceptingPatients = AcceptingPatients

    def to_dict(self):
        return {
            "OpeningTimes": self.OpeningTimes,
            "BankHolidayOpeningTimes": self.BankHolidayOpeningTimes,
            "DentistsAcceptingPatients": self.DentistsAcceptingPatients,
            "Facilities": self.Facilities,
            "HospitalDepartment": self.HospitalDepartment,
            "Services": self.Services,
            "ContactDetails": self.ContactDetails,
            "AcceptingPatients": self.AcceptingPatients,
            "BankHolidayOpeningTimes": self.BankHolidayOpeningTimes,
            "DentistsAcceptingPatients": self.DentistsAcceptingPatients,
            "Facilities": self.Facilities,
            "HospitalDepartment": self.HospitalDepartment,
            "Services": self.Services,
            "ContactDetails": self.ContactDetails,
            "AcceptingPatients": self.AcceptingPatients,
        }


class LastUpdatedDatesField(models.Field):
    def from_db_value(self, value, expression, connection):
        db_val = super().from_db_value(value, expression, connection)

        if db_val is None:
            return db_val

        return LastUpdatedDates(**db_val)

    def get_prep_value(self, value):
        dict_value = value.to_dict()
        prep_value = super().get_prep_value(dict_value)
        return prep_value


class Service(models.Model):
    ServiceName = models.CharField(max_length=100, unique=False)
    ServiceCode = models.CharField(max_length=100, unique=False)
    ServiceDescription = models.CharField(max_length=250)
    # ServiceProvider = ServiceProvider()
    # Treatments = models.CharField(max_length=250)
    OpeningTimes = models.CharField(max_length=250)
    AgeRange = models.CharField(max_length=250)
    Metrics = models.CharField(max_length=250)


class ServiceProvider(models.Model):
    ODSCode = models.CharField(max_length=100, unique=False)
    OrganisationName = models.CharField(max_length=100, unique=False)
    service = models.OneToOneField(
        Service,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="ServiceProvider",
    )


class Organisation(models.Model):
    ODSCode = models.CharField(max_length=50, unique=True)
    OrganisationName = models.CharField(max_length=250)
    OrganisationTypeId = models.CharField(max_length=250)
    OrganisationType = models.CharField(max_length=250)
    OrganisationStatus = models.CharField(max_length=250)
    SummaryText = models.CharField(max_length=250)
    URL = models.CharField(max_length=250)
    Address1 = models.CharField(max_length=250)
    Address2 = models.CharField(max_length=250)
    Address3 = models.CharField(max_length=250)
    City = models.CharField(max_length=250)
    County = models.CharField(max_length=250)
    Latitude = models.CharField(max_length=250)
    Longitude = models.CharField(max_length=250)
    Postcode = models.CharField(max_length=250)
    Geocode = GeocodeField()
    OrganisationSubType = models.CharField(max_length=250)
    # OrganisationAliases = models.CharField(max_length=250)
    ParentOrganisation = ParentOrganisationField()
    # Services = models.ForeignKey(Service, on_delete=models.CASCADE)
    OpeningTimes = models.CharField(max_length=250)
    # Contacts = models.CharField(max_length=250)
    # Facilities = models.CharField(max_length=250)
    Staff = models.CharField(max_length=250)
    GSD = models.CharField(max_length=250)
    # LastUpdatedDates = LastUpdatedDatesField()
    # AcceptingPatients = AcceptingPatientsField()
    GPRegistration = models.CharField(max_length=250)
    CCG = models.CharField(max_length=250)
    RelatedIAPTCCGs = models.CharField(max_length=250)
    CCGLocalAuthority = models.CharField(max_length=250)
    Trusts = models.CharField(max_length=250)
    # Metrics = models.CharField(max_length=250)


class Contact(models.Model):
    ContactMethodType = models.CharField(max_length=100, unique=False)
    ContactValue = models.CharField(max_length=100, unique=False)
    ContactType = models.CharField(max_length=100, unique=False)
    ContactAvailabilityType = models.CharField(max_length=100, unique=False)
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="Contacts",
        blank=True,
        null=True,
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="Services",
        blank=True,
        null=True,
    )


class Treatment(models.Model):
    name = models.CharField(max_length=250, unique=True)
    service = models.ForeignKey(
        Service, on_delete=models.CASCADE, related_name="Treatments"
    )


class OrganisationAlias(models.Model):
    OrganisationAlias = models.CharField(max_length=100, unique=False)
    OrganisationAliasId = models.CharField(max_length=50, unique=True)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, blank=True, null=True
    )


class Facility(models.Model):
    Id = models.IntegerField()
    Name = models.CharField(max_length=100)
    Value = models.CharField(max_length=50)
    FacilityGroupName = models.CharField(max_length=100)
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="facilities",
        blank=True,
        null=True,
    )


class Metric(models.Model):
    MetricID = models.IntegerField()
    MetricName = models.CharField(max_length=100)
    DisplayName = models.CharField(max_length=100)
    Description = models.CharField(max_length=100)
    Value = models.CharField(max_length=100)
    Value2 = models.CharField(max_length=100)
    Value3 = models.CharField(max_length=100)
    Text = models.CharField(max_length=250)
    LinkUrl = models.CharField(max_length=100)
    LinkText = models.CharField(max_length=100)
    MetricDisplayTypeID = models.IntegerField
    MetricDisplayTypeName = models.CharField(max_length=100)
    HospitalSectorType = models.CharField(max_length=100)
    MetricText = models.CharField(max_length=100)
    DefaultText = models.CharField(max_length=100)
    IsMetaMetric = models.BooleanField(blank=True, null=True)
    BandingClassification = models.CharField(max_length=100)
    BandingName = models.CharField(max_length=100)
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="Metrics",
    )
