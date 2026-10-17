# CLAUDE.md – Projektregeln

Spezifikation: `docs/feature-liste.md` (nicht hier kopieren). Ablauf und Meilensteine: Abschnitt 15, Umsetzungsstand und Entscheidungen: Abschnitt 16 (nach jedem Meilenstein fortschreiben).

**Aktueller Meilenstein: 9 – Team-Funktionen.**

## Regeln

- **Stack:** Django, PostgreSQL, Redis, Celery, Docker, Caddy. Projektstruktur laut Abschnitt 14; Abweichungen begründet als ADR in `docs/architektur/` und in Abschnitt 16 der Feature-Liste.
- **Sprache:** Oberfläche, Texte und Doku komplett auf Deutsch.
- **Farben:** nur über Design-Tokens aus `app/static/css/tokens.css` – keine Farbwerte in Templates, CSS-Komponenten oder JS (ein Test prüft das). Farbige Daten speichern einen Palette-Schlüssel (`apps/productions/palette.py`, CSS-Klasse `color-<schlüssel>`).
- **Mandantentrennung:** AG-Daten erben von `OrganizationScopedModel`; jede Abfrage über `Model.objects.for_org(request.organization)`, einzelne Objekte mit `get_object_or_404(...for_org(...), pk=...)`. Jede View prüft das Recht laut Rechte-Tabelle (`@permission_required_in_org(Perm.X)`, `apps/organizations/permissions.py`).
- **Neue AG-Daten** in `apps.py` bei `apps.audit.registry.register(...)` und `apps.organizations.export.register(...)` anmelden.
- **Geheimnisse:** nie im Code, nur in `.env` (Vorlage: `.env.example`).
- **Tests:** Jede neue Funktion bekommt Tests, jede neue View auch Tests auf Mandantentrennung (fremde IDs → 404) und Rechte je Rolle. `make test` und `make lint` müssen grün sein.
- **Arbeitsweise:** Branch je Meilenstein, Plan zur Freigabe, Pull Request mit grüner CI, Squash-Merge in `main` (geschützt).

## Befehle

- `make dev` – Entwicklungsumgebung (App :8000, Mailpit :8025); `make migrate`, `make makemigrations`
- `make test` / `make lint` / `make format` – laufen im Dev-Container gegen PostgreSQL
- `make beispieldaten` (Logins `owner`, `admin`, `lehrer`, `schueler`, `ben`, `sued` – Passwort jeweils wie der Name), `make reset-db`, `make superuser`
- Abhängigkeiten: `uv add …` in `app/`, danach `make build`

## Bausteine

- **Layout:** `app/templates/base.html`; Bottom-Sheet über `includes/sheet_start.html` / `sheet_end.html`
- **Formulare:** Template beginnt mit `{% extends layout %}`; Links mit `data-sheet-url` öffnen es im Bottom-Sheet. `<form data-draft="…">` speichert Entwürfe im Browser. Felder über `includes/field.html` bzw. `includes/form_fields.html`.
- **Zeitfelder:** `PeriodTimesMixin` (`apps/scheduling/forms.py`) + `includes/time_or_period.html` für Eingabe als Uhrzeit oder Schulstunde
- **Konflikte:** `apps.scheduling.services.find_conflicts(membership, start, end)`
- **Systemmeldungen im Board:** `apps.board.services.post_system(org, text, link_production=…, key=…)`
- **Material-Konflikte:** `apps.inventory.services.check(material, production, menge)` bzw. `production_shortages(production)`
- **Produktion speichern:** `apps.productions.services.save_production(org, user, form, formset)`; Felder als Include `productions/includes/production_fields.html`
- **PDFs:** View mit `apps.documents.views._document(...)` (Vorschau + PDF aus einem Template unter `templates/documents/`); Farben nur über die `--print-…`-Tokens
- **Kalendereinträge:** `apps.scheduling.calendar.calendar_entries(org, start, end, membership=None)`

## Apps (`app/apps/`)

| App | Inhalt | ADR |
| --- | --- | --- |
| `core` | Navigation, Platzhalterseiten, Health-Check | 0003 |
| `accounts` | Konten, Login, 2FA, Passwort, Profil | 0004 |
| `organizations` | AGs, Rollen und Rechte, Einladungen, Einstellungen, Datenexport, `beispieldaten` | 0004 |
| `audit` | Änderungsprotokoll (7 Tage) | 0004 |
| `productions` | Produktionen (weich gelöscht: `objects` / `all_objects`), Jobs, Crew, To-dos, Kategorien, Status, Dashboard | 0005 |
| `scheduling` | Kalender, Termine und Serien, „Nicht verfügbar“, Stundenraster, ICS | 0006 |
| `board` | Board, Produktions-Chats, Systemmeldungen (Signale), Lesestand | 0007 |
| `inquiries` | Technik-Anfragen: öffentlicher Link, Formular, Spam-Schutz, geteilte Ansicht Anfrage/Produktion | 0009 |
| `inventory` | Material, Material-Kategorien, Defekte, Materialsätze, Planung je Produktion (Spitzenbedarf), Packliste | 0008 |
| `documents` | PDFs mit WeasyPrint: Call Sheets, Freistellungsliste, Packliste; Vorschau mit Herunterladen, Teilen, Drucken | 0010 |

Weitere Fach-Apps (Abschnitt 14) entstehen erst in ihrem Meilenstein.

## Tests

- Allgemeine Fixtures (`org`, `other_org`, `owner`, `make_member`, `login`, `member_client`): `app/conftest.py`
- Produktions-Fixtures (`make_production`, `make_job`, `make_assignment`, `concert`, `planner_client`, `student_client`): `app/tests/fixtures_productions.py`
- Material-Fixtures (`make_material`, `make_kit`, `mics`): `app/apps/inventory/tests/conftest.py`
