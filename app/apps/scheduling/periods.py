"""Stundenraster: Schulstunden ↔ Uhrzeiten."""

from datetime import time

from .models import SchoolPeriod

# Vorschlag beim ersten Öffnen (anpassbar): 45 Minuten, übliche Pausen
DEFAULT_PERIODS = [
    (1, time(8, 0), time(8, 45)),
    (2, time(8, 45), time(9, 30)),
    (3, time(9, 50), time(10, 35)),
    (4, time(10, 35), time(11, 20)),
    (5, time(11, 40), time(12, 25)),
    (6, time(12, 25), time(13, 10)),
    (7, time(13, 40), time(14, 25)),
    (8, time(14, 25), time(15, 10)),
    (9, time(15, 15), time(16, 0)),
    (10, time(16, 0), time(16, 45)),
]


def periods_for(organization):
    return list(SchoolPeriod.objects.for_org(organization))


def period_choices(organization):
    return [("", "Uhrzeit")] + [(p.number, p.label) for p in periods_for(organization)]


def times_for(organization, first, last=None):
    """(Beginn, Ende) für „ab der first. bis zur last. Stunde“."""
    periods = {p.number: p for p in periods_for(organization)}
    start = periods.get(int(first)) if first else None
    end = periods.get(int(last or first)) if (last or first) else None
    return (start.start_time if start else None, end.end_time if end else None)


def affected_periods(organization, start_time, end_time):
    """Schulstunden, die in den Zeitraum fallen (z. B. für die Freistellungsliste)."""
    if start_time is None or end_time is None:
        return periods_for(organization)
    return [
        p for p in periods_for(organization) if p.start_time < end_time and p.end_time > start_time
    ]


def describe(periods):
    """„3.–5. Stunde“ bzw. „4. Stunde“."""
    if not periods:
        return ""
    numbers = [p.number for p in periods]
    if len(numbers) == 1:
        return f"{numbers[0]}. Stunde"
    return f"{numbers[0]}.–{numbers[-1]}. Stunde"
