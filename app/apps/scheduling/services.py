"""Terminserien und Konfliktprüfung."""

import calendar as pycalendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Event, EventAttendee, EventSeries, Unavailability

MAX_SERIES_DAYS = 400  # etwas mehr als ein Schuljahr


# ---------- Serien ----------


def occurrence_dates(start: date, frequency: str, until: date):
    """Termine einer Serie. Monatlich: gleicher Tag im Monat; fehlt er (z. B. 31.), entfällt er."""
    if frequency in (EventSeries.Frequency.WEEKLY, EventSeries.Frequency.BIWEEKLY):
        step = timedelta(days=7 if frequency == EventSeries.Frequency.WEEKLY else 14)
        day = start
        while day <= until:
            yield day
            day += step
        return
    year, month = start.year, start.month
    while True:
        if pycalendar.monthrange(year, month)[1] >= start.day:
            day = date(year, month, start.day)
            if day > until:
                return
            yield day
        month += 1
        if month > 12:
            year, month = year + 1, 1
        if date(year, month, 1) > until:
            return


EVENT_FIELDS = ["title", "start_time", "end_time", "location", "notes"]


@transaction.atomic
def create_event(organization, data, *, frequency="", until=None, user=None):
    """Legt einen Termin an – oder eine ganze Serie, wenn `frequency` gesetzt ist."""
    fields = {f: data.get(f) or ("" if f in ("location", "notes") else None) for f in EVENT_FIELDS}
    if not frequency:
        return Event.objects.create(
            organization=organization, date=data["date"], created_by=user, **fields
        )
    series = EventSeries.objects.create(organization=organization, frequency=frequency, until=until)
    events = [
        # einzeln anlegen (nicht bulk_create), damit das Änderungsprotokoll jeden Termin erfasst
        Event.objects.create(
            organization=organization, date=day, series=series, created_by=user, **fields
        )
        for day in occurrence_dates(data["date"], frequency, until)
    ]
    return events[0]


def following(event):
    """Dieser und alle folgenden, nicht einzeln geänderten Termine der Serie."""
    return Event.objects.filter(
        Q(series=event.series, date__gte=event.date, is_detached=False) | Q(pk=event.pk)
    )


@transaction.atomic
def update_event(event, data, *, scope="single"):
    """scope="single": nur dieser Termin (wird von der Serie gelöst);
    scope="following": dieser und alle folgenden, nicht einzeln geänderten Termine."""
    if scope == "following" and event.series_id:
        delta = data["date"] - event.date
        for other in following(event).order_by("date"):
            for f in EVENT_FIELDS:
                setattr(other, f, data.get(f) or ("" if f in ("location", "notes") else None))
            other.date = other.date + delta
            other.save()
        return
    for f in EVENT_FIELDS:
        setattr(event, f, data.get(f) or ("" if f in ("location", "notes") else None))
    event.date = data["date"]
    if event.series_id:
        event.is_detached = True
    event.save()


@transaction.atomic
def delete_event(event, *, scope="single"):
    if scope == "following" and event.series_id:
        for other in following(event):
            other.delete()
    else:
        event.delete()


def set_cancelled(event, cancelled):
    event.cancelled = cancelled
    if event.series_id:
        event.is_detached = True
    event.save(update_fields=["cancelled", "is_detached"])


def assign_attendee(event, membership, status):
    attendee, created = EventAttendee.objects.get_or_create(
        organization=event.organization,
        event=event,
        membership=membership,
        defaults={"status": status},
    )
    if not created and attendee.status != status:
        attendee.status = status
        attendee.save(update_fields=["status"])
    return attendee


# ---------- Konflikte ----------


@dataclass
class Conflict:
    kind: str  # "job", "event", "unavailable"
    title: str
    when: str


def _fmt(start: datetime, end: datetime, all_day=False):
    start, end = timezone.localtime(start), timezone.localtime(end)
    if all_day:
        last = (end - timedelta(seconds=1)).date()
        if last == start.date():
            return f"{start:%d.%m.}, ganztägig"
        return f"{start:%d.%m.}–{last:%d.%m.}, ganztägig"
    if start.date() == end.date():
        return f"{start:%d.%m.}, {start:%H:%M}–{end:%H:%M} Uhr"
    return f"{start:%d.%m. %H:%M} – {end:%d.%m. %H:%M} Uhr"


def find_conflicts(
    membership, start: datetime, end: datetime, *, exclude_job=None, exclude_event=None
):
    """Überschneidungen mit Jobs, Terminen und „Nicht verfügbar“ der Person."""
    from apps.productions.models import CrewAssignment

    org = membership.organization
    first, last = timezone.localtime(start).date(), timezone.localtime(end).date()
    conflicts = []

    assignments = (
        CrewAssignment.objects.for_org(org)
        .filter(
            membership=membership,
            job__date__range=(first, last),
            job__production__deleted_at__isnull=True,
        )
        .select_related("job", "job__production")
    )
    for a in assignments:
        if exclude_job is not None and a.job_id == exclude_job.pk:
            continue
        if a.job.start_datetime < end and a.job.end_datetime > start:
            conflicts.append(
                Conflict(
                    "job",
                    f"{a.job.production} – {a.job.name} ({a.get_status_display()})",
                    _fmt(a.job.start_datetime, a.job.end_datetime),
                )
            )

    attendances = (
        EventAttendee.objects.for_org(org)
        .filter(membership=membership, event__date__range=(first, last), event__cancelled=False)
        .select_related("event")
    )
    for a in attendances:
        if exclude_event is not None and a.event_id == exclude_event.pk:
            continue
        ev = a.event
        if ev.start_datetime < end and ev.end_datetime > start:
            conflicts.append(
                Conflict(
                    "event",
                    f"{ev.title} ({a.get_status_display()})",
                    _fmt(ev.start_datetime, ev.end_datetime, ev.all_day),
                )
            )

    absences = Unavailability.objects.for_org(org).filter(
        membership=membership, start_date__lte=last, end_date__gte=first
    )
    for u in absences:
        if u.start_datetime < end and u.end_datetime > start:
            conflicts.append(
                Conflict(
                    "unavailable",
                    "Nicht verfügbar",
                    _fmt(u.start_datetime, u.end_datetime, u.all_day),
                )
            )
    return conflicts
