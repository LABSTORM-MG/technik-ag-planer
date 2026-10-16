"""Gliederung der Einstellungen (Abschnitt 10). `url_name=None` = folgt in späterem Meilenstein."""

from dataclasses import dataclass

from .permissions import Perm


@dataclass(frozen=True)
class Entry:
    label: str
    subtitle: str
    url_name: str | None = None
    milestone: int | None = None
    owner_only: bool = False
    perm: Perm | None = None


GROUPS = [
    (
        "Team",
        [
            Entry(
                "Mitglieder",
                "Liste mit Anzahl; einladen und Rollen vergeben nur durch den Owner",
                "organizations:members",
            ),
            Entry(
                "Organisation verwalten",
                "Ownership übertragen, verlassen oder auflösen",
                "organizations:manage",
            ),
        ],
    ),
    (
        "Planung",
        [
            Entry(
                "Kategorien",
                "Produktions-Kategorien verwalten und sortieren",
                "productions:categories",
                perm=Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK,
            ),
            Entry(
                "Technik anfragen",
                "Öffentlichen Anfrage-Link verwalten",
                milestone=7,
                perm=Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK,
            ),
            Entry(
                "Kürzlich gelöscht",
                "Gelöschte Produktionen 7 Tage lang wiederherstellen",
                "productions:trash",
                perm=Perm.MANAGE_PRODUCTIONS,
            ),
            Entry(
                "Google-Konto",
                "Google-Konto der AG für Drive und Kalender verbinden",
                milestone=10,
                owner_only=True,
            ),
            Entry(
                "Stundenraster",
                "Unterrichtsstunden mit Beginn und Ende festlegen",
                milestone=4,
                owner_only=True,
            ),
            Entry(
                "Fähigkeiten",
                "Fähigkeiten zur Auswahl anlegen, sortieren, löschen",
                milestone=9,
                owner_only=True,
            ),
            Entry(
                "Status-Werte",
                "Status für Produktionen mit Name und Farbe",
                "productions:statuses",
                owner_only=True,
            ),
            Entry(
                "Schuljahreswechsel",
                "Alle Jahrgangsstufen um eins erhöhen, Q2 wird „Extern“",
                milestone=9,
                owner_only=True,
            ),
        ],
    ),
    (
        "Datenschutz",
        [
            Entry(
                "Zwei-Faktor für alle Mitglieder",
                "Pflicht ein/aus",
                "organizations:require_2fa",
                owner_only=True,
            ),
        ],
    ),
    (
        "Für mich",
        [
            Entry(
                "Benachrichtigungen", "Push-Mitteilungen aktivieren und einstellen", milestone=11
            ),
            Entry("Nicht verfügbar", "Tage oder Zeiträume, an denen du nicht kannst", milestone=4),
            Entry("Meine Fähigkeiten", "Eigene Fähigkeiten aus der Liste auswählen", milestone=9),
            Entry("Hilfe & FAQ", "Kurze Antworten auf häufige Fragen", milestone=12),
            Entry("Über die App", "Alle Funktionen auf einen Blick", milestone=12),
        ],
    ),
    (
        "Konto",
        [
            Entry(
                "Name und Jahrgangsstufe ändern", "Frei wählbarer Anzeigename", "accounts:profile"
            ),
            Entry("Passwort ändern", "Eigenes Passwort neu setzen", "accounts:password_change"),
            Entry(
                "Meine Zwei-Faktor-Anmeldung",
                "Status, Einrichtung per Authenticator-App",
                "accounts:two_factor",
            ),
            Entry("Konto löschen", "Eigenes Konto dauerhaft löschen", milestone=9),
        ],
    ),
]


def visible_groups(membership):
    result = []
    for title, entries in GROUPS:
        visible = [
            e
            for e in entries
            if (not e.owner_only or membership.is_owner)
            and (e.perm is None or membership.has_perm(e.perm))
        ]
        if visible:
            result.append((title, visible))
    return result
