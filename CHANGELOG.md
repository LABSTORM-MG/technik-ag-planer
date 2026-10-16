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
- Konten nur auf Einladung: Einladungslinks (einmalig, 7 Tage gültig), Name und Jahrgangsstufe beim Beitritt, erneut senden und zurückziehen
- Anmeldung mit E-Mail und Passwort, Sperre nach 5 Fehlversuchen, „Passwort vergessen“, Abmelden
- Zwei-Faktor-Anmeldung per Authenticator-App (TOTP), auf Wunsch Pflicht für alle Mitglieder einer AG
- AGs mit Rollen Owner, Admin, Lehrkraft, Schüler/in; Rechte-Tabelle als Code, gegen die Feature-Liste getestet
- Mandantentrennung mit Tests; AG wechseln, Mitgliederliste, Rollen ändern, Mitglied entfernen, Ownership übertragen, AG verlassen und auflösen
- Einstellungen in den fünf Gruppen aus Abschnitt 10 mit Rollen-Badge
- Django-Admin für den Betreiber: AG mit Owner-Einladung anlegen, Owner wechseln, Konten sperren, 2FA zurücksetzen, Datenexport als ZIP; im Betrieb nur mit 2FA
- Internes Änderungsprotokoll, Einträge werden nach 7 Tagen gelöscht
- `make beispieldaten` für lokales Durchklicken
