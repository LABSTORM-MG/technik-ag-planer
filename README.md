# Technik-AG Planer

Planungs-App für Technik-AGs an Schulen: Produktionen, Jobs und Crew, Kalender, Material, Board und Technik-Anfragen – als Django-Web-App für Handy, Tablet und Computer (PWA).

> **Status:** Meilenstein 1 (Grundgerüst) – Layout und Infrastruktur stehen, die Fachfunktionen folgen.

## Schnellstart (Entwicklung)

Voraussetzungen: Docker mit Compose und `make`. Für Arbeit ohne Docker zusätzlich [uv](https://docs.astral.sh/uv/).

```sh
make dev      # App auf http://localhost:8000, Test-Mails auf http://localhost:8025
make migrate  # in einem zweiten Terminal: Datenbank einrichten
make test     # Tests gegen PostgreSQL
make lint     # Code prüfen
make help     # alle Befehle
```

Die Entwicklungsumgebung braucht keine `.env`. Nach neuen Abhängigkeiten (`uv add …` in `app/`) einmal `make build`.

## Betrieb

```sh
cp .env.example .env   # Werte eintragen, v. a. Domain, Passwörter, Secret Key
docker compose -f deploy/docker-compose.yml up -d
```

Caddy holt automatisch ein HTTPS-Zertifikat für `DOMAIN`. Migrationen laufen beim Start des Web-Containers. Ausführliche Anleitungen folgen in [docs/installation/](docs/installation/).

## Aufbau

| Ordner | Inhalt |
| --- | --- |
| `app/` | Django-Projekt (`config/`, `apps/`, `templates/`, `static/`, `tests/`) |
| `deploy/` | Dockerfile, Compose für Betrieb und Entwicklung, Caddy |
| `docs/` | Feature-Liste, Architektur-Entscheidungen, Anleitungen |

## Dokumentation

- [Feature-Liste](docs/feature-liste.md) – verbindliche Spezifikation und Meilensteine
- [Architektur und Entscheidungen (ADRs)](docs/architektur/)
- [Installation](docs/installation/) · [Betrieb](docs/betrieb/) · [Handbuch](docs/handbuch/)

## Stack

Django 5.2 (Python 3.13), PostgreSQL, Redis, Celery, Docker, Caddy – Details in [ADR 0002](docs/architektur/0002-stack.md).

## Lizenz

Quelloffen (source-available) unter der [PolyForm Noncommercial License 1.0.0](LICENSE). Nutzung, Änderung und Weitergabe für nicht-kommerzielle Zwecke sind erlaubt – Schulen und andere Bildungseinrichtungen ausdrücklich eingeschlossen. Kommerzielle Nutzung ist nicht erlaubt. Beiträge siehe [CONTRIBUTING.md](CONTRIBUTING.md).
