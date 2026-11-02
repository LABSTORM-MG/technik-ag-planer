"""Einzelauswahl sieht überall gleich aus: Schalter statt einfacher Radio-Punkte."""

from pathlib import Path

from django.conf import settings

from apps.notifications.forms import SettingsForm
from apps.scheduling.forms import EventEditScopeForm, SegmentedRadio

APP_DIR = Path(settings.BASE_DIR)
ALLOWED = {
    "segmented_option.html",
    "chip_option.html",
    "scan.html",  # eigener Schalter „Ausgabe | Rückgabe“ mit großen Flächen
    "settings.html",  # Materialverwaltung: Modus als Karten mit Erklärung
    "material_picker_option.html",  # Auswahl aus einer Liste, kein Umschalter
}


def test_templates_use_radios_only_inside_switches():
    for template in (APP_DIR / "templates").rglob("*.html"):
        content = template.read_text()
        if template.name in ALLOWED or 'type="radio"' not in content:
            continue
        assert "segmented--choice" in content, f"Einfache Radio-Punkte in {template}"


def test_forms_use_segmented_switch():
    assert isinstance(SettingsForm().fields["reminder_mode"].widget, SegmentedRadio)
    assert isinstance(EventEditScopeForm().fields["scope"].widget, SegmentedRadio)


def test_hidden_radios_do_not_inherit_full_width():
    """Sonst werden Seiten mit Chips oder Schaltern breiter als der Bildschirm."""
    css = (APP_DIR / "static" / "css" / "app.css").read_text()

    assert '.field input:not([type="checkbox"], [type="radio"])' in css
