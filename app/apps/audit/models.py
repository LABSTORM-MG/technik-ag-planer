from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    """Internes Änderungsprotokoll – nur im Django-Admin sichtbar, nach 7 Tagen gelöscht."""

    class Action(models.TextChoices):
        CREATE = "create", "angelegt"
        UPDATE = "update", "geändert"
        DELETE = "delete", "gelöscht"

    created_at = models.DateTimeField("Zeitpunkt", auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Nutzer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    actor_label = models.CharField("Nutzer (Text)", max_length=255, blank=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="AG",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    organization_label = models.CharField("AG (Text)", max_length=255, blank=True)
    action = models.CharField("Aktion", max_length=10, choices=Action.choices)
    object_type = models.CharField("Objekttyp", max_length=100)
    object_id = models.CharField("Objekt-ID", max_length=64)
    object_repr = models.CharField("Bezeichnung", max_length=255)
    changes = models.JSONField("Änderungen", default=dict, blank=True)

    class Meta:
        verbose_name = "Protokolleintrag"
        verbose_name_plural = "Änderungsprotokoll"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()}: {self.object_type} {self.object_repr}"
