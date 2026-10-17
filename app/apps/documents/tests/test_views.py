"""Vorschau und PDF: Inhalte, Dateinamen, Rechte je Rolle und Mandantentrennung."""

from datetime import time

import pytest
from django.urls import reverse

from apps.inventory import services as inventory_services
from apps.organizations.permissions import Role
from apps.productions.models import CrewAssignment


@pytest.fixture
def show(org, raster, monday, make_member, make_production, make_job, make_assignment):
    production = make_production(org, "Sommerkonzert", location_name="Aula", notes="Bitte schwarz")
    job = make_job(
        production, "Aufbau", day=monday, start=time(8), end=time(10), meeting_point="Bühneneingang"
    )
    emma = make_member(org, Role.STUDENT, display_name="Emma Schulz", grade="Q1")
    make_assignment(job, emma, CrewAssignment.Status.CONFIRMED, role_label="FOH")
    teacher = make_member(org, Role.TEACHER, display_name="Frau Muster")
    production.supervisors.add(teacher)
    return production


def _urls(production):
    job = production.jobs.get()
    return {
        "production_call_sheet": production.pk,
        "job_call_sheet": job.pk,
        "release_list": production.pk,
        "packing_list": production.pk,
    }


def test_call_sheet_preview_shows_jobs_and_crew(show, student_client):
    content = student_client.get(
        reverse("documents:production_call_sheet", args=[show.pk])
    ).content.decode()
    for text in [
        "Sommerkonzert",
        "Aufbau",
        "Bühneneingang",
        "Emma Schulz",
        "FOH",
        "zugesagt",
        "Frau Muster",
        "Bitte schwarz",
        "PDF herunterladen",
        "Teilen",
        "Drucken",
    ]:
        assert text in content
    assert reverse("documents:production_call_sheet_pdf", args=[show.pk]) in content


def test_job_call_sheet_shows_only_that_job(show, make_job, student_client):
    make_job(show, "Abbau")
    job = show.jobs.get(name="Aufbau")
    content = student_client.get(reverse("documents:job_call_sheet", args=[job.pk])).content
    assert b"Aufbau" in content and b"Abbau" not in content


@pytest.mark.parametrize(
    ("url_name", "filename"),
    [
        ("production_call_sheet_pdf", "call-sheet-sommerkonzert.pdf"),
        ("job_call_sheet_pdf", "call-sheet-sommerkonzert-aufbau.pdf"),
        ("release_list_pdf", "freistellungsliste-sommerkonzert.pdf"),
        ("packing_list_pdf", "packliste-sommerkonzert.pdf"),
    ],
)
def test_pdfs(show, planner_client, url_name, filename):
    pk = _urls(show)[url_name.removesuffix("_pdf")]
    url = reverse(f"documents:{url_name}", args=[pk])

    response = planner_client.get(url)
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert response["Content-Disposition"] == f'inline; filename="{filename}"'
    assert response["Cache-Control"] == "private, no-store"

    download = planner_client.get(url + "?download=1")
    assert download["Content-Disposition"] == f'attachment; filename="{filename}"'


def test_release_list_preview(show, planner_client):
    content = planner_client.get(reverse("documents:release_list", args=[show.pk])).content.decode()
    assert "Emma Schulz" in content and "1.–3. Stunde" in content and "Frau Muster" in content
    assert "kein Stundenraster" not in content


def test_release_list_hints_missing_raster(org, make_production, planner_client):
    production = make_production(org)
    content = planner_client.get(reverse("documents:release_list", args=[production.pk])).content
    assert b"kein Stundenraster" in content


def test_packing_list_preview_groups_by_category(org, show, planner_client, make_material):
    from apps.inventory.models import MaterialCategory

    lights = MaterialCategory.objects.for_org(org).get(name="Licht")
    planned = inventory_services.plan(show, make_material(org, "Lichtpult", category=lights), 2)
    inventory_services.set_packed(planned, "issued_at", True)
    content = planner_client.get(reverse("documents:packing_list", args=[show.pk])).content.decode()
    assert "Licht" in content and "Lichtpult" in content and "✓" in content


@pytest.mark.parametrize("role", [Role.OWNER, Role.ADMIN, Role.TEACHER, Role.STUDENT])
def test_rights_per_role(org, owner, show, make_member, login, role):
    member = owner if role == Role.OWNER else make_member(org, role)
    client = login(member.user, org)
    for url_name, pk in _urls(show).items():
        expected = 403 if url_name == "release_list" and role == Role.STUDENT else 200
        assert client.get(reverse(f"documents:{url_name}", args=[pk])).status_code == expected
        pdf = client.get(reverse(f"documents:{url_name}_pdf", args=[pk]))
        assert pdf.status_code == expected


def test_foreign_and_deleted_productions_return_404(
    org, owner, other_org, login, make_production, make_job, show
):
    foreign = make_production(other_org, "Fremdes Konzert")
    make_job(foreign)
    client = login(owner.user, org)
    for production in [foreign, show]:
        urls = _urls(production)
        if production is show:
            show.soft_delete()
        for url_name, pk in urls.items():
            assert client.get(reverse(f"documents:{url_name}", args=[pk])).status_code == 404
            assert client.get(reverse(f"documents:{url_name}_pdf", args=[pk])).status_code == 404


def test_detail_page_links_by_role(show, student_client, planner_client):
    url = reverse("productions:detail", args=[show.pk])
    release = reverse("documents:release_list", args=[show.pk])
    job_sheet = reverse("documents:job_call_sheet", args=[show.jobs.get().pk])

    student_page = student_client.get(url).content.decode()
    assert reverse("documents:production_call_sheet", args=[show.pk]) in student_page
    assert job_sheet in student_page
    assert release not in student_page
    assert release in planner_client.get(url).content.decode()


def test_packing_checklist_links_pdf(show, student_client, make_material, org):
    inventory_services.plan(show, make_material(org, "Kabel"), 1)
    content = student_client.get(reverse("inventory:packing_list", args=[show.pk])).content
    assert reverse("documents:packing_list", args=[show.pk]).encode() in content
