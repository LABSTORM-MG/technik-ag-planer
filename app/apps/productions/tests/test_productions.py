from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.organizations.permissions import Role
from apps.productions.models import (
    Category,
    CrewAssignment,
    Job,
    Production,
    ProductionStatus,
    Todo,
)
from apps.productions.tasks import purge_deleted_productions


def _form_data(org, **overrides):
    today = timezone.localdate()
    data = {
        "name": "Abiball",
        "category": Category.objects.for_org(org).first().pk,
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=1)).isoformat(),
        "status": ProductionStatus.planning_for(org).pk,
        "location_name": "Aula",
        "address": "",
        "notes": "",
        "jobs-TOTAL_FORMS": "2",
        "jobs-INITIAL_FORMS": "0",
        "jobs-MIN_NUM_FORMS": "0",
        "jobs-MAX_NUM_FORMS": "1000",
        "jobs-0-name": "Aufbau",
        "jobs-0-date": today.isoformat(),
        "jobs-0-start_time": "14:00",
        "jobs-0-end_time": "16:00",
        "jobs-0-meeting_point": "Bühneneingang",
        "jobs-1-name": "",
        "jobs-1-date": "",
        "jobs-1-start_time": "",
        "jobs-1-end_time": "",
        "jobs-1-meeting_point": "",
    }
    data.update(overrides)
    return data


def test_new_org_gets_default_categories_and_statuses(make_org):
    org = make_org()
    assert [c.name for c in Category.objects.for_org(org)] == [
        "Schulfest",
        "Theater",
        "Konzert",
        "Sonstiges",
    ]
    assert set(ProductionStatus.objects.for_org(org).values_list("system_key", flat=True)) == {
        "planning",
        "confirmed",
    }


def test_create_production_with_jobs(org, planner_client):
    response = planner_client.post(reverse("productions:create"), _form_data(org))

    production = Production.objects.for_org(org).get()
    assert response.url == reverse("productions:detail", args=[production.pk])
    assert production.status.is_planning
    assert [j.name for j in production.jobs.all()] == ["Aufbau"]
    assert production.jobs.get().organization == org


def test_job_outside_production_period_is_rejected(org, planner_client):
    later = (timezone.localdate() + timedelta(days=10)).isoformat()
    response = planner_client.post(
        reverse("productions:create"), _form_data(org, **{"jobs-0-date": later})
    )

    assert response.status_code == 200
    assert not Production.objects.exists()
    assert "im Zeitraum" in response.content.decode()


def test_end_before_start_is_rejected(org, planner_client):
    today = timezone.localdate()
    response = planner_client.post(
        reverse("productions:create"),
        _form_data(org, end_date=(today - timedelta(days=1)).isoformat()),
    )
    assert response.status_code == 200
    assert not Production.objects.exists()


def test_form_rejects_category_of_other_org(org, other_org, planner_client):
    foreign = Category.objects.for_org(other_org).first()
    response = planner_client.post(
        reverse("productions:create"), _form_data(org, category=foreign.pk)
    )
    assert response.status_code == 200
    assert not Production.objects.exists()


def test_form_rejects_status_of_other_org(org, other_org, planner_client):
    foreign = ProductionStatus.planning_for(other_org)
    planner_client.post(reverse("productions:create"), _form_data(org, status=foreign.pk))
    assert not Production.objects.exists()


def test_edit_updates_and_deletes_jobs(org, planner_client, concert):
    jobs = list(concert.jobs.all())
    data = _form_data(
        org,
        name="Schulkonzert 2026",
        start_date=concert.start_date.isoformat(),
        end_date=concert.end_date.isoformat(),
        **{
            "jobs-TOTAL_FORMS": "2",
            "jobs-INITIAL_FORMS": "2",
            "jobs-0-id": jobs[0].pk,
            "jobs-0-name": "Aufbau",
            "jobs-0-date": concert.start_date.isoformat(),
            "jobs-0-start_time": "13:00",
            "jobs-0-end_time": "16:00",
            "jobs-1-id": jobs[1].pk,
            "jobs-1-name": "Show",
            "jobs-1-date": concert.start_date.isoformat(),
            "jobs-1-start_time": "18:00",
            "jobs-1-end_time": "21:00",
            "jobs-1-DELETE": "on",
        },
    )
    planner_client.post(reverse("productions:edit", args=[concert.pk]), data)

    concert.refresh_from_db()
    assert concert.name == "Schulkonzert 2026"
    assert [(j.name, j.start_time) for j in concert.jobs.all()] == [("Aufbau", time(13))]


def test_change_status_directly(org, planner_client, concert):
    confirmed = ProductionStatus.objects.for_org(org).get(system_key="confirmed")
    planner_client.post(reverse("productions:status", args=[concert.pk]), {"status": confirmed.pk})
    concert.refresh_from_db()
    assert concert.status == confirmed


def test_copy_without_crew_and_reset_status(org, planner_client, concert, student, make_assignment):
    confirmed = ProductionStatus.objects.for_org(org).get(system_key="confirmed")
    concert.status = confirmed
    concert.save()
    make_assignment(concert.jobs.first(), student)
    Todo.objects.create(organization=org, production=concert, text="Kabel prüfen")
    Todo.objects.create(organization=org, production=concert, text="Erledigt", done=True)

    response = planner_client.post(reverse("productions:copy", args=[concert.pk]))

    copy = Production.objects.for_org(org).exclude(pk=concert.pk).get()
    assert response.url == reverse("productions:edit", args=[copy.pk])
    assert copy.status.is_planning
    assert copy.jobs.count() == 2
    assert not CrewAssignment.objects.filter(job__production=copy).exists()
    assert [t.text for t in copy.todos.all()] == ["Kabel prüfen"]


def test_soft_delete_restore_and_purge(org, planner_client, concert):
    planner_client.post(reverse("productions:delete", args=[concert.pk]))
    assert not Production.objects.filter(pk=concert.pk).exists()
    assert Production.all_objects.filter(pk=concert.pk).exists()
    assert concert.name in planner_client.get(reverse("productions:trash")).content.decode()
    assert planner_client.get(reverse("productions:detail", args=[concert.pk])).status_code == 404

    planner_client.post(reverse("productions:restore", args=[concert.pk]))
    assert Production.objects.filter(pk=concert.pk).exists()

    concert.soft_delete()
    Production.all_objects.filter(pk=concert.pk).update(
        deleted_at=timezone.now() - timedelta(days=7, minutes=1)
    )
    purge_deleted_productions.delay()
    assert not Production.all_objects.filter(pk=concert.pk).exists()
    assert not Job.objects.filter(production_id=concert.pk).exists()


def test_purge_keeps_recently_deleted(concert):
    concert.soft_delete()
    purge_deleted_productions.delay()
    assert Production.all_objects.filter(pk=concert.pk).exists()


def test_list_upcoming_past_search_and_filter(org, member_client, make_production):
    theater = Category.objects.for_org(org).get(name="Theater")
    make_production(org, "Theater-Premiere", category=theater)
    make_production(org, "Schulkonzert")
    make_production(org, "Sommerfest 2025", days_ahead=-30)

    content = member_client.get(reverse("productions:list")).content.decode()
    upcoming, past = content.split("Vergangene Produktionen anzeigen", 1)
    assert "Theater-Premiere" in upcoming and "Schulkonzert" in upcoming
    assert "Sommerfest 2025" in past
    assert "(1)" in past

    filtered = member_client.get(reverse("productions:list"), {"kategorie": theater.pk})
    assert "Theater-Premiere" in filtered.content.decode()
    assert "Schulkonzert" not in filtered.content.decode()

    searched = member_client.get(reverse("productions:list"), {"q": "konzert"})
    assert "Schulkonzert" in searched.content.decode()
    assert "Theater-Premiere" not in searched.content.decode()


def test_detail_shows_location_and_navigation(member_client, concert):
    content = member_client.get(reverse("productions:detail", args=[concert.pk])).content.decode()
    assert "Aula" in content
    assert "Navigation starten" in content
    assert "google.com/maps/dir" in content


def test_all_members_create_toggle_and_delete_todos(org, student_client, concert):
    content = student_client.get(reverse("productions:detail", args=[concert.pk])).content.decode()
    assert "+ To-do" in content

    student_client.post(
        reverse("productions:todo_create", args=[concert.pk]), {"text": "Funkmikros laden"}
    )
    todo = Todo.objects.for_org(org).get()

    student_client.post(reverse("productions:todo_toggle", args=[todo.pk]))
    todo.refresh_from_db()
    assert todo.done and todo.done_by is not None

    student_client.post(reverse("productions:todo_delete", args=[todo.pk]))
    assert not Todo.objects.exists()


def test_palette_has_twelve_colors_with_tokens():
    from pathlib import Path

    from apps.productions.palette import Color

    app_dir = Path(__file__).resolve().parents[3]
    tokens = (app_dir / "static/css/tokens.css").read_text()
    css = (app_dir / "static/css/app.css").read_text()
    assert len(Color) == 12
    for color in Color:
        assert f"--palette-{color.value}:" in tokens
        assert f".color-{color.value} " in css


def test_teacher_registers_as_supervisor(org, make_member, login, concert):
    teacher = make_member(org, Role.TEACHER, display_name="Frau Lehmann")
    client = login(teacher.user, org)

    client.post(reverse("productions:supervise", args=[concert.pk]))
    assert teacher in concert.supervisors.all()
    assert (
        "Frau Lehmann"
        in client.get(reverse("productions:detail", args=[concert.pk])).content.decode()
    )

    client.post(reverse("productions:supervise", args=[concert.pk]))
    assert teacher not in concert.supervisors.all()


@pytest.mark.parametrize("role", [Role.OWNER, Role.ADMIN, Role.STUDENT])
def test_only_teachers_can_supervise(org, make_member, login, concert, role):
    membership = make_member(org, role)
    response = login(membership.user, org).post(reverse("productions:supervise", args=[concert.pk]))
    assert response.status_code == 403


def test_job_create_and_delete(org, planner_client, concert):
    planner_client.post(
        reverse("productions:job_create", args=[concert.pk]),
        {
            "name": "Abbau",
            "date": concert.start_date.isoformat(),
            "start_time": "21:00",
            "end_time": "22:30",
            "meeting_point": "",
        },
    )
    abbau = concert.jobs.get(name="Abbau")
    planner_client.post(reverse("productions:job_delete", args=[abbau.pk]))
    assert not concert.jobs.filter(name="Abbau").exists()


def test_new_menu_links_production_form(planner_client):
    content = planner_client.get(reverse("productions:dashboard")).content.decode()
    sheet = content.split('id="sheet-new"', 1)[1].split("</dialog>", 1)[0]
    assert reverse("productions:create") in sheet


def test_form_as_sheet_fragment(planner_client):
    response = planner_client.get(reverse("productions:create"), HTTP_X_SHEET="1")
    content = response.content.decode()
    assert "<html" not in content
    assert 'name="name"' in content
