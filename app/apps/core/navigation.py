"""Bereiche der App (Feature-Liste, Abschnitt 1) – Grundlage für Navigation und Platzhalter."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    key: str
    label: str
    icon: str
    url_name: str
    milestone: int
    mobile_label: str = ""

    @property
    def short_label(self):
        return self.mobile_label or self.label


DASHBOARD = Section("dashboard", "Dashboard", "home", "core:dashboard", 3, mobile_label="Home")
CALENDAR = Section("calendar", "Kalender", "calendar", "core:calendar", 4)
PRODUCTIONS = Section("productions", "Produktionen", "clapper", "core:productions", 3)
INVENTORY = Section("inventory", "Material", "box", "core:inventory", 6)
BOARD = Section("board", "Board", "chat", "core:board", 5)
SETTINGS = Section("settings", "Einstellungen", "gear", "core:settings", 12)

# Reihenfolge der Seitenleiste
SIDEBAR = [DASHBOARD, CALENDAR, PRODUCTIONS, INVENTORY, BOARD, SETTINGS]
# Handy-Leiste: links und rechts vom zentralen „+“, „Mehr“ folgt danach
MOBILE_LEFT = [DASHBOARD, CALENDAR]
MOBILE_RIGHT = [PRODUCTIONS]
MOBILE_MORE = [INVENTORY, BOARD]

# Einträge im „+ Neu“-Menü (Abschnitt 4)
NEW_ITEMS = [
    {"label": "Termin", "hint": "Einfacher Termin, z. B. AG-Treffen", "icon": "calendar"},
    {"label": "Produktion", "hint": "Veranstaltung mit Jobs und Crew", "icon": "clapper"},
    {
        "label": "Nicht verfügbar",
        "hint": "Tage oder Zeiträume, an denen du nicht kannst",
        "icon": "slash",
    },
]

BY_KEY = {section.key: section for section in SIDEBAR}
