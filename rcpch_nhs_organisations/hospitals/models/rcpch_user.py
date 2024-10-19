# RCPCH Custom User Model
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

# Constants
MR = 1
MRS = 2
MS = 3
DR = 4
PROFESSOR = 5

TITLES = ((MR, "Mr"), (MRS, "Mrs"), (MS, "Ms"), (DR, "Dr"), (PROFESSOR, "Professor"))


class RCPCHUser(AbstractUser):
    class Meta:
        verbose_name = _("RCPCH User")
        verbose_name_plural = _("RCPCH Users")

    # Methods

    def __str__(self):
        return self.get_full_name() + f" ({self.email})"

    def get_full_name(self):
        return f"{self.get_title_display()} {self.first_name} {self.surname}"

    def get_short_name(self):
        return f"{self.first_name} {self.surname}"

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        super().save(*args, **kwargs)

    # Fields

    # remove username field and set email as unique identifier
    username = None
    email = models.EmailField(
        _("email address"),
        unique=True,
        help_text=_("Required. Must be a valid email address."),
        error_messages={
            "unique": _("A user with that email already exists."),
        },
    )
    title = models.PositiveSmallIntegerField(
        _("title"),
        choices=TITLES,
        max_length=30,
        help_text=_("Please enter your title."),
        blank=True,
        null=True,
    )
    first_name = models.CharField(
        _("first name"),
        max_length=30,
        help_text=_("Please enter your first name."),
        blank=True,
    )
    surname = models.CharField(
        _("surname"),
        max_length=150,
        help_text=_("Please enter your surname."),
        blank=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "surname"]

    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. Unselect this instead of deleting accounts."
        ),
    )

    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )

    date_joined = models.DateTimeField(
        _("date joined"),
        auto_now_add=True,
        help_text=_("The date and time this user account was created."),
    )

    updated_at = models.DateTimeField(
        _("updated at"),
        auto_now=True,
        help_text=_("The date and time this user account was last updated."),
    )


# User Manager


class RCPCHUserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("The Email field must be set"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, password, **extra_fields)
