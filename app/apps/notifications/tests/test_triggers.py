"""Wer bekommt wann eine Push-Mitteilung (Abschnitte 5, 6, 8, 9)."""

from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from apps.audit.context import acting_as
from apps.board import services as board
from apps.notifications.models import NotificationSettings
from apps.notifications.tasks import send_due_reminders
from apps.organizations.permissions import Role
from apps.productions import services as productions
from apps.productions.models import CrewAssignment
from apps.scheduling.models import Event, EventAttendee

from .conftest import titles

CONFIRMED = CrewAssignment.Status.CONFIRMED


@pytest.fixture
def run(django_capture_on_commit_callbacks):
    """Führt die nach dem Speichern eingeplanten Versand-Tasks sofort aus."""

    def wrapper(func, *args, **kwargs):
        with django_capture_on_commit_callbacks(execute=True):
            return func(*args, **kwargs)

    return wrapper


@pytest.fixture
def show(org, make_production, make_job):
    production = make_production(org, "Schulkonzert", location_name="Aula")
    return production, make_job(production, "Aufbau", meeting_point="Bühneneingang")


def test_crew_request_and_assignment(org, show, student, planner, pushed, device, run):
    production, job = show
    device(student)
    device(planner)
    run(productions.assign, job, student, status="requested", requested_by=planner.user)
    other = productions.Job.objects.create(
        organization=org,
        production=production,
        name="Show",
        date=job.date,
        start_time=time(18),
        end_time=time(21),
    )
    run(productions.assign, other, student, status="confirmed", requested_by=planner.user)
    assert titles(pushed) == [
        "Neue Crew-Anfrage: Aufbau Schulkonzert",
        "Du bist eingeteilt: Show Schulkonzert",
    ]
    assert all(user == student.user for user, _ in pushed)  # nicht an die Planerin


def test_event_attendance(org, student, pushed, device, run):
    device(student)
    event = Event.objects.create(organization=org, title="AG-Treffen", date=timezone.localdate())
    run(EventAttendee.objects.create, organization=org, event=event, membership=student)
    assert titles(pushed) == ["Neue Anfrage: AG-Treffen"]


def test_job_changes_reach_crew_only(
    org, show, student, make_member, make_assignment, pushed, device, run
):
    production, job = show
    outsider = make_member(org)
    make_assignment(job, student, CONFIRMED)
    device(student)
    device(outsider)

    def move():
        job.start_time = time(15)
        job.save()

    run(move)
    assert titles(pushed) == ["Geändert: Aufbau Schulkonzert"]
    assert "15:00" in pushed[0][1]["body"] and pushed[0][0] == student.user

    job.name = "Aufbau (neu)"  # Name allein ist keine Änderung für die Crew
    run(job.save)
    assert len(pushed) == 1


def test_job_deleted(org, show, student, make_assignment, pushed, device, run):
    _production, job = show
    make_assignment(job, student, CONFIRMED)
    device(student)
    run(job.delete)
    assert titles(pushed) == ["Abgesagt: Aufbau Schulkonzert"]


def test_production_changes(org, show, student, make_assignment, pushed, device, run):
    production, job = show
    make_assignment(job, student)
    device(student)

    def change():
        production.start_date += timedelta(days=1)
        production.end_date += timedelta(days=1)
        production.location_name = "Turnhalle"
        production.save()

    run(change)
    run(production.soft_delete)
    assert titles(pushed) == ["Geändert: Schulkonzert", "Produktion gelöscht: Schulkonzert"]
    assert "neuer Ort Turnhalle" in pushed[0][1]["body"]


def test_actor_gets_nothing(org, show, student, make_assignment, pushed, device, run):
    _production, job = show
    make_assignment(job, student, CONFIRMED)
    device(student)
    with acting_as(student.user):
        job.meeting_point = "Haupteingang"
        run(job.save)
    assert pushed == []


def test_inquiry_only_for_handlers(org, owner, make_member, pushed, device, run):
    from apps.inquiries.models import Inquiry

    teacher = make_member(org, Role.TEACHER)
    student = make_member(org)
    for m in (owner, teacher, student):
        device(m)
    run(
        Inquiry.objects.create,
        organization=org,
        requester_name="Frau Muster",
        requester_email="m@example.org",
        event_name="Elternabend",
        date=timezone.localdate(),
    )
    assert {u for u, _ in pushed} == {owner.user, teacher.user}
    assert titles(pushed)[0] == "Neue Technik-Anfrage: Elternabend"


def test_board_message_to_all_but_author(org, student, planner, make_member, pushed, device, run):
    third = make_member(org)
    for m in (student, planner, third):
        device(m)
    run(board.post, org, planner.user, "Wer hat den Schlüssel?")
    assert {u for u, _ in pushed} == {student.user, third.user}
    assert pushed[0][1]["body"] == "Ali Admin: Wer hat den Schlüssel?"


def test_chat_only_for_crew_and_supervisors(
    org, show, student, make_member, make_assignment, pushed, device, run
):
    production, job = show
    production.chat_enabled = True
    production.save()
    make_assignment(job, student)
    teacher = make_member(org, Role.TEACHER)
    production.supervisors.add(teacher)
    outsider = make_member(org)
    author = make_member(org)
    for m in (student, teacher, outsider, author):
        device(m)
    run(board.post, org, author.user, "Kabel liegen bereit", production=production)
    assert {u for u, _ in pushed} == {student.user, teacher.user}
    assert titles(pushed)[0] == "Chat: Schulkonzert"


def test_other_org_never_notified(org, other_org, show, make_member, pushed, device, run, planner):
    foreign = make_member(other_org)
    device(foreign)
    run(board.post, org, planner.user, "Hallo")
    assert pushed == []


# ---------- Erinnerungen ----------


def _at(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


@pytest.fixture
def tomorrow_job(org, student, make_production, make_job, make_assignment, device):
    production = make_production(org, "Schulkonzert", days_ahead=1)
    job = make_job(production, "Aufbau", start=time(14), end=time(16), meeting_point="Aula")
    device(student)
    return make_assignment(job, student, CONFIRMED)


def test_reminder_evening_before(tomorrow_job, pushed, run):
    today = timezone.localdate()
    assert run(send_due_reminders, now=_at(today, 17, 50)) == 0
    assert run(send_due_reminders, now=_at(today, 18, 0)) == 1
    assert titles(pushed) == ["Morgen 14:00 Uhr: Aufbau Schulkonzert"]
    assert pushed[0][1]["body"] == "Treffpunkt: Aula"
    assert run(send_due_reminders, now=_at(today, 18, 10)) == 0  # nur einmal


def test_reminder_hours_before(tomorrow_job, student, pushed, run):
    NotificationSettings.objects.create(user=student.user, reminder_mode="hours", reminder_hours=3)
    tomorrow = timezone.localdate() + timedelta(days=1)
    assert run(send_due_reminders, now=_at(tomorrow, 10, 50)) == 0
    assert run(send_due_reminders, now=_at(tomorrow, 11, 0)) == 1
    assert titles(pushed) == ["Heute 14:00 Uhr: Aufbau Schulkonzert"]


def test_moved_job_gets_new_reminder(tomorrow_job, pushed, run):
    today = timezone.localdate()
    run(send_due_reminders, now=_at(today, 18))
    job = tomorrow_job.job
    job.start_time = time(15)
    job.save()
    pushed.clear()
    assert run(send_due_reminders, now=_at(today, 19)) == 1
    assert titles(pushed) == ["Morgen 15:00 Uhr: Aufbau Schulkonzert"]


def test_no_reminder_for_requests_or_deleted(tomorrow_job, pushed, run):
    today = timezone.localdate()
    tomorrow_job.status = CrewAssignment.Status.REQUESTED
    tomorrow_job.save()
    assert run(send_due_reminders, now=_at(today, 18)) == 0
    tomorrow_job.status = CONFIRMED
    tomorrow_job.save()
    tomorrow_job.job.production.soft_delete()
    assert run(send_due_reminders, now=_at(today, 18)) == 0


def test_reminders_can_be_switched_off(tomorrow_job, student, pushed, run):
    NotificationSettings.objects.create(user=student.user, reminders=False)
    run(send_due_reminders, now=_at(timezone.localdate(), 18))
    assert pushed == []


# ---------- Erinnerungen vor Terminen ----------


@pytest.fixture
def meeting(org, student, device):
    day = timezone.localdate() + timedelta(days=1)
    event = Event.objects.create(
        organization=org,
        title="AG-Treffen",
        date=day,
        start_time=time(14),
        end_time=time(15, 30),
        location="Technikraum",
    )
    device(student)
    return EventAttendee.objects.create(
        organization=org, event=event, membership=student, status=EventAttendee.Status.CONFIRMED
    )


def test_event_reminder_evening_before(meeting, pushed, run):
    today = timezone.localdate()
    assert run(send_due_reminders, now=_at(today, 17, 50)) == 0
    assert run(send_due_reminders, now=_at(today, 18)) == 1
    assert titles(pushed) == ["Morgen 14:00 Uhr: AG-Treffen"]
    assert pushed[0][1]["body"] == "Ort: Technikraum"
    assert pushed[0][1]["url"] == f"/termine/{meeting.event_id}/"
    assert run(send_due_reminders, now=_at(today, 18, 10)) == 0


def test_event_reminder_hours_before_and_moved(meeting, student, pushed, run):
    NotificationSettings.objects.create(user=student.user, reminder_mode="hours", reminder_hours=2)
    tomorrow = timezone.localdate() + timedelta(days=1)
    assert run(send_due_reminders, now=_at(tomorrow, 12)) == 1
    event = meeting.event
    event.start_time = time(16)
    event.end_time = time(17)
    event.save()
    assert run(send_due_reminders, now=_at(tomorrow, 14)) == 1
    assert titles(pushed) == ["Heute 14:00 Uhr: AG-Treffen", "Heute 16:00 Uhr: AG-Treffen"]


@pytest.mark.parametrize("case", ["requested", "cancelled", "all_day", "muted"])
def test_no_event_reminder(meeting, student, pushed, run, case):
    if case == "requested":
        meeting.status = EventAttendee.Status.REQUESTED
        meeting.save()
    elif case == "cancelled":
        meeting.event.cancelled = True
        meeting.event.save()
    elif case == "all_day":
        meeting.event.start_time = meeting.event.end_time = None
        meeting.event.save()
    else:
        NotificationSettings.objects.create(user=student.user, reminders=False)
    run(send_due_reminders, now=_at(timezone.localdate(), 18))
    assert pushed == []
