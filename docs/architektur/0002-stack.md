# ADR 0002: Technischer Stack

- **Status:** angenommen
- **Datum:** 2026-10-16

## Kontext

Die Feature-Liste legt Django, PostgreSQL, Redis, Docker und Caddy fest (Abschnitte 1 und 14). Offen waren Version, Werkzeuge und die Frage, wie das Frontend gebaut wird. Das Projekt wird von einer Person mit Claude Code entwickelt und auf einem eigenen Server betrieben.

## Entscheidung

| Thema | Wahl |
| --- | --- |
| Python / Django | Python 3.13, Django 5.2 LTS (Support bis April 2028) |
| Abhängigkeiten | uv mit `app/pyproject.toml` und `app/uv.lock` |
| Konfiguration | `django-environ`; Werte aus Umgebungsvariablen bzw. `.env` |
| Settings | `config/settings/base.py`, `dev.py`, `test.py`, `prod.py` |
| Hintergrund-Tasks | Celery mit Redis als Broker; ein Container `worker` mit eingebautem Beat |
| Webserver | Gunicorn, statische Dateien über WhiteNoise, Caddy davor (TLS) |
| Frontend | Django-Templates, reines CSS mit Design-Tokens, wenig Vanilla-JS, kein Build-Schritt |
| Schrift / Icons | System-Schriften und eigene Inline-SVG-Icons, keine externen Dienste |
| Tests / Lint | pytest + pytest-django, ruff (Lint und Format) |

**Warum Django:** Admin-Oberfläche für den Betreiber ohne Zusatzaufwand (Abschnitt 2), ausgereifte Benutzer- und Rechteverwaltung, Templates ohne getrenntes Frontend-Projekt, große Verbreitung – gut für ein Schulprojekt, das langfristig von wechselnden Leuten gepflegt werden kann.

**Warum kein JS-Build:** Weniger bewegliche Teile, keine Node-Abhängigkeiten im Betrieb. Wenn Interaktion es nötig macht (z. B. Kalender, Board), kann htmx oder eine kleine Bibliothek als statische Datei ergänzt werden – per neuem ADR.

**Warum Celery:** Erinnerungen, Kalender-Abgleich, Systemmeldungen und Aufräumjobs (3 bzw. 7 Tage) brauchen geplante und asynchrone Aufgaben; Redis ist ohnehin vorgesehen.

## Folgen

- Neue Abhängigkeiten: `uv add …` in `app/`, danach `make build`.
- `make test` läuft im Dev-Container gegen PostgreSQL, wie die CI.
- Ein Test verhindert Farbwerte außerhalb von `static/css/tokens.css`.
