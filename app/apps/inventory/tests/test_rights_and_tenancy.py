"""Rechte je Rolle und Mandantentrennung für alle Material-Views."""

import io
import json
import zipfile

import pytest
from django.urls import reverse

from apps.inventory import services
from apps.inventory.models import Kit, Material, MaterialCategory
from apps.organizations.permissions import Role


@pytest.fixture
def foreign(other_org, make_member, make_production, make_material, make_kit):
    """Daten der anderen AG."""
    owner = make_member(other_org, Role.OWNER)
    production = make_production(other_org, "Fremdes Konzert")
    material = make_material(other_org, "Fremdes Pult")
    return {
        "production": production,
        "material": material,
        "kit": make_kit(other_org, "Fremder Satz", items=[(material, 1)]),
        "defect": services.report_defect(material, 1, "kaputt", owner.user),
        "planned": services.plan(production, material, 1),
        "category": MaterialCategory.objects.for_org(other_org).first(),
    }


FOREIGN_URLS = [
    ("get", "inventory:detail", "material"),
    ("get", "inventory:edit", "material"),
    ("post", "inventory:archive", "material"),
    ("get", "inventory:defect_report", "material"),
    ("post", "inventory:defect_status", "defect"),
    ("get", "inventory:kit_edit", "kit"),
    ("post", "inventory:kit_copy", "kit"),
    ("post", "inventory:kit_delete", "kit"),
    ("get", "inventory:plan", "production"),
    ("get", "inventory:plan_kit", "production"),
    ("get", "inventory:packing_list", "production"),
    ("get", "inventory:planned_edit", "planned"),
    ("post", "inventory:planned_remove", "planned"),
    ("post", "inventory:packing_toggle", "planned"),
    ("get", "inventory:category_edit", "category"),
    ("post", "inventory:category_delete", "category"),
    ("post", "inventory:category_move", "category"),
]


@pytest.mark.parametrize(("method", "url_name", "target"), FOREIGN_URLS)
def test_foreign_objects_return_404(org, owner, login, foreign, method, url_name, target):
    client = login(owner.user, org)
    response = getattr(client, method)(reverse(url_name, args=[foreign[target].pk]))
    assert response.status_code == 404


def test_lists_show_only_own_org(org, owner, login, foreign, make_material):
    make_material(org, "Eigenes Pult")
    client = login(owner.user, org)
    for url in [
        reverse("inventory:list"),
        reverse("inventory:list") + "?filter=defekt",
        reverse("inventory:kits"),
    ]:
        content = client.get(url).content.decode()
        assert "Fremd" not in content
    assert "Eigenes Pult" in client.get(reverse("inventory:list")).content.decode()


def test_cannot_plan_foreign_material_or_kit(org, owner, login, foreign, make_production):
    production = make_production(org)
    client = login(owner.user, org)
    client.post(
        reverse("inventory:plan", args=[production.pk]),
        {"material": foreign["material"].pk, "quantity": "1"},
    )
    client.post(reverse("inventory:plan_kit", args=[production.pk]), {"kit": foreign["kit"].pk})
    assert not production.planned_material.exists()


def test_kit_form_rejects_foreign_material(org, owner, login, foreign):
    login(owner.user, org).post(
        reverse("inventory:kit_create"),
        {
            "name": "Satz",
            "description": "",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-material": foreign["material"].pk,
            "items-0-quantity": "1",
        },
    )
    assert not Kit.objects.for_org(org).exists()


def _member(org, owner, make_member, role):
    """Pro AG gibt es genau einen Owner – der kommt aus der Fixture."""
    return owner if role == Role.OWNER else make_member(org, role)


@pytest.fixture
def own(org, owner, make_production, make_material, make_kit):
    production = make_production(org)
    material = make_material(org)
    return {
        "production": production,
        "material": material,
        "kit": make_kit(org, items=[(material, 1)]),
        "defect": services.report_defect(material, 1, "kaputt", owner.user),
        "planned": services.plan(production, material, 1),
    }


# Schüler/innen: Material nicht anlegen/bearbeiten, keine Sätze, nicht planen
STUDENT_FORBIDDEN = [
    ("get", "inventory:create", None),
    ("get", "inventory:edit", "material"),
    ("post", "inventory:archive", "material"),
    ("post", "inventory:defect_status", "defect"),
    ("get", "inventory:kit_create", None),
    ("get", "inventory:kit_edit", "kit"),
    ("post", "inventory:kit_copy", "kit"),
    ("post", "inventory:kit_delete", "kit"),
    ("get", "inventory:plan", "production"),
    ("get", "inventory:plan_kit", "production"),
    ("get", "inventory:planned_edit", "planned"),
    ("post", "inventory:planned_remove", "planned"),
    ("get", "inventory:categories", None),
]


@pytest.mark.parametrize(("method", "url_name", "target"), STUDENT_FORBIDDEN)
def test_students_cannot_manage(student_client, own, method, url_name, target):
    args = [own[target].pk] if target else []
    response = getattr(student_client, method)(reverse(url_name, args=args))
    assert response.status_code == 403


ALL_MEMBERS_ALLOWED = [
    ("inventory:list", None),
    ("inventory:kits", None),
    ("inventory:detail", "material"),
    ("inventory:defect_report", "material"),
    ("inventory:packing_list", "production"),
]


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize(("url_name", "target"), ALL_MEMBERS_ALLOWED)
def test_every_role_sees_material_and_reports_defects(
    org, owner, make_member, login, own, role, url_name, target
):
    client = login(_member(org, owner, make_member, role).user, org)
    args = [own[target].pk] if target else []
    assert client.get(reverse(url_name, args=args)).status_code == 200


@pytest.mark.parametrize(
    ("role", "expected"),
    [(Role.OWNER, 200), (Role.ADMIN, 200), (Role.TEACHER, 200), (Role.STUDENT, 403)],
)
def test_manage_inventory_rights(org, owner, make_member, login, own, role, expected):
    client = login(_member(org, owner, make_member, role).user, org)
    assert client.get(reverse("inventory:create")).status_code == expected
    assert (
        client.get(reverse("inventory:plan", args=[own["production"].pk])).status_code == expected
    )


@pytest.mark.parametrize(
    ("role", "expected"),
    [(Role.OWNER, 200), (Role.ADMIN, 200), (Role.TEACHER, 403), (Role.STUDENT, 403)],
)
def test_kits_and_categories_for_owner_and_admin_only(
    org, owner, make_member, login, own, role, expected
):
    client = login(_member(org, owner, make_member, role).user, org)
    assert client.get(reverse("inventory:kit_create")).status_code == expected
    assert client.get(reverse("inventory:kit_edit", args=[own["kit"].pk])).status_code == expected
    assert client.get(reverse("inventory:categories")).status_code == expected


def test_buttons_follow_rights(org, make_member, login, own):
    url = reverse("inventory:detail", args=[own["material"].pk])
    student = login(make_member(org, Role.STUDENT).user, org).get(url).content.decode()
    assert "Defekt melden" in student
    assert "Bearbeiten" not in student and "Archivieren" not in student
    assert "Repariert" not in student

    teacher = login(make_member(org, Role.TEACHER).user, org)
    assert "Archivieren" in teacher.get(url).content.decode()
    assert "+ Satz" not in teacher.get(reverse("inventory:kits")).content.decode()


def test_export_and_audit_include_material(org, other_org, own, foreign):
    from apps.audit.models import AuditEntry
    from apps.organizations.export import export_organization

    archive = zipfile.ZipFile(io.BytesIO(export_organization(org)))
    materials = json.loads(archive.read("inventory_material.json"))
    assert [m["name"] for m in materials] == ["Funkmikrofon"]
    assert json.loads(archive.read("inventory_plannedmaterial.json"))
    assert AuditEntry.objects.filter(object_type="Material", organization=org).exists()
    assert Material.objects.for_org(org).count() == 1
