# ADR 0001: Monorepo-Struktur

- **Status:** angenommen
- **Datum:** 2026-10-16

## Kontext

Code, Deployment, Dokumentation und Organisation sollen gemeinsam versioniert werden (Feature-Liste, Abschnitt 14).

## Entscheidung

Ein Git-Repository `technik-ag-planer` mit der Struktur aus Abschnitt 14: `app/` (Django), `deploy/` (Docker, Caddy, Backups), `docs/`, `scripts/` und `.github/`.

CI-Workflows (`ci.yml`, `release.yml`), `Makefile` und der Inhalt von `app/` und `deploy/` entstehen mit Meilenstein 1, sobald es Code zum Testen gibt.

## Folgen

- Änderungen an Code und Doku landen im selben Pull Request.
- Abweichungen von der Struktur werden als weiteres ADR festgehalten.
