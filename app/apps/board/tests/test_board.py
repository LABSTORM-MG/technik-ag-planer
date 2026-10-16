from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.board import services
from apps.board.models import FORMER_MEMBER, Message, ReadMarker
from apps.board.tasks import announce_open_jobs
from apps.board.templatetags.board import board_day
from apps.organizations.permissions import Role
from apps.productions.models import CrewAssignment, ProductionStatus
from apps.productions.services import copy_production

pytestmark = pytest.mark.django_db


def system_texts(org):
    return list(
        Message.objects.for_org(org).filter(kind=Message.Kind.SYSTEM).values_list("text", flat=True)
    )


@pytest.fixture
def chat(concert):
    concert.chat_enabled = True
    concert.save()
    return concert


# ---------- Senden, Anzeigen, Bearbeiten ----------


def test_board_shows_messages_and_marks_own(student_client, student, planner, org):
    services.post(org, planner.user, "Hallo AG")
    services.post(org, student.user, "Hi!")

    response = student_client.get(reverse("board:index"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Hallo AG" in content and "Hi!" in content
    assert content.count("message--own") == 1
    assert "Ali Admin" in content
    assert "Nachricht schreiben …" in content


def test_send_message(student_client, org, student):
    response = student_client.post(reverse("board:send"), {"text": "  Wer kommt mit?  "})

    assert response.status_code == 302
    assert response.url == reverse("board:index") + "#ende"
    message = Message.objects.for_org(org).get(kind=Message.Kind.USER)
    assert (message.text, message.author, message.production) == (
        "Wer kommt mit?",
        student.user,
        None,
    )


def test_send_by_script_returns_no_content(student_client):
    response = student_client.post(reverse("board:send"), {"text": "x"}, headers={"X-Board": "1"})

    assert response.status_code == 204


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_message_is_rejected(student_client, org, text):
    response = student_client.post(reverse("board:send"), {"text": text}, headers={"X-Board": "1"})

    assert response.status_code == 400
    assert not Message.objects.for_org(org).filter(kind=Message.Kind.USER).exists()


def test_send_into_production_chat(student_client, chat, org):
    student_client.post(reverse("board:send"), {"text": "Mikros?", "produktion": chat.pk})

    assert Message.objects.for_org(org).get(text="Mikros?").production == chat


def test_edit_own_message_shows_hint(student_client, student, org):
    message = services.post(org, student.user, "Tippfeler")

    response = student_client.post(reverse("board:edit", args=[message.pk]), {"text": "Tippfehler"})

    assert response.status_code == 302
    message.refresh_from_db()
    assert message.text == "Tippfehler" and message.edited_at
    assert "bearbeitet" in student_client.get(reverse("board:index")).content.decode()


def test_edit_form_renders_in_sheet(student_client, student, org):
    message = services.post(org, student.user, "Text")

    response = student_client.get(
        reverse("board:edit", args=[message.pk]), headers={"X-Sheet": "1"}
    )

    assert response.status_code == 200
    assert "<html" not in response.content.decode()


def test_former_member_label(student_client, org, make_user):
    user = make_user()
    services.post(org, user, "Alte Nachricht")
    user.delete()

    assert FORMER_MEMBER in student_client.get(reverse("board:index")).content.decode()


def test_older_messages_are_paged(student_client, student, org):
    for i in range(55):
        services.post(org, student.user, f"Nachricht {i:02d}")

    content = student_client.get(reverse("board:index")).content.decode()
    assert "Nachricht 54" in content and "Nachricht 04" not in content
    assert "Ältere Nachrichten laden" in content

    oldest_shown = Message.objects.for_org(org).get(text="Nachricht 05")
    older = student_client.get(reverse("board:index"), {"vor": oldest_shown.pk}).content.decode()
    assert "Nachricht 04" in older and "Nachricht 05" not in older


def test_new_messages_fragment(student_client, planner, org):
    first = services.post(org, planner.user, "Erste")
    services.post(org, planner.user, "Zweite")

    response = student_client.get(reverse("board:new"), {"nach": first.pk})

    content = response.content.decode()
    assert response.status_code == 200
    assert "Zweite" in content and "Erste" not in content
    assert "<html" not in content
    assert student_client.get(reverse("board:new"), {"nach": 10**9}).status_code == 204


def test_new_messages_fragment_marks_read(student_client, student, planner, org):
    services.post(org, planner.user, "Neu")
    assert services.unread_count(student) >= 1

    student_client.get(reverse("board:new"), {"nach": 0})

    assert services.unread_count(student) == 0


# ---------- Rechte je Rolle ----------


def test_only_author_may_edit(org, make_member, login, student):
    message = services.post(org, student.user, "Meins")
    for role in [Role.OWNER, Role.ADMIN, Role.TEACHER, Role.STUDENT]:
        other = make_member(org, role)
        client = login(other.user, org)
        assert client.get(reverse("board:edit", args=[message.pk])).status_code == 403
        assert (
            client.post(reverse("board:edit", args=[message.pk]), {"text": "x"}).status_code == 403
        )


def test_system_messages_cannot_be_edited(org, owner, login, make_production):
    make_production(org)
    message = Message.objects.for_org(org).filter(kind=Message.Kind.SYSTEM).first()

    response = login(owner.user, org).get(reverse("board:edit", args=[message.pk]))

    assert response.status_code == 403


def test_author_may_delete_own_message(student_client, student, org):
    message = services.post(org, student.user, "Weg damit")

    response = student_client.post(reverse("board:delete", args=[message.pk]))

    assert response.status_code == 302
    assert not Message.objects.filter(pk=message.pk).exists()


@pytest.mark.parametrize(
    ("role", "allowed"),
    [(Role.OWNER, True), (Role.ADMIN, True), (Role.TEACHER, True), (Role.STUDENT, False)],
)
def test_moderation_of_other_messages(org, make_member, login, student, role, allowed):
    message = services.post(org, student.user, "Unpassend")
    moderator = make_member(org, role)

    response = login(moderator.user, org).post(reverse("board:delete", args=[message.pk]))

    assert response.status_code == (302 if allowed else 403)
    assert Message.objects.filter(pk=message.pk).exists() is not allowed


def test_students_cannot_delete_system_messages(student_client, org, make_production):
    make_production(org)
    message = Message.objects.for_org(org).filter(kind=Message.Kind.SYSTEM).first()

    assert student_client.post(reverse("board:delete", args=[message.pk])).status_code == 403


def test_delete_requires_post(student_client, student, org):
    message = services.post(org, student.user, "x")

    assert student_client.get(reverse("board:delete", args=[message.pk])).status_code == 405


@pytest.mark.parametrize("role", [Role.OWNER, Role.ADMIN, Role.TEACHER, Role.STUDENT])
def test_all_roles_can_use_board(org, make_member, login, role):
    client = login(make_member(org, role).user, org)

    assert client.get(reverse("board:index")).status_code == 200
    assert client.post(reverse("board:send"), {"text": "Hallo"}).status_code == 302


def test_board_requires_organization(login, make_user):
    response = login(make_user()).get(reverse("board:index"))

    assert response.status_code == 302
    assert response.url == reverse("organizations:no_organization")


# ---------- Mandantentrennung ----------


def test_foreign_messages_are_not_found(student_client, other_org, make_member):
    stranger = make_member(other_org, Role.OWNER)
    foreign = services.post(other_org, stranger.user, "Geheim")

    assert student_client.get(reverse("board:edit", args=[foreign.pk])).status_code == 404
    assert student_client.post(reverse("board:delete", args=[foreign.pk])).status_code == 404
    assert "Geheim" not in student_client.get(reverse("board:index")).content.decode()
    assert "Geheim" not in student_client.get(reverse("board:new")).content.decode()


def test_foreign_production_chats_are_not_found(student_client, other_org, make_production):
    foreign = make_production(other_org, chat_enabled=True)

    assert student_client.get(reverse("board:production", args=[foreign.pk])).status_code == 404
    assert student_client.get(reverse("board:new"), {"produktion": foreign.pk}).status_code == 404
    response = student_client.post(reverse("board:send"), {"text": "x", "produktion": foreign.pk})
    assert response.status_code == 404
    assert not Message.objects.filter(production=foreign).exists()


def test_counts_ignore_other_organizations(student, other_org, make_member, make_production):
    stranger = make_member(other_org, Role.OWNER)
    make_production(other_org, chat_enabled=True)
    services.post(other_org, stranger.user, "Fremd")

    assert services.nav_unread_count(student) == services.unread_count(student)
    assert services.chat_bar(student) == []


# ---------- Produktions-Chats ----------


def test_production_chat_page(student_client, chat, planner, org):
    services.post(org, planner.user, "Nur im Chat", chat)
    services.post(org, planner.user, "Nur im Board")

    content = student_client.get(reverse("board:production", args=[chat.pk])).content.decode()

    assert "Nur im Chat" in content and "Nur im Board" not in content
    assert reverse("productions:detail", args=[chat.pk]) in content


def test_chat_must_be_enabled(student_client, concert):
    assert student_client.get(reverse("board:production", args=[concert.pk])).status_code == 404


def test_chat_of_deleted_production_is_gone(student_client, chat, planner, org):
    message = services.post(org, planner.user, "x", chat)
    chat.soft_delete()

    assert student_client.get(reverse("board:production", args=[chat.pk])).status_code == 404
    assert student_client.post(reverse("board:delete", args=[message.pk])).status_code == 404


def test_production_detail_links_chat(planner_client, chat, concert):
    url = reverse("board:production", args=[chat.pk])

    assert url in planner_client.get(reverse("productions:detail", args=[chat.pk])).content.decode()


def test_chat_bar_hides_chats_three_days_after_end(student, org, make_production):
    today = timezone.localdate()
    recent = make_production(org, name="Gerade vorbei", days_ahead=-3, chat_enabled=True)
    make_production(org, name="Lange her", days_ahead=-4, chat_enabled=True)
    make_production(org, name="Ohne Chat", days_ahead=1)

    assert [p.name for p in services.chat_bar(student, today)] == [recent.name]


def test_old_chat_stays_reachable_from_production(student_client, org, make_production):
    old = make_production(org, days_ahead=-30, chat_enabled=True)

    assert student_client.get(reverse("board:production", args=[old.pk])).status_code == 200


def test_chat_bar_puts_unread_first(student, planner, org, make_production):
    first = make_production(org, name="Bald", days_ahead=1, chat_enabled=True)
    later = make_production(org, name="Später", days_ahead=10, chat_enabled=True)
    services.post(org, planner.user, "Neu hier", later)

    bar = services.chat_bar(student)

    assert [p.name for p in bar] == [later.name, first.name]
    assert (bar[0].unread, bar[1].unread) == (1, 0)


def test_board_shows_chat_bar(student_client, chat):
    content = student_client.get(reverse("board:index")).content.decode()

    assert "chat-bar" in content
    assert reverse("board:production", args=[chat.pk]) in content


# ---------- Ungelesen ----------


def test_unread_counts_and_reset_on_open(student_client, student, planner, org):
    services.mark_read(student, None, Message.objects.for_org(org).latest("id").pk)
    services.post(org, planner.user, "Eins")
    services.post(org, planner.user, "Zwei")
    services.post(org, student.user, "Eigene zählt nicht")

    assert services.unread_count(student) == 2
    assert services.nav_unread_count(student) == 2

    student_client.get(reverse("board:index"))

    assert services.unread_count(student) == 0
    assert ReadMarker.objects.get(membership=student, production=None).last_read_id


def test_without_marker_only_messages_since_joining_count(org, planner, make_member):
    services.post(org, planner.user, "Vor dem Beitritt")
    Message.objects.for_org(org).update(created_at=timezone.now() - timedelta(days=1))
    newcomer = make_member(org, Role.STUDENT)

    # nur die Systemmeldung „Neues Mitglied“
    assert services.unread_count(newcomer) == 1


def test_nav_counts_board_and_own_productions_only(student, planner, org, chat, make_production):
    other = make_production(org, name="Fremde Produktion", chat_enabled=True)
    services.mark_read(student, None, Message.objects.for_org(org).latest("id").pk)
    services.post(org, planner.user, "Im fremden Chat", other)
    services.post(org, planner.user, "Im eigenen Chat", chat)

    assert services.nav_unread_count(student) == 0

    CrewAssignment.objects.create(organization=org, job=chat.jobs.first(), membership=student)
    assert services.nav_unread_count(student) == 1


def test_badge_in_navigation(student_client, student, planner, org):
    services.mark_read(student, None, Message.objects.for_org(org).latest("id").pk)
    services.post(org, planner.user, "Neu")

    content = student_client.get(reverse("productions:dashboard")).content.decode()

    assert 'aria-label="1 ungelesen"' in content


# ---------- Systemmeldungen ----------


def test_new_production_and_copy_announce(org, make_production):
    production = make_production(org, name="Abiball")
    copy_production(production)

    assert "Neue Produktion: Abiball" in system_texts(org)
    assert "Neue Produktion: Abiball (Kopie)" in system_texts(org)
    message = Message.objects.for_org(org).get(text="Neue Produktion: Abiball")
    assert message.link_production == production


def test_status_date_and_location_changes_announce(org, make_production):
    production = make_production(org, name="Konzert")
    production.status = ProductionStatus.objects.for_org(org).get(system_key="confirmed")
    production.start_date = production.end_date = date(2026, 11, 20)
    production.location_name = "Aula"
    production.save()

    texts = system_texts(org)
    assert "Konzert: Status jetzt Bestätigt" in texts
    assert "Konzert: neues Datum Fr., 20.11.2026" in texts
    assert "Konzert: neuer Ort Aula" in texts


def test_unrelated_changes_do_not_announce(org, make_production):
    production = make_production(org)
    before = len(system_texts(org))
    production.notes = "Neue Notiz"
    production.save()

    assert len(system_texts(org)) == before


def test_delete_and_restore_announce(org, make_production):
    production = make_production(org, name="Theater")
    production.soft_delete()
    production.restore()

    texts = system_texts(org)
    assert "Produktion gelöscht: Theater" in texts
    assert "Produktion wiederhergestellt: Theater" in texts
    deleted = Message.objects.for_org(org).get(text="Produktion gelöscht: Theater")
    assert deleted.link_production is None


def test_link_to_deleted_production_is_hidden(student_client, org, make_production):
    production = make_production(org, name="Weg")
    production.soft_delete()

    content = student_client.get(reverse("board:index")).content.decode()

    assert "Neue Produktion: Weg" in content
    assert reverse("productions:detail", args=[production.pk]) not in content


def test_new_member_announces(org, make_member):
    make_member(org, Role.STUDENT, display_name="Neo")

    assert "Neues Mitglied: Neo" in system_texts(org)


def test_open_jobs_are_announced_once(org, make_production, make_job, make_member):
    today = timezone.localdate()
    production = make_production(org, name="Schulkonzert", days_ahead=3)
    job = make_job(production, name="Aufbau", crew_needed=3)
    make_job(production, name="Show", crew_needed=1)
    make_job(production, name="Abbau")  # ohne Angabe: keine Meldung
    CrewAssignment.objects.create(
        organization=org,
        job=job,
        membership=make_member(org),
        status=CrewAssignment.Status.CONFIRMED,
    )
    CrewAssignment.objects.create(organization=org, job=job, membership=make_member(org))
    show = production.jobs.get(name="Show")
    CrewAssignment.objects.create(
        organization=org,
        job=show,
        membership=make_member(org),
        status=CrewAssignment.Status.CONFIRMED,
    )

    assert announce_open_jobs(today) == 1
    assert announce_open_jobs(today) == 0
    assert "Aufbau Schulkonzert: noch 2 Plätze frei" in system_texts(org)


def test_open_jobs_ignore_other_days_and_deleted(org, make_production, make_job):
    make_job(make_production(org, days_ahead=4), crew_needed=2)
    deleted = make_production(org, days_ahead=3)
    make_job(deleted, crew_needed=2)
    deleted.soft_delete()

    assert announce_open_jobs(timezone.localdate()) == 0


def test_post_system_is_idempotent_with_key(org):
    assert services.post_system(org, "Material defekt: Mischpult", key="defekt-1")
    assert services.post_system(org, "Material defekt: Mischpult", key="defekt-1") is None


# ---------- Hilfen ----------


def test_board_day_labels():
    today = timezone.localdate()

    assert board_day(today) == "Heute"
    assert board_day(today - timedelta(days=1)) == "Gestern"
    assert board_day(date(2026, 10, 14)) == "Mi., 14.10.2026"


def test_day_separators_in_board(student_client, student, org):
    old = services.post(org, student.user, "Alt")
    Message.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=1))
    services.post(org, student.user, "Neu")

    content = student_client.get(reverse("board:index")).content.decode()

    assert "Gestern" in content and "Heute" in content


def test_author_color_is_stable_palette_key():
    assert services.author_color(7) == services.author_color(7)
    assert services.author_color(7) in services.AUTHOR_COLORS
    assert services.author_color(None) == "grey"
