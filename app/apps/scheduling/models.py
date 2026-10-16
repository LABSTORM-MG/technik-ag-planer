from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.organizations.models import OrganizationScopedModel


def aware(day, t):
    return timezone.make_aware(datetime.combine(day, t))


class SchoolPeriod(OrganizationScopedModel):
    """Eine Unterrichtsstunde im Stundenraster der Schule (gilt an allen Schultagen gleich)."""

    number = models.PositiveSmallIntegerField("Stunde")
    start_time = models.TimeField("Beginn")
    end_time = models.TimeField("Ende")

    class Meta:
        verbose_name = "Unterrichtsstunde"
        verbose_name_plural = "Stundenraster"
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="period_unique_number")
        ]

    def __str__(self):
        return f"{self.number}. Stunde ({self.start_time:%H:%M}–{self.end_time:%H:%M})"

    @property
    def label(self):
        return f"{self.number}. Stunde"


class EventSeries(OrganizationScopedModel):
    class Frequency(models.TextChoices):
        WEEKLY = "weekly", "wöchentlich"
        BIWEEKLY = "biweekly", "alle 2 Wochen"
        MONTHLY = "monthly", "monatlich"

    frequency = models.CharField("Wiederholung", max_length=10, choices=Frequency.choices)
    until = models.DateField("Wiederholen bis")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Terminserie"
        verbose_name_plural = "Terminserien"

    def __str__(self):
        return f"{self.get_frequency_display()} bis {self.until:%d.%m.%Y}"


class Event(OrganizationScopedModel):
    """Einfacher Termin, z. B. AG-Treffen – einzeln oder als Teil einer Serie."""

    title = models.CharField("Titel", max_length=120)
    date = models.DateField("Datum")
    start_time = models.TimeField("Beginn", null=True, blank=True)
    end_time = models.TimeField("Ende", null=True, blank=True)
    location = models.CharField("Ort", max_length=120, blank=True)
    notes = models.TextField("Notizen", blank=True)
    series = models.ForeignKey(
        EventSeries,
        verbose_name="Serie",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    # Einzeln geänderter Termin einer Serie – bleibt bei Änderungen an der Serie unberührt
    is_detached = models.BooleanField(default=False)
    cancelled = models.BooleanField("abgesagt", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Termin"
        verbose_name_plural = "Termine"
        ordering = ["date", "start_time", "title"]

    def __str__(self):
        return f"{self.title} ({self.date:%d.%m.%Y})"

    def clean(self):
        if bool(self.start_time) != bool(self.end_time):
            raise ValidationError("Bitte Beginn und Ende angeben – oder beides leer lassen.")
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "Das Ende muss nach dem Beginn liegen."})

    @property
    def all_day(self):
        return self.start_time is None

    @property
    def start_datetime(self):
        return aware(self.date, self.start_time or time.min)

    @property
    def end_datetime(self):
        if self.end_time is None:
            return aware(self.date + timedelta(days=1), time.min)
        return aware(self.date, self.end_time)


class EventAttendee(OrganizationScopedModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "angefragt"
        CONFIRMED = "confirmed", "zugesagt"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attendees")
    membership = models.ForeignKey(
        "organizations.Membership",
        verbose_name="Mitglied",
        on_delete=models.CASCADE,
        related_name="event_attendances",
    )
    status = models.CharField(
        "Status", max_length=10, choices=Status.choices, default=Status.REQUESTED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Termin-Teilnahme"
        verbose_name_plural = "Termin-Teilnahmen"
        ordering = ["membership__user__display_name"]
        constraints = [
            models.UniqueConstraint(fields=["event", "membership"], name="attendee_unique")
        ]

    def __str__(self):
        return f"{self.membership.user} – {self.event} ({self.get_status_display()})"

    @property
    def is_confirmed(self):
        return self.status == self.Status.CONFIRMED


class Unavailability(OrganizationScopedModel):
    """„Nicht verfügbar“: durchgehender Zeitraum; ohne Uhrzeit ganze Tage."""

    membership = models.ForeignKey(
        "organizations.Membership",
        verbose_name="Mitglied",
        on_delete=models.CASCADE,
        related_name="unavailabilities",
    )
    start_date = models.DateField("Von")
    end_date = models.DateField("Bis")
    start_time = models.TimeField("ab", null=True, blank=True)
    end_time = models.TimeField("bis", null=True, blank=True)
    note = models.CharField("Notiz", max_length=120, blank=True, help_text="Nur für dich, optional")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nicht verfügbar"
        verbose_name_plural = "Nicht verfügbar"
        ordering = ["start_date", "start_time"]

    def __str__(self):
        return f"Nicht verfügbar: {self.membership.user}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "„Bis“ darf nicht vor „Von“ liegen."})
        if (
            self.start_date
            and self.start_date == self.end_date
            and self.start_time
            and self.end_time
            and self.end_time <= self.start_time
        ):
            raise ValidationError({"end_time": "Das Ende muss nach dem Beginn liegen."})

    @property
    def all_day(self):
        return self.start_time is None and self.end_time is None

    @property
    def start_datetime(self):
        return aware(self.start_date, self.start_time or time.min)

    @property
    def end_datetime(self):
        if self.end_time is None:
            return aware(self.end_date + timedelta(days=1), time.min)
        return aware(self.end_date, self.end_time)
