"""Einsatzübersicht: Stunden je Mitglied, Zeiträume, Korrektur, Rechte und PDF."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.organizations.permissions import Role
from apps.productions import hours
from apps.productions.models import CrewAssignment
from apps.scheduling.models import Event, EventAttendee

CONFIRMED = CrewAssignment.Status.CONFIRMED


def test_school_year_periods():
    options = {p.key: p for p in hours.periods(date(2026, 10, 17))}
    assert (options["schuljahr"].start, options["schuljahr"].end) == (
        date(2026, 8, 1),
        date(2027, 7, 31),
    )
    assert options["schuljahr"].label == "Schuljahr 2026/27"
    assert options["halbjahr1"].end == date(2027, 1, 31)
    assert options["halbjahr2"].start == date(2027, 2, 1)
    assert options["vorjahr"].start == date(2025, 8, 1)
    assert hours.periods(date(2027, 3, 1))[0].start == date(2026, 8, 1)


def test_custom_period_and_fallback():
    today = date(2026, 10, 17)
    custom = hours.period_from_request(
        {"zeitraum": "eigener", "von": "2026-09-01", "bis": "2026-09-30"}, today
    )
    assert (custom.start, custom.end) == (date(2026, 9, 1), date(2026, 9, 30))
    broken = hours.period_from_request({"zeitraum": "eigener", "von": "kaputt"}, today)
    assert broken.key == "schuljahr"


@pytest.fixture
def worked(org, student, make_production, make_job, make_assignment):
    """Emma: zwei vergangene Jobs (2 h, 3 h) und ein Termin (1,5 h), dazu Nicht-Zählendes."""
    past = make_production(org, "Herbstkonzert", days_ahead=-2)
    a1 = make_assignment(make_job(past, "Aufbau", start=time(14), end=time(16)), student, CONFIRMED)
    make_assignment(make_job(past, "Show", start=time(18), end=time(21)), student, CONFIRMED)
    make_assignment(make_job(past, "Abbau"), student)  # nur angefragt
    deleted = make_production(org, "Gelöscht", days_ahead=-2)
    make_assignment(make_job(deleted), student, CONFIRMED)
    deleted.soft_delete()
    future = make_production(org, "Später", days_ahead=5)
    make_assignment(make_job(future), student, CONFIRMED)

    day = timezone.localdate() - timedelta(days=1)
    meeting = Event.objects.create(
        organization=org, title="AG-Treffen", date=day, start_time=time(13), end_time=time(14, 30)
    )
    EventAttendee.objects.create(
        organization=org, event=meeting, membership=student, status=EventAttendee.Status.CONFIRMED
    )
    cancelled = Event.objects.create(
        organization=org,
        title="Abgesagt",
        date=day,
        start_time=time(9),
        end_time=time(10),
        cancelled=True,
    )
    EventAttendee.objects.create(
        organization=org,
        event=cancelled,
        membership=student,
        status=EventAttendee.Status.CONFIRMED,
    )
    return a1


def _period():
    today = timezone.localdate()
    return today - timedelta(days=30), today + timedelta(days=30)


def test_entries_and_total(student, worked):
    items = hours.entries(student, *_period())
    assert sorted((e.title, e.hours) for e in items) == [
        ("AG-Treffen", Decimal("1.50")),
        ("Herbstkonzert", Decimal("2.00")),
        ("Herbstkonzert", Decimal("3.00")),
    ]
    assert hours.total(items) == Decimal("6.50")


def test_correction_wins(student, worked):
    worked.corrected_hours = Decimal("2.75")
    worked.save()
    items = hours.entries(student, *_period())
    corrected = next(e for e in items if e.obj == worked)
    assert (corrected.is_corrected, corrected.calculated, corrected.hours) == (
        True,
        Decimal("2.00"),
        Decimal("2.75"),
    )
    assert hours.total(items) == Decimal("7.25")


def test_member_page_and_correction(org, student, worked, planner_client):
    url = reverse("productions:hours_member", args=[student.pk])
    content = planner_client.get(url).content.decode()
    assert "Herbstkonzert" in content and "6,5 h" in content
    assert "Später" not in content and "Gelöscht" not in content and "Abgesagt" not in content

    correct = reverse("productions:hours_correct_job", args=[worked.pk])
    response = planner_client.post(f"{correct}?next={url}", {"corrected_hours": "4"})
    assert response.url == url
    worked.refresh_from_db()
    assert worked.corrected_hours == Decimal("4")

    planner_client.post(correct, {"corrected_hours": ""})
    worked.refresh_from_db()
    assert worked.corrected_hours is None


def test_overview_for_planners(org, student, worked, planner_client):
    content = planner_client.get(reverse("productions:hours")).content.decode()
    assert "Emma" in content and "6,5 h" in content and "3 Einsätze" in content


def test_student_sees_only_own(org, student, student_client, make_member, worked):
    response = student_client.get(reverse("productions:hours"))
    assert response.url == reverse("productions:hours_member", args=[student.pk])
    assert student_client.get(response.url).status_code == 200
    other = make_member(org)
    assert (
        student_client.get(reverse("productions:hours_member", args=[other.pk])).status_code == 403
    )
    assert student_client.get(reverse("documents:hours_pdf", args=[other.pk])).status_code == 403
    correct = reverse("productions:hours_correct_job", args=[worked.pk])
    assert student_client.post(correct, {"corrected_hours": "9"}).status_code == 403


@pytest.mark.parametrize("role", [Role.OWNER, Role.ADMIN, Role.TEACHER])
def test_planners_may_correct(org, owner, make_member, login, worked, role):
    member = owner if role == Role.OWNER else make_member(org, role)
    client = login(member.user, org)
    url = reverse("productions:hours_correct_job", args=[worked.pk])
    assert client.get(url).status_code == 200


def test_foreign_objects_return_404(
    org, other_org, owner, login, make_member, make_production, make_job, make_assignment
):
    foreign_member = make_member(other_org)
    foreign = make_assignment(
        make_job(make_production(other_org, days_ahead=-1)), foreign_member, CONFIRMED
    )
    event = Event.objects.create(organization=other_org, title="Fremd", date=date(2026, 9, 1))
    attendee = EventAttendee.objects.create(
        organization=other_org, event=event, membership=foreign_member
    )
    client = login(owner.user, org)
    for url in [
        reverse("productions:hours_member", args=[foreign_member.pk]),
        reverse("productions:hours_correct_job", args=[foreign.pk]),
        reverse("productions:hours_correct_event", args=[attendee.pk]),
        reverse("documents:hours", args=[foreign_member.pk]),
        reverse("documents:hours_pdf", args=[foreign_member.pk]),
    ]:
        assert client.get(url).status_code == 404


def test_pdf_keeps_period(student, worked, planner_client):
    query = "zeitraum=vorjahr"
    preview = planner_client.get(
        reverse("documents:hours", args=[student.pk]) + "?" + query
    ).content.decode()
    pdf_url = reverse("documents:hours_pdf", args=[student.pk])
    assert f"{pdf_url}?{query}" in preview
    assert f"{pdf_url}?{query}&amp;download=1" in preview

    response = planner_client.get(pdf_url)
    assert response.content.startswith(b"%PDF")
    start = hours.periods()[0].start
    assert f"einsatzuebersicht-emma-{start:%Y-%m-%d}.pdf" in response["Content-Disposition"]
