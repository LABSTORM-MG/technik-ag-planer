"""Konto löschen: Einsätze und Nachrichten bleiben anonym erhalten (Abschnitt 2)."""

from datetime import time

import pytest
from django.urls import reverse

from apps.accounts.models import FORMER_MEMBER, User
from apps.board.models import Message
from apps.organizations import services as org_services
from apps.organizations.models import Invitation, Membership
from apps.organizations.permissions import Role
from apps.productions.models import CrewAssignment
from apps.scheduling.models import Event, EventAttendee, Unavailability
from conftest import PASSWORD


@pytest.fixture
def history(org, student, owner, make_production, make_job, make_assignment):
    production = make_production(org, "Sommerfest")
    job = make_job(production, "Aufbau", start=time(14), end=time(16))
    assignment = make_assignment(job, student, CrewAssignment.Status.CONFIRMED, role_label="FOH")
    event = Event.objects.create(organization=org, title="AG-Treffen", date=production.start_date)
    attendee = EventAttendee.objects.create(organization=org, event=event, membership=student)
    Message.objects.create(organization=org, author=student.user, text="Bin dabei!")
    Unavailability.objects.create(
        organization=org,
        membership=student,
        start_date=production.start_date,
        end_date=production.start_date,
    )
    Invitation.objects.create(
        organization=org,
        email=student.user.email,
        role=Role.STUDENT,
        token_hash="x" * 64,
        expires_at=production.created_at,
    )
    return {"production": production, "job": job, "assignment": assignment, "attendee": attendee}


def _assert_anonymous(history, client):
    assignment = CrewAssignment.objects.get(pk=history["assignment"].pk)
    attendee = EventAttendee.objects.get(pk=history["attendee"].pk)
    assert assignment.membership is None and assignment.person == FORMER_MEMBER
    assert attendee.membership is None and attendee.person == FORMER_MEMBER
    production = history["production"]
    for url in [
        reverse("productions:detail", args=[production.pk]),
        reverse("documents:production_call_sheet", args=[production.pk]),
    ]:
        assert FORMER_MEMBER in client.get(url).content.decode()
    ics = client.get(reverse("scheduling:ics_job", args=[history["job"].pk])).content.decode()
    assert FORMER_MEMBER in ics


def test_delete_account(org, owner, student, student_client, login, history):
    url = reverse("accounts:delete")
    assert "Ehemaliges Mitglied" in student_client.get(url).content.decode()

    response = student_client.post(url, {"password": PASSWORD, "confirm": "on"})

    assert response.url == reverse("accounts:login")
    assert not User.objects.filter(pk=student.user_id).exists()
    assert not Membership.objects.filter(pk=student.pk).exists()
    assert not Unavailability.objects.exists()
    assert not Invitation.objects.exists()
    assert Message.objects.get(text="Bin dabei!").author_name == FORMER_MEMBER
    assert student_client.get(reverse("productions:dashboard")).status_code == 302
    _assert_anonymous(history, login(owner.user, org))


def test_wrong_password_or_missing_confirmation(student, student_client):
    url = reverse("accounts:delete")
    student_client.post(url, {"password": "falsch", "confirm": "on"})
    student_client.post(url, {"password": PASSWORD})
    assert User.objects.filter(pk=student.user_id).exists()


def test_owner_must_transfer_first(org, owner, login):
    client = login(owner.user, org)
    content = client.get(reverse("accounts:delete")).content.decode()
    assert "Ownership" in content
    client.post(reverse("accounts:delete"), {"password": PASSWORD, "confirm": "on"})
    assert User.objects.filter(pk=owner.user_id).exists()


def test_removing_member_keeps_assignments(org, owner, student, login, history):
    org_services.remove_member(student)
    _assert_anonymous(history, login(owner.user, org))
