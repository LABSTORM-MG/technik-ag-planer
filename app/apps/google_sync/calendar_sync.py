"""Kalender-Übertragung App → Google (Abschnitt 9), als Gesamtvergleich.

`desired_events` berechnet den Soll-Stand aller Einträge, `sync_calendar` gleicht ihn mit den
übertragenen Terminen (SyncedEvent) ab: anlegen, ändern (nur bei geänderter Prüfsumme),
löschen. Änderungen direkt in Google werden so beim nächsten Abgleich überschrieben.
"""

import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone

from apps.productions.models import CrewAssignment, Job, Production
from apps.productions.palette import Color
from apps.scheduling.models import Event, Unavailability

from . import google_api
from .google_api import GoogleError
from .models import GoogleConnection, SyncedEvent

HISTORY_DAYS = 365  # auch vergangene Einträge eines Jahres bleiben im Google-Kalender

# Palette → Google-Kalender-Farben (colorId 1–11); Pink und Koralle teilen sich „Flamingo“
GOOGLE_COLORS = {
    Color.GREEN: "10",  # Basilikum
    Color.ORANGE: "6",  # Mandarine
    Color.BLUE: "9",  # Heidelbeere
    Color.LILAC: "1",  # Lavendel
    Color.RED: "11",  # Tomate
    Color.TEAL: "7",  # Pfau
    Color.PINK: "4",  # Flamingo
    Color.YELLOW: "5",  # Banane
    Color.VIOLET: "3",  # Weintraube
    Color.LIME: "2",  # Salbei
    Color.CORAL: "4",  # Flamingo
    Color.GREY: "8",  # Graphit
}
EVENT_COLOR = "1"  # Termine: Lavendel (Akzentfarbe der App)
UNAVAILABLE_COLOR = "8"  # Graphit, zurückhaltend


def _link(path):
    return settings.SITE_URL.rstrip("/") + path


def _all_day(first, last):
    return {"date": first.isoformat()}, {"date": (last + timedelta(days=1)).isoformat()}


def _timed(start, end):
    tz = settings.TIME_ZONE
    return (
        {"dateTime": timezone.localtime(start).isoformat(), "timeZone": tz},
        {"dateTime": timezone.localtime(end).isoformat(), "timeZone": tz},
    )


def _body(key, summary, start, end, *, description="", location="", color="", link=""):
    body = {
        "summary": summary,
        "start": start,
        "end": end,
        "description": description,
        "location": location,
        "extendedProperties": {"private": {"app_key": key}},
    }
    if color:
        body["colorId"] = color
    if link:
        body["source"] = {"title": "Technik-AG Planer", "url": link}
    return body


def _place(production):
    return ", ".join(p for p in [production.location_name, production.address] if p)


def _crew_lines(job):
    return [
        f"• {a.person}"
        + (f" ({a.role_label})" if a.role_label else "")
        + f" – {a.get_status_display()}"
        for a in job.crew.all()
    ]


def _job_line(job):
    line = f"{job.name}: {job.date:%d.%m.} {job.start_time:%H:%M}–{job.end_time:%H:%M} Uhr"
    if job.meeting_point:
        line += f", Treffpunkt {job.meeting_point}"
    return line


def _production_event(p):
    link = _link(reverse("productions:detail", args=[p.pk]))
    lines = [f"Status: {p.status.name}"]
    if p.category:
        lines.append(f"Kategorie: {p.category.name}")
    if p.notes:
        lines += ["", p.notes]
    jobs = list(p.jobs.all())
    if jobs:
        lines += ["", "Jobs:"]
        for job in jobs:
            lines.append(_job_line(job))
            lines += [f"  {c}" for c in _crew_lines(job)]
    lines += ["", f"In der App öffnen: {link}"]
    start, end = _all_day(p.start_date, p.end_date)
    return _body(
        f"production:{p.pk}",
        p.name,
        start,
        end,
        description="\n".join(lines),
        location=_place(p),
        color=GOOGLE_COLORS.get(p.category.color, "") if p.category else "",
        link=link,
    )


def _job_event(job):
    p = job.production
    link = _link(reverse("productions:detail", args=[p.pk]))
    lines = []
    if job.meeting_point:
        lines.append(f"Treffpunkt: {job.meeting_point}")
    crew = _crew_lines(job)
    if crew:
        lines += ["Crew:", *crew]
    lines += ["", f"In der App öffnen: {link}"]
    start, end = _timed(job.start_datetime, job.end_datetime)
    return _body(
        f"job:{job.pk}",
        f"{p.name} – {job.name}",
        start,
        end,
        description="\n".join(lines).strip(),
        location=_place(p),
        color=GOOGLE_COLORS.get(p.category.color, "") if p.category else "",
        link=link,
    )


def _event_event(e):
    link = _link(reverse("scheduling:event_detail", args=[e.pk]))
    if e.all_day:
        start, end = _all_day(e.date, e.date)
    else:
        start, end = _timed(e.start_datetime, e.end_datetime)
    description = "\n".join(filter(None, [e.notes, f"In der App öffnen: {link}"]))
    return _body(
        f"event:{e.pk}",
        f"Abgesagt: {e.title}" if e.cancelled else e.title,
        start,
        end,
        description=description,
        location=e.location,
        color=EVENT_COLOR,
        link=link,
    )


def _unavailability_event(u):
    if u.all_day:
        start, end = _all_day(u.start_date, u.end_date)
    else:
        start, end = _timed(u.start_datetime, u.end_datetime)
    # Die Notiz ist privat („Nur für dich“) und wird nicht übertragen
    return _body(
        f"unavailable:{u.pk}",
        f"Nicht verfügbar: {u.membership.user}",
        start,
        end,
        color=UNAVAILABLE_COLOR,
    )


def desired_events(organization, today=None):
    """Soll-Stand: {Schlüssel: Google-Termin} für alle Einträge ab einem Jahr zurück."""
    since = (today or timezone.localdate()) - timedelta(days=HISTORY_DAYS)
    crew = Prefetch("crew", queryset=CrewAssignment.objects.select_related("membership__user"))
    productions = (
        Production.objects.for_org(organization)
        .filter(end_date__gte=since)
        .select_related("category", "status")
        .prefetch_related(Prefetch("jobs", queryset=Job.objects.prefetch_related(crew)))
    )
    result = {}
    for p in productions:
        result[f"production:{p.pk}"] = _production_event(p)
        for job in p.jobs.all():
            job.production = p
            result[f"job:{job.pk}"] = _job_event(job)
    for e in Event.objects.for_org(organization).filter(date__gte=since):
        result[f"event:{e.pk}"] = _event_event(e)
    unavailabilities = (
        Unavailability.objects.for_org(organization)
        .filter(end_date__gte=since)
        .select_related("membership__user")
    )
    for u in unavailabilities:
        result[f"unavailable:{u.pk}"] = _unavailability_event(u)
    return result


def checksum(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def _ensure_calendar(connection, api):
    if connection.calendar_id and api.calendar_exists(connection.calendar_id):
        return connection.calendar_id
    connection.calendar_id = api.create_calendar(
        f"Technik-AG Planer – {connection.organization.name}"
    )
    connection.save(update_fields=["calendar_id"])
    # Neuer Kalender: alle Termine neu übertragen
    SyncedEvent.objects.for_org(connection.organization).delete()
    return connection.calendar_id


def sync_calendar(organization):
    """Gleicht den Google-Kalender der AG ab. Gibt (angelegt, geändert, gelöscht) zurück oder
    None, wenn nicht verbunden bzw. schon ein Abgleich läuft."""
    connection = GoogleConnection.objects.filter(organization=organization).first()
    if not connection or not connection.is_connected:
        return None
    lock = f"google-sync-lock:{organization.pk}"
    if not cache.add(lock, 1, timeout=10 * 60):
        return None
    try:
        return _sync(connection)
    except GoogleError as error:
        connection.last_error = error.message[:300]
        connection.save(update_fields=["last_error"])
        return None
    finally:
        cache.delete(lock)


def _sync(connection):
    organization = connection.organization
    api = google_api.for_connection(connection)
    calendar_id = _ensure_calendar(connection, api)
    desired = desired_events(organization)
    existing = {s.key: s for s in SyncedEvent.objects.for_org(organization)}
    created = updated = deleted = 0

    for key, body in desired.items():
        digest = checksum(body)
        synced = existing.pop(key, None)
        if synced is None:
            event_id = api.insert_event(calendar_id, body)
            SyncedEvent.objects.create(
                organization=organization, key=key, google_event_id=event_id, checksum=digest
            )
            created += 1
        elif synced.checksum != digest:
            try:
                api.update_event(calendar_id, synced.google_event_id, body)
            except GoogleError as error:
                if error.kind != "not_found":
                    raise
                # Termin wurde in Google gelöscht – neu anlegen
                synced.google_event_id = api.insert_event(calendar_id, body)
            synced.checksum = digest
            synced.save(update_fields=["google_event_id", "checksum", "synced_at"])
            updated += 1

    for synced in existing.values():
        api.delete_event(calendar_id, synced.google_event_id)
        synced.delete()
        deleted += 1

    connection.last_sync_at = timezone.now()
    connection.last_error = ""
    connection.save(update_fields=["last_sync_at", "last_error"])
    return created, updated, deleted
