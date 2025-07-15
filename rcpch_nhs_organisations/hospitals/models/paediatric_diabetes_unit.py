# python imports

# django imports
from django.contrib.gis.db import models
from django.db.models import CharField

from .paediatric_diabetes_network import PaediatricDiabetesNetwork

class PaediatricDiabetesUnit(models.Model):
    pz_code = CharField("Paediatric Diabetes Unit PZ Number", max_length=5, unique=True)

    unit_name = CharField(
        "Name for the unit if different from the primary organisation for the parent",
        max_length=255,
        null=True,
        blank=True,
        default=None
    )

    class Meta:
        verbose_name = "Paediatric Diabetes Unit"
        verbose_name_plural = "Paediatric Diabetes Units"
        ordering = ("pz_code",)

    def __str__(self) -> str:
        return f"{self.pz_code}"

    paediatric_diabetes_network = models.ForeignKey(  # it is possible for a PaediatricDiabetesUnit to not be associated with a PaediatricDiabetesNetwork (eg RCPCH has a PZ code but no PN code)
        to=PaediatricDiabetesNetwork,
        on_delete=models.CASCADE,
        verbose_name="Paediatric Diabetes Network",
        related_name="paediatric_diabetes_units",
        blank=True,
        null=True,
    )

    updated_at = models.DateTimeField(
        "Last Updated",
        auto_now=True,
    )

    active = models.BooleanField(
        "Active",
        default=True,
    )

    @property
    def primary_organisation(self):
        # Fix circular import
        from .organisation import Organisation

        organisations = Organisation.objects.filter(paediatric_diabetes_unit=self).all()

        if not organisations.exists():
            return None

        if organisations.count() > 1:
            if self.pz_code == "PZ024":
                # RVV01 is the parent organisation for PZ024 (William Harvey Hospital, Ashford)
                return organisations.filter(ods_code="RVV01").get()
            elif self.pz_code == "PZ050":
                # RVR07 is the parent organisation for PZ024 (Queen Mary's Hospital for Children, Carshalton)
                return organisations.filter(ods_code="RVR07").get()
            elif self.pz_code == "PZ136":
                # R0A03 is the parent organisation for PZ099 (Manchester Children's Hospital)
                return organisations.filter(ods_code="R0A03").get()
            elif self.pz_code == "PZ206":
                # RM321 is the parent organisation for PZ206 (Trafford General Hospital)
                return organisations.filter(ods_code="RM321").get()
            elif self.pz_code == "PZ230":
                # RXC01 is the parent organisation for PZ230 (Conquest Hospital, Hastings)
                return organisations.filter(ods_code="RXC01").get()
            elif self.pz_code == "PZ249":
                # PZ249 is South Tees Hospital NHS Foundation Trust
                return organisations.filter(ods_code="RTRAT").get()
            elif self.pz_code == "PZ250":
                #  PZ250 is Sunderland Royal Hospital (R0B01) and South Tyneside District General Hospital (R0B0Q)
                return organisations.filter(ods_code="R0B01").get()  # Sunderland Royal Hospital
            elif self.pz_code == "PZ242":
                # PZ242 is GLOUCESTERSHIRE HOSPITALS NHS FOUNDATION TRUST
                #  - RTE01	CHELTENHAM GENERAL HOSPITAL 
                #  - RTE03	GLOUCESTERSHIRE ROYAL HOSPITAL (lead)
                return organisations.filter(ods_code="RTE03").get()  # GLOUCESTERSHIRE ROYAL HOSPITAL
            else:
                return organisations.first()
        else:
            return organisations.get()
    
    @property
    def name(self):
        if self.unit_name:
            return self.unit_name
        
        # These units identify themselves by their trust rather than lead organisation
        if self.pz_code in [
            "PZ024", # East Kent Hospitals University NHS Foundation Trust
            "PZ120", # Northumbria Healthcare NHS Foundation Trust
            "PZ167", # UNIVERSITY HOSPITALS OF MORECAMBE BAY NHS FOUNDATION TRUST
            "PZ172", # WEST HERTFORDSHIRE TEACHING HOSPITALS NHS TRUST
            "PZ186", # CALDERDALE AND HUDDERSFIELD NHS FOUNDATION TRUST
            "PZ232", # BARKING, HAVERING AND REDBRIDGE UNIVERSITY HOSPITALS NHS TRUST
            "PZ246", # NORTHERN CARE ALLIANCE NHS FOUNDATION TRUST
            "PZ249", # SOUTH TEES HOSPITALS NHS FOUNDATION TRUST
            "PZ250", # SOUTH TYNESIDE AND SUNDERLAND NHS FOUNDATION TRUST
        ]:
            return self.primary_organisation.trust.name
        
        # These units identify themselves by their local health board (🐉) rather than lead organisation
        if self.pz_code in [
            "PZ244"
        ]:
            return self.primary_organisation.local_health_board.name

        if self.primary_organisation:
            return self.primary_organisation.name
        
        return self.pz_code