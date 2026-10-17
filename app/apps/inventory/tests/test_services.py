"""Bestand, Spitzenbedarf je Tag, Sätze und Kopieren."""

from apps.inventory import services
from apps.inventory.models import DefectReport, KitItem, MaterialCategory, PlannedMaterial
from apps.productions.services import copy_production


def test_new_org_gets_default_material_categories(make_org):
    org = make_org()
    names = list(MaterialCategory.objects.for_org(org).values_list("name", flat=True))
    assert names[:2] == ["Licht", "Audio"]
    assert "Sonstiges" in names


def test_available_subtracts_open_defects(owner, mics):
    defect = services.report_defect(mics, 2, "Kapsel knackt", owner.user)
    assert services.available(mics) == 4

    services.set_defect_status(defect, DefectReport.Status.IN_REPAIR)
    assert services.available(mics) == 4

    services.set_defect_status(defect, DefectReport.Status.REPAIRED)
    defect.refresh_from_db()
    assert services.available(mics) == 6
    assert defect.resolved_at is not None


def test_unlimited_material_never_conflicts(org, make_material, make_production):
    tape = make_material(org, "Gaffa", quantity=None)
    production = make_production(org)
    services.plan(production, tape, 500)
    assert services.available(tape) is None
    assert services.check(tape, production, 1000) is None
    assert services.production_shortages(production) == {}


def test_overlapping_productions_add_up(org, mics, make_production):
    a = make_production(org, "Konzert", days_ahead=3, length=2)
    b = make_production(org, "Probe", days_ahead=4)
    services.plan(a, mics, 4)

    shortage = services.check(mics, b, 3)
    assert shortage.needed == 7 and shortage.available == 6 and shortage.missing == 1
    assert services.check(mics, b, 2) is None


def test_consecutive_productions_do_not_add_up(org, mics, make_production):
    """Spitzenbedarf je Tag: A (Tag 3–4) und C (Tag 6–7) überlappen beide mit B (Tag 4–6),
    aber nie gleichzeitig miteinander."""
    a = make_production(org, "A", days_ahead=3, length=2)
    b = make_production(org, "B", days_ahead=4, length=3)
    c = make_production(org, "C", days_ahead=6, length=2)
    services.plan(a, mics, 3)
    services.plan(c, mics, 3)

    assert services.check(mics, b, 3) is None
    assert services.check(mics, b, 4).needed == 7


def test_deleted_productions_do_not_count(org, mics, make_production):
    a = make_production(org, "A")
    b = make_production(org, "B")
    services.plan(a, mics, 6)
    assert services.check(mics, b, 1)

    a.soft_delete()
    assert services.check(mics, b, 1) is None


def test_defects_cause_overbooking(org, owner, mics, make_production):
    production = make_production(org)
    services.plan(production, mics, 6)
    assert services.production_shortages(production) == {}

    services.report_defect(mics, 1, "kaputt", owner.user)
    shortage = services.production_shortages(production)[mics.pk]
    assert (shortage.needed, shortage.available) == (6, 5)


def test_plan_adds_to_existing_quantity(org, mics, make_production):
    production = make_production(org)
    services.plan(production, mics, 2)
    planned = services.plan(production, mics, 3)
    assert planned.quantity == 5
    assert PlannedMaterial.objects.filter(production=production).count() == 1


def test_apply_kit_copies_items_and_skips_archived(
    org, mics, make_material, make_kit, make_production
):
    desk = make_material(org, "Mischpult", quantity=1)
    old = make_material(org, "Altes Kabel", quantity=10)
    kit = make_kit(org, items=[(mics, 4), (desk, 1), (old, 2)])
    services.archive(old)
    production = make_production(org)
    services.plan(production, mics, 1)

    skipped = services.apply_kit(production, kit)

    assert skipped == [old]
    planned = {p.material: p for p in production.planned_material.all()}
    assert planned[mics].quantity == 5
    assert planned[desk].source_kit == kit
    assert old not in planned

    # Spätere Änderungen am Satz wirken nicht zurück
    KitItem.objects.filter(kit=kit, material=desk).update(quantity=3)
    kit.delete()
    planned[desk].refresh_from_db()
    assert planned[desk].quantity == 1 and planned[desk].source_kit is None


def test_kit_shortages(org, mics, make_kit, make_production):
    kit = make_kit(org, items=[(mics, 4)])
    production = make_production(org)
    services.plan(production, mics, 3)
    assert [s.material for s in services.kit_shortages(production, kit)] == [mics]


def test_copy_kit(org, mics, make_kit):
    kit = make_kit(org, items=[(mics, 4)])
    copy = services.copy_kit(kit)
    assert copy.name == "Große Audioanlage (Kopie)"
    assert [(i.material, i.quantity) for i in copy.items.all()] == [(mics, 4)]


def test_copy_production_copies_material_without_checks(org, mics, make_production):
    production = make_production(org)
    planned = services.plan(production, mics, 2)
    services.set_packed(planned, "issued_at", True)

    copy = copy_production(production)
    copied = copy.planned_material.get()
    assert copied.quantity == 2 and copied.material == mics
    assert copied.issued_at is None and copied.organization == org


def test_material_plannings_marks_overbooking(org, mics, make_production):
    a = make_production(org, "A")
    b = make_production(org, "B", days_ahead=10)
    services.plan(a, mics, 7)
    services.plan(b, mics, 2)

    plannings = {p.production.name: p.overbooked for p in services.material_plannings(mics)}
    assert plannings == {"A": True, "B": False}
