from datetime import time

from django.conf import settings
from django.db import models


class Kind(models.TextChoices):
    """Arten von Push-Mitteilungen – jede einzeln abschaltbar (Abschnitt 9)."""

    CREW = "crew", "Crew-Anfragen und Einteilungen"
    CHANGES = "changes", "Änderungen an meinen Jobs"
    REMINDERS = "reminders", "Erinnerung vor meinen Jobs"
    INQUIRIES = "inquiries", "Neue Technik-Anfragen"
    BOARD = "board", "Neue Nachrichten im Board"
    CHATS = "chats", "Neue Nachrichten in Chats meiner Produktionen"


class PushSubscription(models.Model):
    """Ein Gerät (Browser), das Push-Mitteilungen empfängt. Gehört zum Konto, nicht zur AG."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.URLField("Endpoint", max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField("Gerät", max_length=300, blank=True)
    created_at = models.DateTimeField("angemeldet am", auto_now_add=True)
    last_used_at = models.DateTimeField("zuletzt benutzt", null=True, blank=True)

    class Meta:
        verbose_name = "Push-Gerät"
        verbose_name_plural = "Push-Geräte"

    def __str__(self):
        return f"{self.user} – {self.user_agent[:40] or 'Gerät'}"


class NotificationSettings(models.Model):
    """Benachrichtigungs-Einstellungen eines Kontos (gelten für alle AGs)."""

    class ReminderMode(models.TextChoices):
        EVENING = "evening", "Am Vorabend um …"
        HOURS = "hours", "Einige Stunden vorher"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_settings"
    )
    crew = models.BooleanField(Kind.CREW.label, default=True)
    changes = models.BooleanField(Kind.CHANGES.label, default=True)
    reminders = models.BooleanField(Kind.REMINDERS.label, default=True)
    inquiries = models.BooleanField(Kind.INQUIRIES.label, default=True)
    board = models.BooleanField(Kind.BOARD.label, default=True)
    chats = models.BooleanField(Kind.CHATS.label, default=True)
    reminder_mode = models.CharField(
        "Erinnerung", max_length=10, choices=ReminderMode.choices, default=ReminderMode.EVENING
    )
    reminder_time = models.TimeField("Uhrzeit am Vorabend", default=time(18, 0))
    reminder_hours = models.PositiveSmallIntegerField(
        "Stunden vorher", default=3, help_text="1 bis 48"
    )

    class Meta:
        verbose_name = "Benachrichtigungs-Einstellungen"
        verbose_name_plural = "Benachrichtigungs-Einstellungen"

    def __str__(self):
        return str(self.user)

    def wants(self, kind):
        return getattr(self, Kind(kind).value)

    @classmethod
    def for_user(cls, user):
        settings_obj, _ = cls.objects.get_or_create(user=user)
        return settings_obj
