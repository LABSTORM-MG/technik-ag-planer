"""Minimaler iCalendar-Export (RFC 5545) für einzelne Einträge – „In Kalender übernehmen“."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from django.utils import timezone


@dataclass
class IcsEvent:
    uid: str
    summary: str
    start: datetime | date
    end: datetime | date  # bei ganztägig: Tag NACH dem letzten Tag (exklusiv)
    location: str = ""
    description: str = ""
    url: str = ""


def _escape(text):
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line):
    """Zeilen auf 75 Bytes umbrechen (Folgezeilen beginnen mit einem Leerzeichen)."""
    raw = line.encode()
    if len(raw) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        encoded = char.encode()
        if len(current) + len(encoded) > (75 if not parts else 74):
            parts.append(current.decode())
            current = b""
        current += encoded
    parts.append(current.decode())
    return "\r\n ".join(parts)


def _dt(value):
    if isinstance(value, datetime):
        return ":" + value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return ";VALUE=DATE:" + value.strftime("%Y%m%d")


def build_calendar(events):
    stamp = timezone.now().astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Technik-AG Planer//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for ev in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{ev.uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART{_dt(ev.start)}",
            f"DTEND{_dt(ev.end)}",
            f"SUMMARY:{_escape(ev.summary)}",
        ]
        if ev.location:
            lines.append(f"LOCATION:{_escape(ev.location)}")
        if ev.description:
            lines.append(f"DESCRIPTION:{_escape(ev.description)}")
        if ev.url:
            lines.append(f"URL:{ev.url}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def all_day(start_date, end_date):
    """Ganztägig von start_date bis einschließlich end_date."""
    return start_date, end_date + timedelta(days=1)
