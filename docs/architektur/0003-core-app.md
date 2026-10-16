# ADR 0003: App `core` für Grundlayout

- **Status:** angenommen
- **Datum:** 2026-10-16

## Kontext

Abschnitt 14 listet die Fach-Apps (`accounts`, `organizations`, `productions` …), aber keinen Ort für das, was alle gemeinsam nutzen: Grundlayout, Navigation, Health-Check.

## Entscheidung

Zusätzliche App `app/apps/core/` mit:

- Navigation (`navigation.py`) – Bereiche, Reihenfolge der Seitenleiste und der Handy-Leiste, „+ Neu“-Menü
- Context-Processor für die Navigation
- Platzhalterseiten für Bereiche, deren Meilenstein noch aussteht
- Health-Check `/healthz/` (prüft die Datenbank) für Docker und Caddy
- Test-Task `ping` für den Worker

Die Fach-Apps entstehen erst in ihrem jeweiligen Meilenstein; leere Apps werden nicht vorab angelegt. Sobald ein Bereich echt umgesetzt ist, ersetzt die Fach-App die Platzhalterseite und den Eintrag in `apps/core/urls.py`.

## Folgen

- `core` enthält keine Fachlogik und keine Modelle.
- Allgemeine Template-Bausteine liegen in `app/templates/includes/` (Icons, Bottom-Sheet).
