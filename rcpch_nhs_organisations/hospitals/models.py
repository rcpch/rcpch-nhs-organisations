from django.db import models
from django.utils.translation import gettext_lazy as _


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
    OrganisationSubType = models.CharField(max_length=250)
    # OrganisationAliases = models.CharField(max_length=250)
    # ParentOrganisation = ParentOrganisationField()
    # Services = models.ForeignKey(Service, on_delete=models.CASCADE)
    # OpeningTimes = models.CharField(max_length=250)
    # Contacts = models.CharField(max_length=250)
    # Facilities = models.CharField(max_length=250)
    Staff = models.CharField(max_length=250)
    GSD = models.CharField(max_length=250)
    # LastUpdatedDates = LastUpdatedDatesField()
    AcceptingPatients = models.JSONField()
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


class Geocode(models.Model):
    type = models.CharField(max_length=100, unique=False)
    coordinates = models.CharField(max_length=100, unique=False)
    crs = models.JSONField(max_length=100, unique=False)
    organisation = models.OneToOneField(
        Organisation, on_delete=models.CASCADE, blank=True, null=True)


class ParentOrganisation(models.Model):
    ODSCode = models.CharField(max_length=100, unique=False)
    OrganisationName = models.CharField(max_length=100, unique=False)
    organisation = models.OneToOneField(
        Organisation, on_delete=models.CASCADE, blank=True, null=True, related_name='ParentOrganisation')


class OpeningTime(models.Model):
    Weekday = models.CharField(
        max_length=50, unique=False, blank=True, null=True)
    Times = models.DateTimeField(unique=False, blank=True, null=True)
    OpeningTime = models.DateTimeField(unique=False, blank=True, null=True)
    ClosingTime = models.DateTimeField(unique=False, blank=True, null=True)
    OffsetOpeningTime = models.DateTimeField(
        unique=False, blank=True, null=True)
    OffsetClosingTime = models.DateTimeField(
        unique=False, blank=True, null=True)
    OpeningTimeType = models.CharField(
        max_length=50, unique=False, blank=True, null=True)
    AdditionalOpeningDate = models.DateTimeField(
        unique=False, blank=True, null=True)
    IsOpen = models.BooleanField(unique=False, blank=True, null=True)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, blank=True, null=True, related_name='OpeningTimes')


class LastUpdatedDate(models.Model):
    OpeningTimes = models.DateField()
    BankHolidayOpeningTimes = models.DateTimeField()
    DentistsAcceptingPatients = models.BooleanField(blank=True, null=True)
    Facilities = models.DateTimeField()
    HospitalDepartment = models.CharField(
        max_length=50, unique=False, blank=True, null=True)
    Services = models.DateTimeField()
    ContactDetails = models.DateTimeField()
    AcceptingPatients = models.DateTimeField()
    organisation = models.OneToOneField(
        Organisation, on_delete=models.CASCADE, null=True, blank=True)
