COMPOSE_DEV := docker compose -f deploy/docker-compose.dev.yml -p technik-ag-planer-dev
RUN_DEV := $(COMPOSE_DEV) run --rm web

# Dateien im eingebundenen Code gehören dem eigenen Nutzer, nicht root
export UID := $(shell id -u)
export GID := $(shell id -g)

.DEFAULT_GOAL := help
.PHONY: help dev down logs build test lint format migrate makemigrations shell superuser beispieldaten reset-db

help: ## Diese Übersicht
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-16s %s\n", $$1, $$2}'

dev: ## Entwicklungsumgebung starten (App :8000, Mailpit :8025)
	$(COMPOSE_DEV) up --build

down: ## Entwicklungsumgebung stoppen
	$(COMPOSE_DEV) down

reset-db: ## Entwicklungs-Datenbank löschen und neu aufsetzen (alle lokalen Daten weg!)
	$(COMPOSE_DEV) down -v
	$(COMPOSE_DEV) up -d db cache
	$(RUN_DEV) python manage.py migrate

logs: ## Logs der Entwicklungsumgebung
	$(COMPOSE_DEV) logs -f

build: ## Entwicklungs-Image neu bauen (z. B. nach neuen Abhängigkeiten)
	$(COMPOSE_DEV) build

test: ## Tests gegen PostgreSQL ausführen (ARGS="-k name" für Auswahl)
	$(RUN_DEV) env DJANGO_SETTINGS_MODULE=config.settings.test pytest $(ARGS)

lint: ## Code prüfen (ruff)
	$(RUN_DEV) sh -c "ruff check . && ruff format --check ."

format: ## Code formatieren und automatisch korrigierbare Fehler beheben
	$(RUN_DEV) sh -c "ruff format . && ruff check --fix ."

migrate: ## Datenbank-Migrationen ausführen
	$(RUN_DEV) python manage.py migrate

makemigrations: ## Neue Migrationen erzeugen
	$(RUN_DEV) python manage.py makemigrations

shell: ## Django-Shell
	$(RUN_DEV) python manage.py shell

superuser: ## Betreiber-Konto für den Django-Admin anlegen
	$(RUN_DEV) python manage.py createsuperuser

beispieldaten: ## Zwei Beispiel-AGs mit Konten in allen Rollen anlegen
	$(RUN_DEV) python manage.py beispieldaten
