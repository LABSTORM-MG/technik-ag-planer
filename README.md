# Technik-AG Planer

Planungs-App für Technik-AGs an Schulen: Produktionen, Jobs und Crew, Kalender, Material, Board und Technik-Anfragen – als Django-Web-App für Handy, Tablet und Computer (PWA).

> **Stand:** Meilensteine 1–4 von 12 sind fertig – Grundgerüst, Konten und AGs, Produktionen, Kalender und Zeiten. Details: [Umsetzungsstand](docs/feature-liste.md#16-umsetzungsstand-und-entscheidungen).

## Was die App schon kann

- **Konten nur auf Einladung**, Anmeldung mit Zwei-Faktor (Authenticator-App), mehrere AGs je Konto, Rollen Owner, Admin, Lehrkraft und Schüler/in
- **Produktionen** mit Jobs, Crew (anfragen, einteilen, Konfliktwarnung), To-dos, Aufsicht, Kopieren und „Kürzlich gelöscht“
- **Dashboard „Was steht an?“** mit nächster Produktion und „Meine Jobs“
- **Kalender** (Monat, Woche, Agenda), Termine und Terminserien, Stundenraster, „Nicht verfügbar“, Export als `.ics`
- **Django-Admin** für den Betreiber: AGs anlegen, Owner einladen, Konten verwalten, Datenexport, Änderungsprotokoll

## Schnellstart (Entwicklung)

Voraussetzungen: Docker mit Compose und `make`. Für Arbeit ohne Docker zusätzlich [uv](https://docs.astral.sh/uv/).

```sh
make dev            # App auf http://localhost:8000, Test-Mails (Mailpit) auf http://localhost:8025
make migrate        # in einem zweiten Terminal: Datenbank einrichten
make beispieldaten  # zwei Beispiel-AGs mit Konten, Produktionen und Terminen
make superuser      # Betreiber-Konto für den Django-Admin (http://localhost:8000/admin/)
```

Beispielkonten (Passwort jeweils `technik-ag-planer`):

| Konto | Rolle |
| --- | --- |
| `owner@nord.example` | Owner der Technik-AG Nord |
| `admin@nord.example` | Admin |
| `lehrkraft@nord.example` | Lehrkraft |
| `emma@nord.example` | Schülerin, auch Mitglied der Technik-AG Süd |
| `ben@nord.example` | Schüler |

Weitere Befehle:

```sh
make test       # Tests gegen PostgreSQL
make lint       # Code prüfen (ruff)
make format     # Code formatieren
make reset-db   # Entwicklungs-Datenbank neu aufsetzen (z. B. nach größeren Modelländerungen)
make help       # alle Befehle
```

Die Entwicklungsumgebung braucht keine `.env`. Nach neuen Abhängigkeiten (`uv add …` in `app/`) einmal `make build`.

## Betrieb

Kurzfassung – Details in [docs/installation/](docs/installation/README.md):

```sh
cp .env.example .env   # Werte eintragen, v. a. Domain, Passwörter, Secret Key
docker compose -f deploy/docker-compose.yml up -d
```

Caddy holt automatisch ein HTTPS-Zertifikat für `DOMAIN`. Migrationen laufen beim Start des Web-Containers. Den Django-Admin für den Betreiber beschreibt [docs/betrieb/django-admin.md](docs/betrieb/django-admin.md).

## Aufbau

| Ordner | Inhalt |
| --- | --- |
| `app/` | Django-Projekt: `config/` (Settings, URLs, Celery), `apps/` (Fach-Apps), `templates/`, `static/`, `tests/` |
| `deploy/` | Dockerfile, Compose für Betrieb und Entwicklung, Caddy |
| `docs/` | Feature-Liste, Architektur-Entscheidungen, Anleitungen – Übersicht in [docs/README.md](docs/README.md) |
| `.github/` | CI, Release-Workflow, Vorlagen für Issues und Pull Requests |

## Stack

Django 5.2 (Python 3.13), PostgreSQL, Redis, Celery, Docker, Caddy – Details in [ADR 0002](docs/architektur/0002-stack.md).

## Lizenz

Quelloffen (source-available) unter der [PolyForm Noncommercial License 1.0.0](LICENSE). Nutzung, Änderung und Weitergabe für nicht-kommerzielle Zwecke sind erlaubt – Schulen und andere Bildungseinrichtungen ausdrücklich eingeschlossen. Kommerzielle Nutzung ist nicht erlaubt. Für Beiträge gilt die Zustimmung in der Pull-Request-Vorlage. Sicherheitslücken bitte nicht als öffentliches Issue, sondern [privat über GitHub](https://github.com/LABSTORM-MG/technik-ag-planer/security/advisories/new) melden.
