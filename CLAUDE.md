# CLAUDE.md – Projektregeln

Spezifikation: `docs/feature-liste.md` (nicht hier kopieren). Aktueller Meilenstein: **1 – Grundgerüst** (siehe Abschnitt 15 der Feature-Liste).

## Regeln

- **Stack:** Django, PostgreSQL, Redis, Docker, Caddy. Projektstruktur laut Abschnitt 14 der Feature-Liste; Abweichungen begründet als ADR in `docs/architektur/`.
- **Sprache:** Oberfläche komplett auf Deutsch.
- **Farben:** ausschließlich über die Design-Tokens (CSS-Variablen) aus Abschnitt 1 – keine Farbwerte direkt in Templates oder CSS-Komponenten.
- **Mandantentrennung:** Jede Abfrage wird nach Organisation gefiltert; jede View prüft Rolle und Recht laut Rechte-Tabelle (Abschnitt 2).
- **Geheimnisse:** nie im Code, nur in `.env` (Vorlage: `.env.example`).
- **Tests:** Jede neue Funktion bekommt Tests; `make test` und `make lint` müssen grün sein.
- **Arbeitsweise:** `main` ist immer lauffähig; Änderungen über Branch und Pull Request mit grüner CI.
