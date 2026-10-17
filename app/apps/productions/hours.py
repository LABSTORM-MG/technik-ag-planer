"""Einsatzübersicht: Einsätze und Stunden je Mitglied (Abschnitt 5).

Gezählt werden zugesagte Jobs nicht gelöschter Produktionen und zugesagte, nicht abgesagte
Termine – jeweils bis heute. Eine Korrektur (`corrected_hours`) ersetzt den berechneten Wert.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone

from apps.scheduling.models import EventAttendee

from .models import CrewAssignment

# Schuljahr ab 1. August, 2. Halbjahr ab 1. Februar
SCHOOL_YEAR_START_MONTH = 8
SECOND_HALF_START_MONTH = 2

ZERO = Decimal("0")


def school_year_start(day):
    year = day.year if day.month >= SCHOOL_YEAR_START_MONTH else day.year - 1
    return date(year, SCHOOL_YEAR_START_MONTH, 1)


@dataclass(frozen=True)
class Period:
    key: str
    label: str
    start: date
    end: date


def periods(today=None):
    """Auswahl für den Zeitraum-Filter – das aktuelle Schuljahr zuerst."""
    today = today or timezone.localdate()
    start = school_year_start(today)
    y = start.year
    end = date(y + 1, SCHOOL_YEAR_START_MONTH - 1, 31)
    half = date(y + 1, SECOND_HALF_START_MONTH, 1)
    label = f"{y}/{str(y + 1)[-2:]}"
    previous = f"{y - 1}/{str(y)[-2:]}"
    return [
        Period("schuljahr", f"Schuljahr {label}", start, end),
        Period("halbjahr1", f"1. Halbjahr {label}", start, date(y + 1, 1, 31)),
        Period("halbjahr2", f"2. Halbjahr {label}", half, end),
        Period(
            "vorjahr",
            f"Schuljahr {previous}",
            date(y - 1, SCHOOL_YEAR_START_MONTH, 1),
            date(y, SCHOOL_YEAR_START_MONTH - 1, 31),
        ),
    ]


def _parse(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def period_from_request(params, today=None):
    """Zeitraum aus `?zeitraum=…` bzw. `?von=…&bis=…` (eigener Zeitraum)."""
    options = periods(today)
    start, end = _parse(params.get("von")), _parse(params.get("bis"))
    if params.get("zeitraum") == "eigener" and start and end and start <= end:
        label = f"{start:%d.%m.%Y} – {end:%d.%m.%Y}"
        return Period("eigener", label, start, end)
    return next((p for p in options if p.key == params.get("zeitraum")), options[0])


def _duration(day, start, end):
    if start is None or end is None:
        return ZERO
    seconds = (datetime.combine(day, end) - datetime.combine(day, start)).total_seconds()
    return (Decimal(seconds) / 3600).quantize(Decimal("0.01"))


@dataclass
class Entry:
    """Ein Einsatz: Job (kind="job") oder Termin (kind="event")."""

    kind: str
    obj: object  # CrewAssignment bzw. EventAttendee
    date: date
    title: str
    detail: str
    calculated: Decimal

    @property
    def corrected(self):
        return self.obj.corrected_hours

    @property
    def is_corrected(self):
        return self.corrected is not None

    @property
    def hours(self):
        return self.corrected if self.is_corrected else self.calculated


def _assignments(organization, start, end):
    return (
        CrewAssignment.objects.for_org(organization)
        .filter(
            status=CrewAssignment.Status.CONFIRMED,
            membership__isnull=False,
            job__production__deleted_at__isnull=True,
            job__date__range=(start, end),
        )
        .select_related("job", "job__production")
    )


def _attendances(organization, start, end):
    return (
        EventAttendee.objects.for_org(organization)
        .filter(
            status=EventAttendee.Status.CONFIRMED,
            membership__isnull=False,
            event__cancelled=False,
            event__date__range=(start, end),
        )
        .select_related("event")
    )


def _entries(organization, start, end, membership=None):
    end = min(end, timezone.localdate())  # nur bis heute
    assignments = _assignments(organization, start, end)
    attendances = _attendances(organization, start, end)
    if membership is not None:
        assignments = assignments.filter(membership=membership)
        attendances = attendances.filter(membership=membership)
    result = []
    for a in assignments:
        job = a.job
        result.append(
            Entry(
                "job",
                a,
                job.date,
                str(job.production),
                job.name + (f" · {a.role_label}" if a.role_label else ""),
                _duration(job.date, job.start_time, job.end_time),
            )
        )
    for a in attendances:
        event = a.event
        result.append(
            Entry(
                "event",
                a,
                event.date,
                event.title,
                "Termin" if event.start_time else "Termin (ganztägig)",
                _duration(event.date, event.start_time, event.end_time),
            )
        )
    return result


def entries(membership, start, end):
    """Einsätze einer Person im Zeitraum, nach Datum sortiert."""
    return sorted(
        _entries(membership.organization, start, end, membership), key=lambda e: (e.date, e.title)
    )


def total(items):
    return sum((e.hours for e in items), ZERO)


def summary(organization, memberships, start, end):
    """Für die Gesamtübersicht: [(Mitgliedschaft, Anzahl Einsätze, Stunden)]."""
    by_member = {}
    for e in _entries(organization, start, end):
        by_member.setdefault(e.obj.membership_id, []).append(e)
    return [(m, len(by_member.get(m.pk, [])), total(by_member.get(m.pk, []))) for m in memberships]


def confirmed_counts(organization, membership_ids, today=None):
    """Zugesagte Job-Einsätze je Mitglied im laufenden Schuljahr (für Crew-Vorschläge)."""
    start = school_year_start(today or timezone.localdate())
    counts = dict.fromkeys(membership_ids, 0)
    rows = (
        CrewAssignment.objects.for_org(organization)
        .filter(
            membership_id__in=membership_ids,
            status=CrewAssignment.Status.CONFIRMED,
            job__production__deleted_at__isnull=True,
            job__date__gte=start,
        )
        .values_list("membership_id", flat=True)
    )
    for membership_id in rows:
        counts[membership_id] += 1
    return counts
