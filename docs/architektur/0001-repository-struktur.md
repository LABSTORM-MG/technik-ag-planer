# ADR 0001: Monorepo-Struktur

- **Status:** angenommen
- **Datum:** 2026-10-16

## Kontext

Code, Deployment, Dokumentation und Organisation sollen gemeinsam versioniert werden (Feature-Liste, Abschnitt 14).

## Entscheidung

Ein Git-Repository `technik-ag-planer` mit der Struktur aus Abschnitt 14: `app/` (Django), `deploy/` (Docker, Caddy, Backups), `docs/`, `scripts/` und `.github/`.

CI-Workflows (`ci.yml`, `release.yml`), `Makefile` und der Inhalt von `app/` und `deploy/` sind mit Meilenstein 1 entstanden. Ordner, die erst später Inhalt bekommen (z. B. `docs/handbuch/`), enthalten eine kurze `README.md` mit dem geplanten Inhalt.

Abweichung: Die Beispieldaten sind kein Skript in `scripts/`, sondern ein Django-Befehl (`make beispieldaten`, `apps/organizations/management/commands/beispieldaten.py`), weil sie die Modelle direkt nutzen.

## Folgen

- Änderungen an Code und Doku landen im selben Pull Request.
- Abweichungen von der Struktur werden als weiteres ADR festgehalten.
