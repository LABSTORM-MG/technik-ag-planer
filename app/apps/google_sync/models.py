from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.organizations.models import OrganizationScopedModel

from . import crypto


class GoogleConnection(OrganizationScopedModel):
    """Das verbundene Google-Konto der AG (genau eins je AG, nur der Owner verwaltet es)."""

    organization = models.OneToOneField(
        "organizations.Organization",
        verbose_name="AG",
        on_delete=models.CASCADE,
        related_name="google_connection",
    )
    account_email = models.EmailField("Google-Konto")
    refresh_token_encrypted = models.TextField(blank=True, editable=False)
    scopes = models.JSONField("Berechtigungen", default=list, blank=True)
    connected_at = models.DateTimeField("verbunden am", null=True, blank=True)
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="verbunden von",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # Bleiben nach dem Trennen erhalten – beim erneuten Verbinden desselben Kontos weiter genutzt
    calendar_id = models.CharField("Kalender-ID", max_length=255, blank=True)
    root_folder_id = models.CharField(max_length=255, blank=True)
    folder_ids = models.JSONField(default=dict, blank=True)
    last_sync_at = models.DateTimeField("zuletzt abgeglichen", null=True, blank=True)
    last_error = models.CharField("letzter Fehler", max_length=300, blank=True)

    class Meta:
        verbose_name = "Google-Verbindung"
        verbose_name_plural = "Google-Verbindungen"

    def __str__(self):
        return f"{self.account_email} ({self.organization})"

    @property
    def is_connected(self):
        return bool(self.refresh_token_encrypted)

    @property
    def refresh_token(self):
        return crypto.decrypt(self.refresh_token_encrypted)

    @refresh_token.setter
    def refresh_token(self, value):
        self.refresh_token_encrypted = crypto.encrypt(value)


class SyncedEvent(OrganizationScopedModel):
    """Ein übertragener Google-Termin: App-Schlüssel (z. B. „job:12“) → Google-Termin."""

    key = models.CharField(max_length=40)
    google_event_id = models.CharField(max_length=255)
    checksum = models.CharField(max_length=64)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "übertragener Termin"
        verbose_name_plural = "übertragene Termine"
        constraints = [
            models.UniqueConstraint(fields=["organization", "key"], name="synced_event_unique")
        ]

    def __str__(self):
        return self.key


class Attachment(OrganizationScopedModel):
    """Datei im Google Drive der AG. Hängt an genau einem Eintrag."""

    production = models.ForeignKey(
        "productions.Production",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    material = models.ForeignKey(
        "inventory.Material",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    defect = models.ForeignKey(
        "inventory.DefectReport",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    name = models.CharField("Name", max_length=200)
    mime_type = models.CharField(max_length=120)
    size = models.PositiveBigIntegerField("Größe", default=0)
    drive_file_id = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    uploaded_at = models.DateTimeField("hochgeladen am", auto_now_add=True)

    TARGETS = ("production", "material", "defect", "inquiry")

    class Meta:
        verbose_name = "Datei"
        verbose_name_plural = "Dateien"
        ordering = ["uploaded_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(production__isnull=False, material=None, defect=None, inquiry=None)
                    | Q(production=None, material__isnull=False, defect=None, inquiry=None)
                    | Q(production=None, material=None, defect__isnull=False, inquiry=None)
                    | Q(production=None, material=None, defect=None, inquiry__isnull=False)
                ),
                name="attachment_exactly_one_target",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def is_image(self):
        return self.mime_type.startswith("image/")
