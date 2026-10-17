"""Kalender-Übertragung App → Google als Gesamtvergleich."""

from datetime import time, timedelta

from django.utils import timezone

from apps.google_sync.calendar_sync import sync_calendar
from apps.google_sync.google_api import EXPIRED, GoogleError
from apps.google_sync.models import GoogleConnection
from apps.productions.models import Category, CrewAssignment
from apps.scheduling.models import Event, Unavailability


def test_not_connected_does_nothing(org, google):
    assert sync_calendar(org) is None
    assert not google.calls


def test_creates_all_entries(
    org, connected, google, student, make_production, make_job, make_assignment
):
    concert = make_production(
        org,
        "Schulkonzert",
        length=2,
        category=Category.objects.for_org(org).get(name="Konzert"),
        location_name="Aula",
        address="Schulstraße 1",
        notes="Schwarz tragen",
    )
    job = make_job(concert, "Aufbau", meeting_point="Bühneneingang")
    make_assignment(job, student, CrewAssignment.Status.CONFIRMED, role_label="Licht")
    day = timezone.localdate() + timedelta(days=4)
    Event.objects.create(organization=org, title="AG-Treffen", date=day, cancelled=True)
    Unavailability.objects.create(
        organization=org,
        membership=student,
        start_date=day,
        end_date=day,
        start_time=time(8),
        end_time=time(12),
        note="Zahnarzt",
    )

    assert sync_calendar(org) == (4, 0, 0)
    events = google.by_key()
    production = events[f"production:{concert.pk}"]
    assert production["start"] == {"date": concert.start_date.isoformat()}
    assert production["end"] == {"date": (concert.end_date + timedelta(days=1)).isoformat()}
    assert production["colorId"] == "9"  # Konzert = Blau → Heidelbeere
    assert production["location"] == "Aula, Schulstraße 1"
    assert "Schwarz tragen" in production["description"]
    assert "Emma (Licht) – zugesagt" in production["description"]
    assert f"/produktionen/{concert.pk}/" in production["source"]["url"]

    job_event = events[f"job:{job.pk}"]
    assert job_event["summary"] == "Schulkonzert – Aufbau"
    assert job_event["start"]["dateTime"].startswith(f"{job.date.isoformat()}T14:00")
    assert "Treffpunkt: Bühneneingang" in job_event["description"]

    meeting = next(b for k, b in events.items() if k.startswith("event:"))
    assert meeting["summary"] == "Abgesagt: AG-Treffen" and "date" in meeting["start"]

    away = next(b for k, b in events.items() if k.startswith("unavailable:"))
    assert away["summary"] == "Nicht verfügbar: Emma"
    assert away["colorId"] == "8"  # Graphit
    assert "Zahnarzt" not in str(away)  # Notiz bleibt privat
    assert GoogleConnection.objects.get().last_sync_at is not None


def test_only_changes_are_sent(org, connected, google, make_production, make_job):
    concert = make_production(org)
    job = make_job(concert)
    sync_calendar(org)
    google.calls.clear()

    assert sync_calendar(org) == (0, 0, 0)
    assert "update_event" not in google.calls

    job.meeting_point = "Haupteingang"
    job.save()
    created, updated, deleted = sync_calendar(org)
    assert (created, deleted) == (0, 0) and updated == 2  # Job und Beschreibung der Produktion
    assert "Haupteingang" in google.by_key()[f"job:{job.pk}"]["description"]


def test_deleted_and_restored_production(org, connected, google, make_production, make_job):
    concert = make_production(org)
    make_job(concert)
    sync_calendar(org)

    concert.soft_delete()
    assert sync_calendar(org) == (0, 0, 2)
    assert not google.events

    concert.restore()
    assert sync_calendar(org) == (2, 0, 0)


def test_event_deleted_in_google_is_recreated(org, connected, google, make_production):
    concert = make_production(org)
    sync_calendar(org)
    google.events.clear()
    concert.notes = "neu"
    concert.save()
    sync_calendar(org)
    assert google.by_key()[f"production:{concert.pk}"]["description"].count("neu") == 1


def test_missing_calendar_is_recreated(org, connected, google, make_production):
    make_production(org)
    sync_calendar(org)
    google.calendars.clear()
    google.events.clear()
    assert sync_calendar(org) == (1, 0, 0)
    assert GoogleConnection.objects.get().calendar_id in google.calendars


def test_expired_token_is_reported(org, connected, google):
    google.fail_with = GoogleError(EXPIRED, "expired")
    assert sync_calendar(org) is None
    assert GoogleConnection.objects.get().last_error == EXPIRED


def test_changes_trigger_sync(
    org, connected, google, make_production, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        concert = make_production(org, "Theater")
    assert [b["summary"] for b in google.events.values()] == ["Theater"]
    assert google.by_key()[f"production:{concert.pk}"]


def test_no_sync_without_connection(
    org, google, make_production, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        make_production(org)
    assert not google.calls
