"""Rechte je Rolle und Mandantentrennung für alle Produktions-Views."""

import pytest
from django.urls import reverse

from apps.organizations.permissions import Role
from apps.productions.models import Category, CrewAssignment, ProductionStatus, Todo


@pytest.fixture
def foreign(other_org, make_member, make_production, make_job, make_assignment):
    """Daten der anderen AG."""
    production = make_production(other_org, "Fremdes Konzert")
    job = make_job(production)
    member = make_member(other_org, Role.STUDENT, display_name="Sam Süd")
    assignment = make_assignment(job, member)
    todo = Todo.objects.create(organization=other_org, production=production, text="Fremd")
    status = ProductionStatus.objects.create(organization=other_org, name="Fremd")
    return {
        "production": production,
        "job": job,
        "assignment": assignment,
        "todo": todo,
        "category": Category.objects.for_org(other_org).first(),
        "status": status,
        "member": member,
    }


FOREIGN_URLS = [
    ("get", "productions:detail", "production"),
    ("get", "productions:edit", "production"),
    ("post", "productions:status", "production"),
    ("post", "productions:copy", "production"),
    ("post", "productions:delete", "production"),
    ("post", "productions:restore", "production"),
    ("get", "productions:job_create", "production"),
    ("post", "productions:todo_create", "production"),
    ("get", "productions:job_edit", "job"),
    ("post", "productions:job_delete", "job"),
    ("get", "productions:job_crew", "job"),
    ("post", "productions:crew_remove", "assignment"),
    ("post", "productions:crew_respond", "assignment"),
    ("post", "productions:todo_toggle", "todo"),
    ("post", "productions:todo_delete", "todo"),
    ("get", "productions:category_edit", "category"),
    ("post", "productions:category_delete", "category"),
    ("post", "productions:category_move", "category"),
    ("get", "productions:status_edit", "status"),
    ("post", "productions:status_delete", "status"),
    ("post", "productions:status_move", "status"),
]


@pytest.mark.parametrize(("method", "url_name", "target"), FOREIGN_URLS)
def test_foreign_objects_return_404(org, owner, login, foreign, method, url_name, target):
    client = login(owner.user, org)
    response = getattr(client, method)(reverse(url_name, args=[foreign[target].pk]))
    assert response.status_code == 404


def test_lists_and_dashboard_show_only_own_org(org, owner, login, foreign, make_production):
    make_production(org, "Eigenes Konzert")
    client = login(owner.user, org)

    for url in [
        reverse("productions:list"),
        reverse("productions:dashboard"),
        reverse("productions:trash"),
    ]:
        content = client.get(url).content.decode()
        assert "Fremdes Konzert" not in content
    assert "Eigenes Konzert" in client.get(reverse("productions:list")).content.decode()


def test_cannot_assign_member_of_other_org(org, owner, login, foreign, make_production, make_job):
    job = make_job(make_production(org))
    login(owner.user, org).post(
        reverse("productions:job_crew", args=[job.pk]),
        {"membership": foreign["member"].pk, "status": "confirmed"},
    )
    assert not CrewAssignment.objects.filter(job=job).exists()


STUDENT_FORBIDDEN = [
    ("get", "productions:create", None),
    ("get", "productions:edit", "production"),
    ("post", "productions:status", "production"),
    ("post", "productions:copy", "production"),
    ("post", "productions:delete", "production"),
    ("get", "productions:job_create", "production"),
    ("get", "productions:job_crew", "job"),
    ("post", "productions:crew_remove", "assignment"),
    ("get", "productions:trash", None),
    ("get", "productions:categories", None),
    ("get", "productions:statuses", None),
]


@pytest.fixture
def own(org, make_member, make_production, make_job, make_assignment):
    production = make_production(org)
    job = make_job(production)
    assignment = make_assignment(job, make_member(org, Role.STUDENT))
    return {"production": production, "job": job, "assignment": assignment}


@pytest.mark.parametrize(("method", "url_name", "target"), STUDENT_FORBIDDEN)
def test_students_cannot_plan(student_client, own, method, url_name, target):
    args = [own[target].pk] if target else []
    response = getattr(student_client, method)(reverse(url_name, args=args))
    assert response.status_code == 403


def test_students_see_no_edit_buttons(student_client, own):
    content = student_client.get(
        reverse("productions:detail", args=[own["production"].pk])
    ).content.decode()
    assert "Bearbeiten" not in content
    assert "+ Job" not in content
    assert ">Crew<" not in content


@pytest.mark.parametrize("role", [Role.OWNER, Role.ADMIN, Role.TEACHER])
def test_planners_can_open_forms(org, make_member, login, own, role):
    client = login(make_member(org, role).user, org)
    assert client.get(reverse("productions:create")).status_code == 200
    assert client.get(reverse("productions:job_crew", args=[own["job"].pk])).status_code == 200


def test_categories_for_owner_and_admin_only(org, make_member, login):
    for role, expected in [(Role.OWNER, 200), (Role.ADMIN, 200), (Role.TEACHER, 403)]:
        client = login(make_member(org, role).user, org)
        assert client.get(reverse("productions:categories")).status_code == expected


def test_statuses_for_owner_only(org, make_member, login):
    for role, expected in [(Role.OWNER, 200), (Role.ADMIN, 403), (Role.TEACHER, 403)]:
        client = login(make_member(org, role).user, org)
        assert client.get(reverse("productions:statuses")).status_code == expected


def test_manage_categories(org, owner, login, make_production):
    client = login(owner.user, org)
    client.post(reverse("productions:categories"), {"name": "Sport", "color": "teal"})
    sport = Category.objects.for_org(org).get(name="Sport")
    assert sport.position == 4

    client.post(reverse("productions:category_move", args=[sport.pk]), {"richtung": "-1"})
    names = list(Category.objects.for_org(org).values_list("name", flat=True))
    assert names.index("Sport") == 3

    production = make_production(org, category=sport)
    client.post(reverse("productions:category_delete", args=[sport.pk]))
    production.refresh_from_db()
    assert production.category is None


def test_manage_statuses(org, owner, login, make_production):
    client = login(owner.user, org)
    client.post(reverse("productions:statuses"), {"name": "Abgesagt", "color": "red"})
    cancelled = ProductionStatus.objects.for_org(org).get(name="Abgesagt")
    production = make_production(org, status=cancelled)

    client.post(reverse("productions:status_delete", args=[cancelled.pk]))
    production.refresh_from_db()
    assert production.status.is_planning

    planning = ProductionStatus.planning_for(org)
    client.post(reverse("productions:status_delete", args=[planning.pk]))
    assert ProductionStatus.objects.filter(pk=planning.pk).exists()

    client.post(
        reverse("productions:status_edit", args=[planning.pk]),
        {"name": "Planung läuft", "color": "orange"},
    )
    planning.refresh_from_db()
    assert planning.name == "Planung läuft" and planning.is_planning


def test_export_and_audit_include_productions(org, other_org, concert, make_production):
    import io
    import json
    import zipfile

    from apps.audit.models import AuditEntry
    from apps.organizations.export import export_organization

    make_production(other_org, "Fremdes Konzert")
    concert.soft_delete()
    archive = zipfile.ZipFile(io.BytesIO(export_organization(org)))
    productions = json.loads(archive.read("productions_production.json"))

    assert [p["name"] for p in productions] == ["Schulkonzert"]  # inkl. gelöschter
    assert AuditEntry.objects.filter(object_type="Produktion", organization=org).exists()
