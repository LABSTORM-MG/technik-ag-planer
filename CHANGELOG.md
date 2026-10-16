# Changelog

Alle wichtigen Änderungen an diesem Projekt. Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach [Semantic Versioning](https://semver.org/lang/de/).

## [Unveröffentlicht]

### Hinzugefügt

- Repository-Grundstruktur, Feature-Liste, Lizenz und Projektregeln
- Django-Projekt (Django 5.2, Python 3.13) mit Settings für Entwicklung, Tests und Betrieb
- Grundlayout: Seitenleiste (Tablet quer, Computer), Leiste unten (Handy, Tablet hochkant), Bottom-Sheets für „+ Neu“ und „Mehr“, Platzhalterseiten
- Design-Tokens als CSS-Variablen; Test verhindert Farbwerte außerhalb der Tokens
- Docker-Setup für Betrieb (Web, Worker, PostgreSQL, Redis, Caddy mit HTTPS) und Entwicklung (Live-Reload, Mailpit)
- Health-Check `/healthz/`, Celery-Worker mit Beat
- Makefile, CI (Lint, Tests, Sicherheits-Check, Docker-Build) und Release-Workflow (Image nach GHCR)
