from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.accounts.models import FORMER_MEMBER
from apps.organizations.models import OrganizationScopedModel

MAX_LENGTH = 2000


class Message(OrganizationScopedModel):
    """Nachricht im Board (production leer) oder im Chat einer Produktion."""

    class Kind(models.TextChoices):
        USER = "user", "Nachricht"
        SYSTEM = "system", "Systemmeldung"

    production = models.ForeignKey(
        "productions.Production",
        verbose_name="Produktions-Chat",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Absender",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    kind = models.CharField("Art", max_length=10, choices=Kind.choices, default=Kind.USER)
    text = models.TextField("Text", max_length=MAX_LENGTH)
    # Systemmeldungen: Antippen öffnet diese Produktion
    link_production = models.ForeignKey(
        "productions.Production",
        verbose_name="verlinkte Produktion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # Systemmeldungen zu Material (Defekt, wieder verfügbar): Antippen öffnet das Material
    link_material = models.ForeignKey(
        "inventory.Material",
        verbose_name="verlinktes Material",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # Verhindert doppelte Systemmeldungen (z. B. „noch 2 Plätze frei“ je Job und Tag)
    system_key = models.CharField(max_length=80, blank=True, editable=False)
    created_at = models.DateTimeField("gesendet am", auto_now_add=True)
    edited_at = models.DateTimeField("bearbeitet am", null=True, blank=True)

    class Meta:
        verbose_name = "Nachricht"
        verbose_name_plural = "Nachrichten"
        ordering = ["id"]
        indexes = [models.Index(fields=["organization", "production", "id"])]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "system_key"],
                condition=~Q(system_key=""),
                name="message_unique_system_key",
            )
        ]

    def __str__(self):
        return self.text[:60]

    @property
    def is_system(self):
        return self.kind == self.Kind.SYSTEM

    @property
    def author_name(self):
        return str(self.author) if self.author_id else FORMER_MEMBER


class ReadMarker(OrganizationScopedModel):
    """Bis zu welcher Nachricht ein Mitglied einen Chat gelesen hat."""

    membership = models.ForeignKey(
        "organizations.Membership", on_delete=models.CASCADE, related_name="+"
    )
    production = models.ForeignKey(
        "productions.Production", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    last_read_id = models.PositiveBigIntegerField(default=0)

    class Meta:
        verbose_name = "Lesestand"
        verbose_name_plural = "Lesestände"
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "production"],
                condition=Q(production__isnull=False),
                name="readmarker_unique_chat",
            ),
            models.UniqueConstraint(
                fields=["membership"],
                condition=Q(production__isnull=True),
                name="readmarker_unique_board",
            ),
        ]

    def __str__(self):
        return f"{self.membership_id}/{self.production_id or 'board'}: {self.last_read_id}"
