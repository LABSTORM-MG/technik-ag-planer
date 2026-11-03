"""Inventory changes; lock order: production, material, unit."""

import base64
import re
from dataclasses import dataclass, field
from io import BytesIO
from urllib.parse import unquote, urlsplit

import qrcode
import qrcode.constants
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.organizations.models import Organization
from apps.organizations.permissions import Perm
from apps.productions.models import CrewAssignment, Production

from .models import (
    DefectReport,
    Material,
    MaterialUnit,
    PlannedMaterial,
    ProductionTeardown,
    TeardownException,
    UnitIssue,
)

QR_MIN_VERSION = 2


def qr_png(code):
    """Nur der Code, keine Adresse: Das ergibt wenige große Felder, die Kameras sicher lesen.

    Mindestens Version 2: Erst sie hat das Ausrichtungsmuster, ohne das der Scanner
    schräg fotografierte Codes nicht liest (ADR 0024).
    """
    stream = BytesIO()
    qr = qrcode.QRCode(
        version=QR_MIN_VERSION,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=16,
        border=4,
    )
    qr.add_data(code)
    qr.make(fit=True)
    qr.make_image().save(stream, format="PNG")
    return stream.getvalue()


def qr_data_uri(code):
    return "data:image/png;base64," + base64.b64encode(qr_png(code)).decode("ascii")


def normalize_code(raw):
    code = raw.strip()
    if "/" in code:
        match = re.fullmatch(r"/geraet/([^/]+)/?", urlsplit(code).path)
        code = unquote(match[1]) if match else ""
    code = code.upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{1,99}", code):
        raise ValidationError("Ungültiger Inventarcode.")
    return code


def lock_mode(organization, *, qr=True):
    org = Organization.objects.select_for_update().get(pk=organization.pk)
    if org.inventory_qr_enabled != qr:
        raise ValidationError("Der Materialmodus wurde geändert. Bitte die Seite neu laden.")


def lock_production(production):
    lock_mode(production.organization)
    return Production.objects.select_for_update().get(
        pk=production.pk, organization=production.organization
    )


def lock_unit(unit):
    lock_mode(unit.organization)
    Material.objects.select_for_update().get(pk=unit.material_id)
    return MaterialUnit.objects.select_for_update().select_related("material").get(pk=unit.pk)


def check_open(production):
    if ProductionTeardown.objects.filter(
        production=production, completed_at__isnull=False
    ).exists():
        raise ValidationError("Der Abbau ist abgeschlossen; neue Ausgaben sind gesperrt.")


def check_available(unit):
    if unit.material.tracking != Material.Tracking.INDIVIDUAL:
        raise ValidationError("Dieses Material wird über Mengen statt Einzelgeräte verwaltet.")
    if unit.archived_at or unit.material.is_archived:
        raise ValidationError("Gerät oder Material ist archiviert.")
    if unit.defects.filter(status__in=DefectReport.OPEN).exists():
        raise ValidationError("Dieses Gerät ist defekt oder in Reparatur.")
    if unit.material.defects.filter(unit__isnull=True, status__in=DefectReport.OPEN).exists():
        raise ValidationError("Für diese Materialart liegt eine offene Defektmeldung vor.")
    if unit.issues.filter(returned_at__isnull=True).exists():
        raise ValidationError("Dieses Gerät ist noch ausgegeben oder vermisst.")


@dataclass
class ScanResult:
    """Ergebnis eines Scans: `action` sagt, was passiert ist, `note` warnt zusätzlich."""

    action: str
    material: Material
    kind: str = "issue"
    note: str = ""
    over_plan: bool = False

    @property
    def message(self):
        return f"{self.action} {self.note}." if self.note else self.action

    def detail(self, production):
        return self.note or material_progress(production, self.material, self.kind)


def reservation_conflict(material, production, quantity):
    """Wer das Material im Zeitraum reserviert hat, wenn `quantity` nicht mehr frei ist."""
    from .services import _plannings, check

    if check(material, production, quantity) is None:
        return []
    return _plannings(
        material, production.start_date, production.end_date, exclude_production=production
    )


def find_unit(organization, raw):
    return (
        MaterialUnit.objects.for_org(organization)
        .select_related("material")
        .filter(code__iexact=normalize_code(raw))
        .first()
    )


@transaction.atomic
def scan_unit(production, raw, mode, user):
    production = lock_production(production)
    unit = find_unit(production.organization, raw)
    if unit is None:
        raise ValidationError("Unbekannter Inventarcode.")
    unit = lock_unit(unit)
    current = unit.issues.filter(returned_at__isnull=True).first()
    here = current is not None and current.production_id == production.pk
    if mode == "return":
        if not here:
            raise ValidationError("Dieses Gerät ist hier nicht ausgegeben.")
        current.returned_at, current.returned_by = timezone.now(), user
        current.save(update_fields=["returned_at", "returned_by"])
        return ScanResult("Rückgabe gespeichert.", unit.material, "return")
    if mode == "undo_issue":
        # Versehentlicher Haken: Die Ausgabe hat nie stattgefunden, also auch keine Rückgabe
        if not here or TeardownException.objects.filter(issue=current).exists():
            raise ValidationError("Diese Ausgabe lässt sich nicht zurücknehmen.")
        current.delete()
        return ScanResult("Ausgabe zurückgenommen.", unit.material)
    if mode == "undo_return":
        check_open(production)
        check_available(unit)
        issue = (
            unit.issues.filter(production=production, returned_at__isnull=False)
            .order_by("-returned_at")
            .first()
        )
        if issue is None:
            raise ValidationError("Dieses Gerät ist hier nicht zurückgegeben.")
        issue.returned_at, issue.returned_by = None, None
        issue.save(update_fields=["returned_at", "returned_by"])
        return ScanResult("Rückgabe zurückgenommen.", unit.material, "return")
    if mode != "issue":
        raise ValidationError("Ungültiger Scanmodus.")
    check_open(production)
    check_available(unit)
    # Jedes freie Gerät geht, solange es in der Planung liegt. Darüber hinaus darf es nur raus,
    # wenn der Rest nicht für andere Produktionen im selben Zeitraum reserviert ist.
    plan = PlannedMaterial.objects.filter(production=production, material=unit.material).first()
    issued = (
        1
        + UnitIssue.objects.filter(production=production, unit__material=unit.material)
        .exclude(unit=unit)
        .values("unit")
        .distinct()
        .count()
    )
    note = ""
    if plan is None or issued > plan.quantity:
        others = reservation_conflict(unit.material, production, issued)
        if others:
            names = ", ".join(
                f"{p.production.name} ({p.production.start_date:%d.%m.})" for p in others
            )
            raise ValidationError(f"{unit.material.name}: nichts mehr frei, reserviert für {names}")
    if plan is None:
        plan = PlannedMaterial.objects.create(
            organization=production.organization,
            production=production,
            material=unit.material,
            quantity=1,
        )
        note = "War nicht eingeplant, jetzt 1 geplant"
    elif issued > plan.quantity:
        note = f"Über Planung: jetzt {issued} statt {plan.quantity} geplant"
        plan.quantity = issued
        plan.save(update_fields=["quantity"])
    UnitIssue.objects.create(
        organization=production.organization,
        unit=unit,
        production=production,
        production_name=production.name,
        issued_by=user,
    )
    return ScanResult("Ausgabe gespeichert.", unit.material, note=note, over_plan=bool(note))


@transaction.atomic
def report_defect(unit, description, user):
    unit = lock_unit(unit)
    description = description.strip()
    if not 5 <= len(description) <= 300:
        raise ValidationError("Beschreibung: 5–300 Zeichen erforderlich.")
    if unit.defects.filter(status__in=DefectReport.OPEN).exists():
        raise ValidationError("Für dieses Gerät ist bereits ein Defekt offen.")
    return DefectReport.objects.create(
        organization=unit.organization,
        material=unit.material,
        unit=unit,
        quantity=1,
        description=description,
        reported_by=user,
    )


@transaction.atomic
def resolve_defect(defect, status, resolution, user):
    lock_unit(defect.unit)
    if status not in DefectReport.Status.values:
        raise ValidationError("Ungültiger Defektstatus.")
    resolution = resolution.strip()
    if status == DefectReport.Status.REPAIRED and not 5 <= len(resolution) <= 2000:
        raise ValidationError("Reparaturvermerk: 5–2000 Zeichen erforderlich.")
    defect.status, defect.resolution = status, resolution
    defect.resolved_at = timezone.now() if status == DefectReport.Status.REPAIRED else None
    defect.resolved_by = user if defect.resolved_at else None
    defect.save(update_fields=["status", "resolution", "resolved_at", "resolved_by"])


@transaction.atomic
def archive_unit(unit, operation):
    unit = lock_unit(unit)
    if operation == "restore":
        unit.archived_at = None
        unit.save(update_fields=["archived_at"])
        return
    if unit.issues.filter(returned_at__isnull=True).exists():
        raise ValidationError("Gerät ist noch ausgegeben.")
    if operation == "delete":
        if unit.issues.exists() or unit.defects.exists():
            raise ValidationError("Geräte mit Historie können nur archiviert werden.")
        unit.delete()
    elif operation == "archive":
        unit.archived_at = timezone.now()
        unit.save(update_fields=["archived_at"])
    else:
        raise ValidationError("Ungültiger Vorgang.")


@transaction.atomic
def teardown(production, operation, user, *, issue_id=None, reason="", note=""):
    production = lock_production(production)
    state = ProductionTeardown.objects.filter(production=production).first()
    if operation == "start":
        if state is None:
            ProductionTeardown.objects.create(
                organization=production.organization, production=production, started_by=user
            )
        return
    if operation == "reopen":
        if state is None or not state.completed_at:
            raise ValidationError("Der Abbau ist nicht abgeschlossen.")
        state.completed_at, state.completed_by = None, None
        state.save(update_fields=["completed_at", "completed_by"])
        return
    if state is None or state.completed_at:
        raise ValidationError("Der Abbau ist nicht aktiv.")
    if operation == "exception":
        issue = UnitIssue.objects.filter(
            pk=issue_id, production=production, returned_at__isnull=True
        ).first()
        if (
            not issue
            or reason not in TeardownException.Reason.values
            or not 5 <= len(note.strip()) <= 2000
        ):
            raise ValidationError(
                "Offene Ausgabe, Grund und Bemerkung (5–2000 Zeichen) erforderlich."
            )
        if TeardownException.objects.filter(issue=issue).exists():
            raise ValidationError("Für diese Ausgabe ist bereits eine Ausnahme dokumentiert.")
        unit = lock_unit(issue.unit)
        if reason == "damaged" and not unit.defects.filter(status__in=DefectReport.OPEN).exists():
            report_defect(unit, ("Bei Abbau beschädigt: " + note.strip())[:300], user)
        TeardownException.objects.create(
            organization=production.organization,
            issue=issue,
            reason=reason,
            note=note.strip(),
            created_by=user,
        )
    elif operation == "complete":
        from django.db.models import F

        if PlannedMaterial.objects.filter(
            production=production,
            material__tracking="bulk",
            issued_quantity__gt=F("returned_quantity"),
        ).exists():
            raise ValidationError("Es sind noch Rückgaben von Mengenmaterial offen.")
        if UnitIssue.objects.filter(
            production=production, returned_at__isnull=True, exception__isnull=True
        ).exists():
            raise ValidationError("Es sind noch Rückgaben ungeklärt.")
        state.completed_at, state.completed_by = timezone.now(), user
        state.save(update_fields=["completed_at", "completed_by"])
    else:
        raise ValidationError("Ungültiger Abbauvorgang.")


@transaction.atomic
def move_quantity(planned, operation, quantity, user):
    from django.db.models import Sum

    from .models import QuantityMovement
    from .services import available

    production = lock_production(planned.production)
    material = Material.objects.select_for_update().get(pk=planned.material_id)
    planned = PlannedMaterial.objects.select_for_update().get(pk=planned.pk)
    if material.tracking == Material.Tracking.INDIVIDUAL or quantity < 1 or quantity > 10000:
        raise ValidationError("Ungültige Menge oder Material mit Einzelgeräten.")
    if operation == "issue":
        check_open(production)
        if material.is_archived or quantity > planned.quantity - planned.issued_quantity:
            raise ValidationError("Die Ausgabe überschreitet die noch geplante Menge.")
        stock = available(material)
        if material.tracking == Material.Tracking.BULK:
            outside = PlannedMaterial.objects.filter(material=material).aggregate(
                issued=Sum("issued_quantity"), returned=Sum("returned_quantity")
            )
            outstanding = (outside["issued"] or 0) - (outside["returned"] or 0)
            if stock is not None:
                stock -= outstanding
        if stock is not None and quantity > stock:
            raise ValidationError("Nicht genügend Material verfügbar.")
        planned.issued_quantity += quantity
        planned.issued_at = timezone.now()
        if material.tracking == Material.Tracking.CONSUMABLE and material.quantity is not None:
            material.quantity -= quantity
            material.save(update_fields=["quantity", "updated_at"])
    elif operation == "return":
        if material.tracking == Material.Tracking.CONSUMABLE:
            raise ValidationError("Verbrauchsmaterial benötigt keine Rückgabe.")
        if quantity > planned.outstanding_quantity:
            raise ValidationError("Die Rückgabe überschreitet die ausgegebene Menge.")
        planned.returned_quantity += quantity
        if planned.outstanding_quantity == 0:
            planned.returned_at = timezone.now()
    else:
        raise ValidationError("Ungültiger Vorgang.")
    planned.save(update_fields=["issued_quantity", "returned_quantity", "issued_at", "returned_at"])
    QuantityMovement.objects.create(
        organization=production.organization,
        planned=planned,
        operation=operation,
        quantity=quantity,
        user=user,
    )


def can_issue(membership, production):
    """Ausgeben darf, wer das Recht hat oder in dieser Produktion einen zugesagten Job hat."""
    if membership.has_perm(Perm.ISSUE_MATERIAL):
        return True
    return CrewAssignment.objects.filter(
        job__production=production,
        membership=membership,
        status=CrewAssignment.Status.CONFIRMED,
    ).exists()


@dataclass
class IssueRow:
    """Eine Zeile der Packliste: Stand beim Ausgeben und Zurücknehmen."""

    planned: PlannedMaterial
    issued: int
    returned: int
    devices_out: list = field(default_factory=list)
    devices: list = field(default_factory=list)

    @property
    def material(self):
        return self.planned.material

    @property
    def is_individual(self):
        return self.material.tracking == Material.Tracking.INDIVIDUAL

    @property
    def is_consumable(self):
        return self.material.tracking == Material.Tracking.CONSUMABLE

    @property
    def to_issue(self):
        return max(self.planned.quantity - self.issued, 0)

    @property
    def to_return(self):
        return 0 if self.is_consumable else self.issued - self.returned


def issue_rows(production):
    """Packliste einer Produktion, sortiert wie die Material-Kategorien."""
    issues = (
        UnitIssue.objects.filter(production=production)
        .select_related("unit")
        .order_by("unit__number")
    )
    by_material = {}
    for issue in issues:
        by_material.setdefault(issue.unit.material_id, []).append(issue)
    rows = []
    planned = (
        PlannedMaterial.objects.filter(production=production)
        .select_related("material", "material__category")
        .order_by("material__category__position", "material__category__name", "material__name")
    )
    for item in planned:
        if item.material.tracking == Material.Tracking.INDIVIDUAL:
            found = by_material.get(item.material_id, [])
            # Je Gerät einmal: Wer ein zweites Mal rausgeht, ist nicht zwei Geräte
            units = {i.unit_id for i in found}
            out = [i for i in found if not i.returned_at]
            rows.append(
                IssueRow(item, len(units), len(units) - len(out), [i.unit.number for i in out])
            )
        else:
            rows.append(IssueRow(item, item.issued_quantity, item.returned_quantity))
    return rows


def material_progress(production, material, kind):
    """Kurzer Stand für das Popup: Wie viel fehlt von diesem Material noch?"""
    row = next((r for r in issue_rows(production) if r.material.pk == material.pk), None)
    if row is None:
        return ""
    if kind == "return":
        if row.is_consumable:
            return ""
        if row.to_return:
            return f"Noch {row.to_return} von {row.issued} offen"
        return f"Alle {row.issued} zurück" if row.issued > 1 else "1 von 1 zurück"
    if row.to_issue:
        return f"Noch {row.to_issue} von {row.planned.quantity} offen"
    planned = row.planned.quantity
    return f"Alle {planned} ausgegeben" if planned > 1 else "1 von 1 ausgegeben"


def packing_totals(rows):
    """Gesamtstand für Packseite und Produktionsseite."""
    return {
        "issued_total": sum(r.issued for r in rows),
        "planned_total": sum(max(r.planned.quantity, r.issued) for r in rows),
        "returned_total": sum(r.returned for r in rows if not r.is_consumable),
        "returnable_total": sum(r.issued for r in rows if not r.is_consumable),
    }


@dataclass
class PackingDevice:
    number: int
    code: str
    out: bool = False
    returned: bool = False


def add_packing_devices(rows, production):
    """Abhakbare Geräte je Zeile: was hier draußen ist, und alles, was noch frei ist."""
    issues = UnitIssue.objects.for_org(production.organization).filter(returned_at__isnull=True)
    out_here = set(issues.filter(production=production).values_list("unit_id", flat=True))
    out_elsewhere = set(issues.exclude(production=production).values_list("unit_id", flat=True))
    returned_here = set(
        UnitIssue.objects.filter(production=production, returned_at__isnull=False).values_list(
            "unit_id", flat=True
        )
    )
    defective = set(
        DefectReport.objects.for_org(production.organization)
        .filter(unit__isnull=False, status__in=DefectReport.OPEN)
        .values_list("unit_id", flat=True)
    )
    by_material = {row.material.pk: row for row in rows if row.is_individual}
    units = (
        MaterialUnit.objects.for_org(production.organization)
        .filter(material_id__in=by_material)
        .order_by("number")
    )
    for unit in units:
        out = unit.pk in out_here
        if not out and (unit.archived_at or unit.pk in out_elsewhere or unit.pk in defective):
            continue
        by_material[unit.material_id].devices.append(
            PackingDevice(unit.number, unit.code, out, not out and unit.pk in returned_here)
        )


def has_outstanding_material(production):
    """Ist noch Material dieser Produktion draußen? Dann darf sie nicht endgültig verschwinden."""
    if UnitIssue.objects.filter(production=production, returned_at__isnull=True).exists():
        return True
    return (
        PlannedMaterial.objects.filter(
            production=production, issued_quantity__gt=F("returned_quantity")
        )
        .exclude(material__tracking=Material.Tracking.CONSUMABLE)
        .exists()
    )
