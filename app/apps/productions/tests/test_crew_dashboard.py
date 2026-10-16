from datetime import time

from django.urls import reverse

from apps.organizations.permissions import Role
from apps.productions.models import CrewAssignment


def test_request_crew_and_student_accepts(org, planner_client, student, student_client, concert):
    job = concert.jobs.get(name="Aufbau")
    planner_client.post(
        reverse("productions:job_crew", args=[job.pk]),
        {"membership": student.pk, "role_label": "FOH", "status": "requested"},
    )

    assignment = CrewAssignment.objects.for_org(org).get()
    assert assignment.status == "requested" and assignment.role_label == "FOH"

    dashboard = student_client.get(reverse("productions:dashboard")).content.decode()
    assert "Crew-Anfragen offen" in dashboard

    student_client.post(
        reverse("productions:crew_respond", args=[assignment.pk]), {"antwort": "ja"}
    )
    assignment.refresh_from_db()
    assert assignment.is_confirmed


def test_decline_removes_request(student, student_client, concert, make_assignment):
    assignment = make_assignment(concert.jobs.first(), student)
    student_client.post(
        reverse("productions:crew_respond", args=[assignment.pk]), {"antwort": "nein"}
    )
    assert not CrewAssignment.objects.exists()


def test_cannot_answer_for_someone_else(org, make_member, login, student, concert, make_assignment):
    assignment = make_assignment(concert.jobs.first(), student)
    other = make_member(org, Role.STUDENT)

    response = login(other.user, org).post(
        reverse("productions:crew_respond", args=[assignment.pk]), {"antwort": "ja"}
    )

    assert response.status_code == 403
    assignment.refresh_from_db()
    assert not assignment.is_confirmed


def test_conflict_warning_then_assign_anyway(
    org, planner_client, student, concert, make_production, make_job, make_assignment
):
    other = make_production(org, "Elternabend", days_ahead=3)
    clash = make_job(other, "Ton", start=time(15), end=time(17))
    make_assignment(clash, student, status="confirmed")
    job = concert.jobs.get(name="Aufbau")  # 14–16 Uhr am selben Tag
    data = {"membership": student.pk, "role_label": "", "status": "confirmed"}

    response = planner_client.post(reverse("productions:job_crew", args=[job.pk]), data)
    assert response.status_code == 200
    assert "Überschneidung" in response.content.decode()
    assert not CrewAssignment.objects.filter(job=job).exists()

    planner_client.post(
        reverse("productions:job_crew", args=[job.pk]), {**data, "ignore_conflicts": "on"}
    )
    assert CrewAssignment.objects.get(job=job).is_confirmed


def test_no_conflict_for_adjacent_jobs(
    org, planner_client, student, concert, make_production, make_job, make_assignment
):
    other = make_production(org, "Probe", days_ahead=3)
    make_assignment(make_job(other, "Probe", start=time(16), end=time(17)), student)
    job = concert.jobs.get(name="Aufbau")  # endet 16 Uhr

    planner_client.post(
        reverse("productions:job_crew", args=[job.pk]),
        {"membership": student.pk, "status": "requested"},
    )
    assert CrewAssignment.objects.filter(job=job).exists()


def test_planner_removes_crew(planner_client, student, concert, make_assignment):
    assignment = make_assignment(concert.jobs.first(), student)
    planner_client.post(reverse("productions:crew_remove", args=[assignment.pk]))
    assert not CrewAssignment.objects.exists()


def test_dashboard_next_production_and_counts(
    org, student, student_client, concert, make_production, make_assignment
):
    make_production(org, "Sommerfest 2025", days_ahead=-30)
    make_production(org, "Theater-Premiere", days_ahead=20)
    make_assignment(concert.jobs.get(name="Aufbau"), student)
    make_assignment(concert.jobs.get(name="Show"), student, status="confirmed")

    response = student_client.get(reverse("productions:dashboard"))
    ctx = response.context
    content = response.content.decode()

    assert "Was steht an?" in content
    assert ctx["next_production"] == concert
    assert ctx["next_job"].name == "Aufbau"
    assert "Bühneneingang" in content
    assert len(ctx["upcoming"]) == 2
    assert ctx["open_request_count"] == 1

    jobs_view = student_client.get(reverse("productions:dashboard"), {"ansicht": "jobs"})
    jobs_content = jobs_view.content.decode()
    assert "Schulkonzert – Aufbau" in jobs_content
    assert "Annehmen" in jobs_content
    assert "Schulkonzert – Show" in jobs_content


def test_deleted_productions_disappear_from_dashboard(
    student, student_client, concert, make_assignment
):
    make_assignment(concert.jobs.first(), student)
    concert.soft_delete()

    ctx = student_client.get(reverse("productions:dashboard")).context
    assert ctx["next_production"] is None
    assert ctx["open_request_count"] == 0
