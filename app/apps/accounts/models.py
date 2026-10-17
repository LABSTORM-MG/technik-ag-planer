from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

FORMER_MEMBER = "Ehemaliges Mitglied"  # Name für Einsätze und Nachrichten gelöschter Konten


class Grade(models.TextChoices):
    """Jahrgangsstufen (Abschnitt 2). „Extern“ entsteht beim Schuljahreswechsel aus Q2."""

    G5 = "5", "5"
    G6 = "6", "6"
    G7 = "7", "7"
    G8 = "8", "8"
    G9 = "9", "9"
    G10 = "10", "10"
    EF = "EF", "EF"
    Q1 = "Q1", "Q1"
    Q2 = "Q2", "Q2"
    EXTERN = "EXT", "Extern"

    @classmethod
    def selectable(cls):
        """Auswahl bei Einladung und im Profil – „Extern“ vergibt nur der Schuljahreswechsel."""
        return [(value, label) for value, label in cls.choices if value != cls.EXTERN]


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Eine E-Mail-Adresse ist erforderlich.")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("display_name", "Betreiber")
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username):
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": username})


class User(AbstractBaseUser, PermissionsMixin):
    """Konto. Login per E-Mail; `is_staff` haben nur Betreiber (Django-Admin)."""

    email = models.EmailField("E-Mail-Adresse", unique=True)
    display_name = models.CharField(
        "Name", max_length=80, help_text="Frei wählbar, auch ein Spitzname."
    )
    grade = models.CharField("Jahrgangsstufe", max_length=3, choices=Grade.choices, blank=True)
    is_active = models.BooleanField(
        "aktiv", default=True, help_text="Gesperrte Konten können sich nicht anmelden."
    )
    is_staff = models.BooleanField("Betreiber", default=False, help_text="Zugang zum Django-Admin.")
    date_joined = models.DateTimeField("registriert am", default=timezone.now)
    grade_promoted_at = models.DateTimeField(
        "zuletzt hochgestuft am",
        null=True,
        blank=True,
        help_text="Schuljahreswechsel – verhindert doppeltes Hochstufen über mehrere AGs.",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Konto"
        verbose_name_plural = "Konten"
        ordering = ["display_name", "email"]

    def __str__(self):
        return self.display_name or self.email

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def get_full_name(self):
        return str(self)

    def get_short_name(self):
        return str(self)

    @property
    def has_2fa(self):
        return self.totpdevice_set.filter(confirmed=True).exists()
