from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import RestrictedError
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.inventory import services, unit_services
from apps.inventory.models import (
    DefectReport,
    Material,
    MaterialUnit,
    PlannedMaterial,
    ProductionTeardown,
    QuantityMovement,
    TeardownException,
    UnitIssue,
)
from apps.organizations import services as org_services
from apps.organizations.permissions import Role
from apps.productions.models import Production
from apps.productions.tasks import purge_deleted_productions


@pytest.fixture
def unit(org, mics):
    mics.tracking = "individual"
    mics.save(update_fields=["tracking"])
    org.inventory_qr_enabled = True
    org.save(update_fields=["inventory_qr_enabled"])
    return MaterialUnit.objects.create(organization=org, material=mics, code="MIC-01")


@pytest.fixture
def planned(org, concert, mics):
    return PlannedMaterial.objects.create(
        organization=org, production=concert, material=mics, quantity=2
    )


def test_scan_issue_and_return(org, concert, unit, planned, planner):
    unit_services.scan_unit(concert, "https://example.org/geraet/mic-01/", "issue", planner.user)
    with pytest.raises(ValidationError):
        unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    issue = UnitIssue.objects.get()
    assert issue.organization == org and issue.returned_at is None
    unit_services.scan_unit(concert, unit.code, "return", planner.user)
    issue.refresh_from_db()
    assert issue.returned_by == planner.user and issue.returned_at


def test_free_device_issued_without_planning(org, concert, unit, planner):
    message = unit_services.scan_unit(concert, unit.code, "issue", planner.user)

    assert "nicht eingeplant" in message
    plan = PlannedMaterial.objects.get(production=concert, material=unit.material)
    assert plan.quantity == 1


def test_more_devices_than_planned_raises_the_plan(org, concert, unit, planned, planner):
    PlannedMaterial.objects.filter(pk=planned.pk).update(quantity=1)
    second = MaterialUnit.objects.create(organization=org, material=unit.material, code="MIC-02")

    first = unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    over = unit_services.scan_unit(concert, second.code, "issue", planner.user)

    assert first == "Ausgabe gespeichert."
    assert "2 von 1 geplant, Planung auf 2 erhöht" in over
    planned.refresh_from_db()
    assert planned.quantity == 2


def test_device_out_for_other_production_cannot_be_issued(
    org, concert, unit, planned, planner, make_production
):
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)

    with pytest.raises(ValidationError, match="noch ausgegeben"):
        unit_services.scan_unit(make_production(org), unit.code, "issue", planner.user)


def test_unit_defect_counts_once_and_only_blocks_affected_device(
    org, concert, unit, planned, planner
):
    second = MaterialUnit.objects.create(organization=org, material=unit.material, code="MIC-02")
    defect = unit_services.report_defect(unit, "Kapsel ist beschädigt", planner.user)
    assert services.defective_count(unit.material) == 1
    with pytest.raises(ValidationError, match="defekt"):
        unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    unit_services.scan_unit(concert, second.code, "issue", planner.user)
    with pytest.raises(ValidationError):
        unit_services.resolve_defect(defect, "repaired", "", planner.user)
    unit_services.resolve_defect(defect, "repaired", "Kapsel ausgetauscht", planner.user)
    assert services.defective_count(unit.material) == 0
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)


def test_teardown_missing_device_stays_blocked(concert, unit, planned, planner):
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    unit_services.teardown(concert, "start", planner.user)
    with pytest.raises(ValidationError, match="ungeklärt"):
        unit_services.teardown(concert, "complete", planner.user)
    unit_services.teardown(
        concert,
        "exception",
        planner.user,
        issue_id=UnitIssue.objects.get().pk,
        reason="missing",
        note="Beim Abbau nicht gefunden",
    )
    unit_services.teardown(concert, "complete", planner.user)
    assert ProductionTeardown.objects.get().completed_at
    assert UnitIssue.objects.get().returned_at is None
    with pytest.raises(ValidationError):
        unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    unit_services.scan_unit(concert, unit.code, "return", planner.user)
    assert UnitIssue.objects.get().returned_at
    assert TeardownException.objects.count() == 1


def test_damaged_exception_creates_real_defect(concert, unit, planned, planner):
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    unit_services.teardown(concert, "start", planner.user)
    unit_services.teardown(
        concert,
        "exception",
        planner.user,
        issue_id=UnitIssue.objects.get().pk,
        reason="damaged",
        note="Gehäuse beim Abbau gebrochen",
    )
    assert DefectReport.objects.get().unit == unit
    with pytest.raises(ValidationError):
        unit_services.teardown(
            concert,
            "exception",
            planner.user,
            issue_id=UnitIssue.objects.get().pk,
            reason="other",
            note="Noch eine Ausnahme",
        )


def test_archive_and_delete_history(concert, unit, planned, planner):
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    with pytest.raises(ValidationError):
        unit_services.archive_unit(unit, "archive")
    unit_services.scan_unit(concert, unit.code, "return", planner.user)
    with pytest.raises(ValidationError):
        unit_services.archive_unit(unit, "delete")
    unit_services.archive_unit(unit, "archive")
    unit.refresh_from_db()
    assert unit.archived_at
    unit_services.archive_unit(unit, "restore")
    unit.refresh_from_db()
    assert unit.archived_at is None


def test_pages_and_permissions(concert, unit, planned, planner_client, member_client):
    for name, pk in [
        ("units", unit.material_id),
        ("scan", concert.pk),
        ("teardown_protocol", concert.pk),
    ]:
        assert planner_client.get(reverse(f"inventory:{name}", args=[pk])).status_code == 200
    assert (
        planner_client.get(reverse("inventory:unit_qr", args=[unit.pk]))["Content-Type"]
        == "image/png"
    )
    assert (
        member_client.post(
            reverse("inventory:unit_action", args=[unit.pk]), {"operation": "archive"}
        ).status_code
        == 403
    )
    response = planner_client.post(
        reverse("inventory:scan", args=[concert.pk]),
        {"code": unit.code, "mode": "issue"},
        HTTP_ACCEPT="application/json",
    )
    assert response.json()["ok"] is True


def test_scan_reports_material_name_for_popup(unit, concert, planned, planner_client):
    url = reverse("inventory:scan", args=[concert.pk])
    data = {"code": unit.code.lower(), "mode": "issue"}

    result = planner_client.post(url, data, HTTP_ACCEPT="application/json").json()
    assert result["name"] == unit.material.name

    again = planner_client.post(url, data, HTTP_ACCEPT="application/json").json()
    assert again["ok"] is False
    assert "name" not in again


def test_unknown_code_reports_no_name(concert, unit, planner_client):
    result = planner_client.post(
        reverse("inventory:scan", args=[concert.pk]),
        {"code": "GIBT-ES-NICHT", "mode": "issue"},
        HTTP_ACCEPT="application/json",
    ).json()
    assert result["ok"] is False
    assert "name" not in result


def test_scan_page_opens_camera_in_own_view(concert, unit, planned, planner_client):
    page = planner_client.get(reverse("inventory:scan", args=[concert.pk])).content.decode()
    assert 'id="scan-overlay"' in page
    assert 'id="scan-toast"' in page
    assert 'name="camera-mode" value="issue">' in page
    assert 'name="camera-mode" value="return">' in page


def test_camera_switch_blocks_issue_after_teardown(concert, unit, planned, planner_client, planner):
    ProductionTeardown.objects.create(
        organization=concert.organization,
        production=concert,
        started_by=planner.user,
        completed_at=timezone.now(),
    )
    page = planner_client.get(reverse("inventory:scan", args=[concert.pk])).content.decode()
    assert 'name="camera-mode" value="issue" disabled>' in page


def test_foreign_ag_rejected(other_org, unit, concert, planned, planner_client, make_material):
    foreign = MaterialUnit.objects.create(
        organization=other_org, material=make_material(other_org), code="FOREIGN-01"
    )
    assert planner_client.get(reverse("inventory:unit_qr", args=[foreign.pk])).status_code == 404
    assert (
        planner_client.post(
            reverse("inventory:scan", args=[concert.pk]),
            {"code": foreign.code, "mode": "issue"},
            HTTP_ACCEPT="application/json",
        ).json()["ok"]
        is False
    )


def test_custom_code_grows_stock(unit, planner_client):
    unit.material.quantity = 1
    unit.material.save()
    planner_client.post(
        reverse("inventory:unit_create", args=[unit.material_id]), {"code": "MIC-02"}
    )
    assert MaterialUnit.objects.count() == 2
    unit.material.refresh_from_db()
    assert unit.material.quantity == 2
    assert (
        planner_client.post(
            reverse("inventory:unit_create", args=[unit.material_id]), {"code": "bad/code"}
        ).status_code
        == 302
    )


def test_legacy_generated_lowercase_code(concert, unit, planned, planner):
    unit.code = "TAG-abcdef01234"
    unit.save()
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    assert UnitIssue.objects.get().unit == unit


def test_return_wrong_production(org, concert, unit, planned, planner, make_production):
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    other = make_production(org)
    with pytest.raises(ValidationError):
        unit_services.scan_unit(other, unit.code, "return", planner.user)
    assert UnitIssue.objects.get().returned_at is None


def test_label_menu_lists_devices_and_preselects_material(org, planner_client, unit, make_material):
    other = make_material(org, "Beamer", tracking="individual")
    second = MaterialUnit.objects.create(organization=org, material=other, code="BEAM-1")
    url = reverse("inventory:labels")

    units = {u.pk: u.preselected for u in planner_client.get(url).context["units"]}
    assert units == {unit.pk: True, second.pk: True}

    response = planner_client.get(url, {"material": other.pk})
    assert {u.pk: u.preselected for u in response.context["units"]} == {
        unit.pk: False,
        second.pk: True,
    }


def test_labels_pdf_uses_selection_of_own_org_only(
    org, other_org, planner_client, unit, make_material, monkeypatch
):
    foreign = MaterialUnit.objects.create(
        organization=other_org, material=make_material(other_org, "Fremd"), code="FREMD-1"
    )
    captured = {}

    def fake_render(template, context, stylesheet):
        captured.update(context)
        return b"%PDF-1.7"

    monkeypatch.setattr("apps.inventory.unit_views.render_plain_pdf", fake_render)
    response = planner_client.get(reverse("inventory:labels_pdf"), {"ids": [unit.pk, foreign.pk]})

    assert response["Content-Type"] == "application/pdf"
    assert [label["name"] for row in captured["rows"] for label in row] == [unit.material.name]


def test_labels_pdf_real_output_without_codes_as_text(unit, planner_client):
    response = planner_client.get(reverse("inventory:labels_pdf"), {"ids": [unit.pk]})

    assert response.content.startswith(b"%PDF")
    html = render_to_string(
        "inventory/labels_pdf.html",
        {"rows": [[{"name": unit.material.name, "qr": "data:image/png;base64,AA"}]]},
    )
    assert unit.material.name in html and unit.code not in html


def test_labels_pdf_without_selection_returns_to_menu(planner_client, unit):
    response = planner_client.get(reverse("inventory:labels_pdf"))

    assert response.url == reverse("inventory:labels")


@pytest.mark.parametrize("name", ["inventory:labels", "inventory:labels_pdf"])
def test_labels_need_qr_mode(org, planner_client, name):
    org.inventory_qr_enabled = False
    org.save(update_fields=["inventory_qr_enabled"])

    assert planner_client.get(reverse(name)).url == reverse("inventory:list")


def test_private_loans_are_gone(org, mics, planner_client):
    org.inventory_qr_enabled = False
    org.save(update_fields=["inventory_qr_enabled"])

    content = planner_client.get(reverse("inventory:detail", args=[mics.pk])).content.decode()

    assert "Ausleihe" not in content
    assert "checkout" not in content


@pytest.mark.django_db(transaction=True)
def test_parallel_device_operations_are_serialized(
    org, concert, unit, planned, planner, make_production
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections, connection

    if connection.vendor != "postgresql":
        pytest.skip("Row-lock concurrency requires PostgreSQL")
    other = make_production(org)
    PlannedMaterial.objects.create(
        organization=org, production=other, material=unit.material, quantity=1
    )
    barrier = Barrier(2)

    def act(production):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                unit_services.scan_unit(production, unit.code, "issue", planner.user)
            except ValidationError:
                return False
            return True
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(act, [concert, other]))
    assert sorted(results) == [False, True]
    assert UnitIssue.objects.filter(returned_at__isnull=True).count() == 1


def test_modes_are_exclusive(org, concert, planned, planner_client):
    planned.material.tracking = "individual"
    planned.material.save(update_fields=["tracking"])
    settings_url = reverse("inventory:settings")
    detail_url = reverse("inventory:detail", args=[planned.material_id])
    pack_url = reverse("inventory:packing_list", args=[concert.pk])
    units_url = reverse("inventory:units", args=[planned.material_id])
    classic = planner_client.get(detail_url).content.decode()
    assert "Einzelgeräte verwalten" not in classic
    assert planner_client.get(units_url).status_code == 302
    assert "pack__check" in planner_client.get(pack_url).content.decode()
    planner_client.post(settings_url, {"mode": "qr"})
    org.refresh_from_db()
    assert org.inventory_qr_enabled
    assert "Einzelgeräte verwalten" in planner_client.get(detail_url).content.decode()
    assert planner_client.get(units_url).status_code == 200
    assert planner_client.get(pack_url).url == reverse("inventory:scan", args=[concert.pk])
    planner_client.post(
        reverse("inventory:packing_toggle", args=[planned.pk]), {"spalte": "ausgabe"}
    )
    planned.refresh_from_db()
    assert planned.issued_at is None
    planner_client.post(settings_url, {"mode": "classic"})
    org.refresh_from_db()
    assert not org.inventory_qr_enabled
    assert "pack__check" in planner_client.get(pack_url).content.decode()


def test_switch_preserves_devices_and_blocks_outstanding_issues(
    org, unit, planned, concert, planner, planner_client
):
    url = reverse("inventory:settings")
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    planner_client.post(url, {"mode": "classic"})
    org.refresh_from_db()
    assert org.inventory_qr_enabled
    unit_services.scan_unit(concert, unit.code, "return", planner.user)
    planner_client.post(url, {"mode": "classic"})
    org.refresh_from_db()
    assert not org.inventory_qr_enabled
    assert MaterialUnit.objects.get().code == unit.code
    planner_client.post(url, {"mode": "qr"})
    assert (
        planner_client.get(reverse("inventory:units", args=[unit.material_id])).status_code == 200
    )


def test_settings_rights_and_ag_scope(org, other_org, planner_client, member_client):
    url = reverse("inventory:settings")
    assert member_client.post(url, {"mode": "qr"}).status_code == 403
    planner_client.post(url, {"mode": "qr"})
    other_org.refresh_from_db()
    assert not other_org.inventory_qr_enabled
    planner_client.post(url, {"mode": "invalid"})
    org.refresh_from_db()
    assert org.inventory_qr_enabled


def test_add_first_device_from_qr_interface(org, mics, planner_client):
    mics.tracking = "individual"
    mics.save(update_fields=["tracking"])
    planner_client.post(reverse("inventory:settings"), {"mode": "qr"})
    response = planner_client.post(reverse("inventory:unit_create", args=[mics.pk]), {"code": ""})
    unit = MaterialUnit.objects.get()
    assert response.url == reverse("inventory:units", args=[mics.pk])
    page = planner_client.get(response.url).content.decode()
    assert unit.code in page and "Einzelgerät hinzufügen" in page
    assert "QR-Etikett anzeigen" in page


def test_classic_mode_reuses_material_with_existing_devices(org, unit, planned, planner_client):
    planner_client.post(reverse("inventory:settings"), {"mode": "classic"})
    org.refresh_from_db()
    assert not org.inventory_qr_enabled
    assert (
        planner_client.get(reverse("inventory:detail", args=[unit.material_id])).status_code == 200
    )


def test_production_page_has_no_device_reservation(unit, planned, concert, planner_client):
    page = planner_client.get(reverse("productions:detail", args=[concert.pk])).content.decode()

    assert "Gerät reservieren" not in page
    scan_page = planner_client.get(reverse("inventory:scan", args=[concert.pk])).content.decode()
    assert "Kamera öffnen" in scan_page


def test_bulk_partial_return_and_teardown(org, concert, planned, planner, planner_client):
    org.inventory_qr_enabled = True
    org.save()
    unit_services.move_quantity(planned, "issue", 2, planner.user)
    planned.refresh_from_db()
    assert planned.outstanding_quantity == 2
    with pytest.raises(ValidationError):
        unit_services.move_quantity(planned, "return", 3, planner.user)
    unit_services.move_quantity(planned, "return", 1, planner.user)
    unit_services.teardown(concert, "start", planner.user)
    with pytest.raises(ValidationError, match="Mengenmaterial"):
        unit_services.teardown(concert, "complete", planner.user)
    planner_client.post(reverse("inventory:settings"), {"mode": "classic"})
    org.refresh_from_db()
    assert org.inventory_qr_enabled
    unit_services.move_quantity(planned, "return", 1, planner.user)
    unit_services.teardown(concert, "complete", planner.user)
    planned.refresh_from_db()
    assert planned.outstanding_quantity == 0 and planned.movements.count() == 3


def test_consumable_reduces_stock_without_return(org, concert, planned, planner):
    org.inventory_qr_enabled = True
    org.save()
    material = planned.material
    material.tracking = "consumable"
    material.save()
    before = material.quantity
    unit_services.move_quantity(planned, "issue", 2, planner.user)
    material.refresh_from_db()
    assert material.quantity == before - 2
    with pytest.raises(ValidationError):
        unit_services.move_quantity(planned, "return", 1, planner.user)
    unit_services.teardown(concert, "start", planner.user)
    unit_services.teardown(concert, "complete", planner.user)


def test_bulk_output_has_no_device_scanner(org, concert, planned, planner_client):
    org.inventory_qr_enabled = True
    org.save()
    content = planner_client.get(reverse("inventory:scan", args=[concert.pk])).content.decode()
    assert "Ausgeben" in content and 'id="scan-form"' not in content
    response = planner_client.post(
        reverse("inventory:quantity_move", args=[planned.pk]), {"quantity": 1, "operation": "issue"}
    )
    assert response.status_code == 302
    planned.refresh_from_db()
    assert planned.issued_quantity == 1
    content = planner_client.get(
        reverse("inventory:teardown_protocol", args=[concert.pk])
    ).content.decode()
    assert planned.material.name in content


def test_bulk_stock_cannot_be_double_issued(org, concert, planned, planner, make_production):
    org.inventory_qr_enabled = True
    org.save()
    material = planned.material
    material.quantity = 2
    material.save()
    other = make_production(org)
    second = PlannedMaterial.objects.create(
        organization=org, production=other, material=material, quantity=2
    )
    unit_services.move_quantity(planned, "issue", 2, planner.user)
    with pytest.raises(ValidationError, match="verfügbar"):
        unit_services.move_quantity(second, "issue", 1, planner.user)


def test_new_inventory_data_is_exported_and_audited(
    org, other_org, unit, concert, planned, planner, make_material
):
    import io
    import json
    import zipfile

    from django.apps import apps

    from apps.audit.context import acting_as
    from apps.audit.models import AuditEntry
    from apps.organizations.export import export_organization

    foreign = MaterialUnit.objects.create(
        organization=other_org, material=make_material(other_org), code="FOREIGN-EXPORT"
    )
    with acting_as(planner.user):
        unit_services.scan_unit(concert, unit.code, "issue", planner.user)
        unit_services.scan_unit(concert, unit.code, "return", planner.user)
    changes = AuditEntry.objects.filter(organization=org, actor=planner.user, action="update")
    assert any("returned_at" in entry.changes for entry in changes)
    with zipfile.ZipFile(io.BytesIO(export_organization(org))) as archive:
        data = {name: json.loads(archive.read(name)) for name in archive.namelist()}
    names = [
        "MaterialUnit",
        "UnitIssue",
        "ProductionTeardown",
        "TeardownException",
        "QuantityMovement",
    ]
    from apps.audit.registry import _registry

    for name in names:
        model = apps.get_model("inventory", name)
        assert model in _registry
        assert f"inventory_{model._meta.model_name}.json" in data
    assert data["ag.json"]["inventory_qr_enabled"] is True
    assert [row["code"] for row in data["inventory_materialunit.json"]] == [unit.code]
    assert foreign.code not in json.dumps(data)


# ---------- Übernahme: Löschpfade, Rechte, Inventarcodes, Kamera ----------


def _issue(org, unit, production, user, returned=True):
    return UnitIssue.objects.create(
        organization=org,
        unit=unit,
        production=production,
        production_name=production.name,
        issued_by=user,
        returned_at=timezone.now() if returned else None,
    )


def _expire(production):
    production.soft_delete()
    Production.all_objects.filter(pk=production.pk).update(
        deleted_at=timezone.now() - timedelta(days=8)
    )


def test_purge_removes_production_and_keeps_device_history(org, unit, planner, make_production):
    production = make_production(org, "Altes Konzert")
    issue = _issue(org, unit, production, planner.user)
    _expire(production)

    assert purge_deleted_productions() == 1

    assert not Production.all_objects.filter(pk=production.pk).exists()
    issue.refresh_from_db()
    assert issue.production is None
    assert issue.production_name == "Altes Konzert"


def test_purge_skips_production_with_open_device_but_continues(org, unit, planner, make_production):
    blocked = make_production(org, "Gerät noch draußen")
    _issue(org, unit, blocked, planner.user, returned=False)
    other = make_production(org, "Frei")
    _expire(blocked)
    _expire(other)

    assert purge_deleted_productions() == 1

    assert Production.all_objects.filter(pk=blocked.pk).exists()
    assert not Production.all_objects.filter(pk=other.pk).exists()


def test_purge_skips_production_with_outstanding_quantity(org, mics, make_production):
    production = make_production(org)
    PlannedMaterial.objects.create(
        organization=org, production=production, material=mics, quantity=2, issued_quantity=2
    )
    _expire(production)

    assert purge_deleted_productions() == 0
    assert Production.all_objects.filter(pk=production.pk).exists()


def test_purge_ignores_consumables_and_removes_movements(org, mics, planner, make_production):
    mics.tracking = Material.Tracking.CONSUMABLE
    mics.save(update_fields=["tracking"])
    production = make_production(org)
    planned_item = PlannedMaterial.objects.create(
        organization=org, production=production, material=mics, quantity=2, issued_quantity=2
    )
    QuantityMovement.objects.create(
        organization=org, planned=planned_item, operation="issue", quantity=2, user=planner.user
    )
    _expire(production)

    assert purge_deleted_productions() == 1
    assert not QuantityMovement.objects.exists()


def test_dissolving_org_with_device_history_works(org, unit, planner, make_production):
    issue = _issue(org, unit, make_production(org), planner.user, returned=False)
    TeardownException.objects.create(
        organization=org, issue=issue, reason="missing", note="weg", created_by=planner.user
    )

    org_services.dissolve(org, org.name)

    assert not MaterialUnit.objects.exists()
    assert not UnitIssue.objects.exists()


def test_material_with_devices_cannot_be_deleted_alone(unit):
    with pytest.raises(RestrictedError):
        unit.material.delete()


def test_same_code_allowed_in_two_orgs_not_twice_in_one(org, other_org, unit, make_material):
    foreign = make_material(other_org, "Fremd", tracking=Material.Tracking.INDIVIDUAL)
    MaterialUnit.objects.create(organization=other_org, material=foreign, code=unit.code)

    with pytest.raises(IntegrityError), transaction.atomic():
        MaterialUnit.objects.create(organization=org, material=unit.material, code=unit.code)


def test_foreign_code_gives_no_hint_when_creating(
    org, other_org, unit, planner_client, make_material
):
    foreign = make_material(other_org, "Fremd", tracking=Material.Tracking.INDIVIDUAL)
    MaterialUnit.objects.create(organization=other_org, material=foreign, code="GEHEIM-1")

    response = planner_client.post(
        reverse("inventory:unit_create", args=[unit.material_id]), {"code": "GEHEIM-1"}, follow=True
    )

    assert "bereits vergeben" not in response.content.decode()
    assert MaterialUnit.objects.for_org(org).filter(code="GEHEIM-1").exists()


@pytest.mark.parametrize(
    ("status", "allowed"), [("confirmed", True), ("requested", False), (None, False)]
)
def test_students_issue_only_with_confirmed_job_in_this_production(
    org, concert, unit, planned, planner, make_member, make_assignment, login, status, allowed
):
    student = make_member(org, Role.STUDENT)
    if status:
        make_assignment(concert.jobs.get(name="Show"), student, status=status)
    client = login(student.user, org)
    url = reverse("inventory:scan", args=[concert.pk])

    assert client.get(url).status_code == (200 if allowed else 403)
    response = client.post(url, {"code": unit.code, "mode": "issue"})

    assert response.status_code == (302 if allowed else 403)
    assert UnitIssue.objects.filter(unit=unit, production=concert).exists() is allowed
    if allowed:
        page = client.get(url).content.decode()
        assert "Abbaukontrolle" not in page
        assert UnitIssue.objects.get(unit=unit).production_name == concert.name


def test_job_in_other_production_does_not_count(
    org, concert, unit, make_production, make_job, make_member, make_assignment, login
):
    student = make_member(org, Role.STUDENT)
    other_job = make_job(make_production(org, "Andere"), "Aufbau")
    make_assignment(other_job, student, status="confirmed")

    url = reverse("inventory:scan", args=[concert.pk])

    assert login(student.user, org).get(url).status_code == 403


@pytest.mark.parametrize("role", [Role.ADMIN, Role.TEACHER])
def test_planning_roles_issue_without_job(org, concert, unit, make_member, login, role):
    client = login(make_member(org, role).user, org)

    assert client.get(reverse("inventory:scan", args=[concert.pk])).status_code == 200


def test_quantity_issue_needs_job_too(org, concert, mics, make_member, make_assignment, login):
    org.inventory_qr_enabled = True
    org.save(update_fields=["inventory_qr_enabled"])
    item = PlannedMaterial.objects.create(
        organization=org, production=concert, material=mics, quantity=2
    )
    student = make_member(org, Role.STUDENT)
    client = login(student.user, org)
    url = reverse("inventory:quantity_move", args=[item.pk])
    data = {"operation": "issue", "quantity": 1}

    assert client.post(url, data).status_code == 403

    make_assignment(concert.jobs.get(name="Aufbau"), student, status="confirmed")

    assert client.post(url, data).status_code == 302
    item.refresh_from_db()
    assert item.issued_quantity == 1


def test_members_cannot_control_teardown(concert, unit, member_client):
    assert (
        member_client.post(
            reverse("inventory:teardown", args=[concert.pk]), {"operation": "start"}
        ).status_code
        == 403
    )


@pytest.mark.parametrize("name", ["Caddyfile", "Caddyfile.proxy"])
def test_camera_allowed_for_own_site_only(name):
    candidates = [
        Path(settings.BASE_DIR).parent / "deploy" / "caddy" / name,
    ]
    path = next((c for c in candidates if c.exists()), None)
    if path is None:
        pytest.skip("deploy/ ist im Test-Container nicht eingebunden")
    assert "camera=(self)" in path.read_text()


# ---------- Material-Auswahl und kurze Codes ----------


def test_material_picker_shows_only_own_org_with_categories(
    org, other_org, planner_client, concert, make_material
):
    own = make_material(org, "Eigenes Mikro")
    make_material(other_org, "Fremdes Mikro")

    page = planner_client.get(reverse("inventory:plan", args=[concert.pk])).content.decode()

    assert "data-picker" in page
    assert own.name in page
    assert "Fremdes Mikro" not in page
    assert "<select" not in page.split('name="material"')[0].split("<form")[-1]


def test_material_picker_requires_a_choice_and_saves(org, planner_client, concert, make_material):
    material = make_material(org, "Eigenes Mikro")
    url = reverse("inventory:plan", args=[concert.pk])

    assert planner_client.post(url, {"quantity": 1}).status_code == 200
    assert not PlannedMaterial.objects.filter(production=concert).exists()

    assert planner_client.post(url, {"material": material.pk, "quantity": 2}).status_code == 302
    assert PlannedMaterial.objects.get(production=concert, material=material).quantity == 2


def test_generated_code_is_short(org, unit, planner_client):
    planner_client.post(reverse("inventory:unit_create", args=[unit.material_id]))

    generated = MaterialUnit.objects.for_org(org).exclude(pk=unit.pk).get()

    assert generated.code.startswith("TAG-")
    assert len(generated.code) == 14


def test_qr_contains_only_the_code_and_is_large(unit, planner_client):
    from io import BytesIO

    from PIL import Image

    response = planner_client.get(reverse("inventory:unit_qr", args=[unit.pk]))

    width, height = Image.open(BytesIO(response.content)).size
    assert width == height
    # 25 Module + 2 × 4 Rand bei 16 px: wenige große Felder statt einer Adresse
    assert width == (25 + 8) * 16


def _qr_modules(code):
    from io import BytesIO

    from PIL import Image

    return Image.open(BytesIO(unit_services.qr_png(code))).width // 16 - 8


def test_short_code_keeps_alignment_pattern_for_slanted_photos():
    # Version 1 (21 Module) hat kein Ausrichtungsmuster und ist schräg nicht lesbar
    assert _qr_modules("TAG-77567C79C0") == 25


def test_long_code_still_grows_beyond_minimum_version():
    assert _qr_modules("TAG-" + "A" * 60) > 25


def test_scanner_still_accepts_labels_with_address():
    assert unit_services.normalize_code("https://example.org/geraet/mic-01/") == "MIC-01"
    assert unit_services.normalize_code("TAG-ABC123") == "TAG-ABC123"


def test_kit_form_uses_material_picker(planner_client, org, make_material):
    make_material(org, "Eigenes Mikro")

    page = planner_client.get(reverse("inventory:kit_create")).content.decode()

    assert "data-picker-collapse" in page
    assert "Eigenes Mikro" in page


def test_devices_are_numbered_per_material_from_one(org, unit, make_material):
    second = MaterialUnit.objects.create(organization=org, material=unit.material, code="MIC-02")
    other = MaterialUnit.objects.create(
        organization=org, material=make_material(org, "Beamer"), code="BEAM-1"
    )

    assert (unit.number, second.number, other.number) == (1, 2, 1)


def test_device_number_stays_when_an_earlier_one_goes(org, unit):
    second = MaterialUnit.objects.create(organization=org, material=unit.material, code="MIC-02")
    third = MaterialUnit.objects.create(organization=org, material=unit.material, code="MIC-03")
    second.delete()
    third.refresh_from_db()

    assert third.number == 3
    next_device = MaterialUnit.objects.create(
        organization=org, material=unit.material, code="MIC-04"
    )
    assert next_device.number == 4


def test_labels_show_name_above_and_number_below(org, unit, planner_client, monkeypatch):
    captured = {}

    def fake_render(template, context, stylesheet):
        captured.update(context)
        return b"%PDF-1.7"

    monkeypatch.setattr("apps.inventory.unit_views.render_plain_pdf", fake_render)
    planner_client.get(reverse("inventory:labels_pdf"), {"ids": [unit.pk]})

    [[label]] = captured["rows"]
    assert (label["name"], label["number"]) == (unit.material.name, 1)
    html = render_to_string("inventory/labels_pdf.html", {"rows": captured["rows"]})
    assert html.index(label["name"]) < html.index("<img") < html.index("labels-print__number")


def test_number_migration_counts_existing_devices(org, make_material):
    from importlib import import_module

    from django.apps import apps as django_apps

    migration = import_module("apps.inventory.migrations.0009_materialunit_number")
    first = make_material(org, "A")
    second = make_material(org, "B")
    units = [
        MaterialUnit.objects.create(organization=org, material=m, code=c)
        for m, c in [(first, "A-1"), (second, "B-1"), (first, "A-2")]
    ]
    for offset, unit in enumerate(units, start=10):
        MaterialUnit.objects.filter(pk=unit.pk).update(number=offset)

    migration.number_devices(django_apps, None)

    for unit in units:
        unit.refresh_from_db()
    assert [u.number for u in units] == [1, 1, 2]


# ---------- Material packen ----------


def test_issue_rows_show_progress_for_devices_and_quantities(
    org, concert, unit, planned, mics, make_material, planner
):
    cable = make_material(org, "Kabel")
    cables = PlannedMaterial.objects.create(
        organization=org,
        production=concert,
        material=cable,
        quantity=4,
        issued_quantity=3,
        returned_quantity=1,
    )
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)

    rows = {r.material.name: r for r in unit_services.issue_rows(concert)}

    assert rows[unit.material.name].devices_out == [1]
    assert (rows["Kabel"].issued, rows["Kabel"].to_issue, rows["Kabel"].to_return) == (3, 1, 2)
    assert cables.pk == rows["Kabel"].planned.pk


def test_consumable_needs_no_return(org, concert, make_material):
    material = make_material(org, "Gaffa", tracking=Material.Tracking.CONSUMABLE)
    PlannedMaterial.objects.create(
        organization=org, production=concert, material=material, quantity=2, issued_quantity=2
    )

    [row] = unit_services.issue_rows(concert)

    assert row.is_consumable and row.to_return == 0


def test_quantity_move_answers_json_without_reload(org, concert, make_material, planner_client):
    org.inventory_qr_enabled = True
    org.save(update_fields=["inventory_qr_enabled"])
    item = PlannedMaterial.objects.create(
        organization=org, production=concert, material=make_material(org, "Kabel"), quantity=2
    )
    url = reverse("inventory:quantity_move", args=[item.pk])

    ok = planner_client.post(
        url, {"operation": "issue", "quantity": 2}, headers={"accept": "application/json"}
    ).json()
    bad = planner_client.post(
        url, {"operation": "issue", "quantity": 1}, headers={"accept": "application/json"}
    ).json()

    assert ok == {"ok": True, "message": "2 × Kabel ausgegeben."}
    assert bad["ok"] is False


def test_packing_page_shows_switch_list_and_prefilled_amount(
    org, concert, make_material, planner_client, unit
):
    PlannedMaterial.objects.create(
        organization=org, production=concert, material=make_material(org, "Kabel"), quantity=7
    )

    content = planner_client.get(reverse("inventory:scan", args=[concert.pk])).content.decode()

    assert "Material packen" in content
    assert 'name="mode" value="return"' in content
    assert "Kabel" in content and 'name="quantity" value="7"' in content
    assert "Materialverwaltung kurz erklärt" not in content


def test_packing_page_lists_free_devices_to_tick(
    org, other_org, concert, make_production, unit, planned, planner_client, planner
):
    out_here = MaterialUnit.objects.create(organization=org, material=unit.material, code="HIER-1")
    elsewhere = MaterialUnit.objects.create(organization=org, material=unit.material, code="WEG-1")
    broken = MaterialUnit.objects.create(organization=org, material=unit.material, code="KAPUTT-1")
    unit_services.scan_unit(concert, out_here.code, "issue", planner.user)
    unit_services.scan_unit(make_production(org), elsewhere.code, "issue", planner.user)
    unit_services.report_defect(broken, "Stecker abgebrochen", planner.user)

    rows = unit_services.issue_rows(concert)
    unit_services.add_packing_devices(rows, concert)

    devices = {d.code: d for r in rows for d in r.devices}
    assert set(devices) == {unit.code, "HIER-1"}
    assert devices["HIER-1"].out and not devices[unit.code].out


def test_ticking_device_issues_and_unticking_returns(concert, unit, planned, planner_client):
    url = reverse("inventory:scan", args=[concert.pk])

    page = planner_client.get(url).content.decode()
    assert f'name="code" value="{unit.code}"' in page

    assert planner_client.post(url, {"code": unit.code, "mode": "issue"}).status_code == 302
    assert unit.issues.filter(returned_at__isnull=True).exists()
    assert planner_client.post(url, {"code": unit.code, "mode": "return"}).status_code == 302
    assert not unit.issues.filter(returned_at__isnull=True).exists()


def test_quantity_tick_issues_whole_open_amount(org, concert, make_material, planner_client):
    org.inventory_qr_enabled = True
    org.save(update_fields=["inventory_qr_enabled"])
    item = PlannedMaterial.objects.create(
        organization=org, production=concert, material=make_material(org, "Kabel"), quantity=3
    )
    planner_client.post(
        reverse("inventory:quantity_move", args=[item.pk]), {"operation": "issue", "quantity": 3}
    )
    page = planner_client.get(reverse("inventory:scan", args=[concert.pk])).content.decode()
    item.refresh_from_db()
    assert item.issued_quantity == 3
    assert 'aria-pressed="true"' in page


def test_material_page_only_links_to_device_management(unit, planner_client):
    content = planner_client.get(
        reverse("inventory:detail", args=[unit.material_id])
    ).content.decode()

    assert reverse("inventory:units", args=[unit.material_id]) in content
    assert "Einzelgeräte verwalten" in content
    assert reverse("inventory:unit_create", args=[unit.material_id]) not in content
    assert "Einzelgerät hinzufügen" not in content
