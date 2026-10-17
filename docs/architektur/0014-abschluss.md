# ADR 0014: Abschluss – Landingpage, Rechtstexte, CSP, Sicherheits-Test, Backups

- **Status:** angenommen
- **Datum:** 2026-10-18

## Kontext

Meilenstein 12 (Abschnitte 10, 12, 14, 15): Einstellungen vervollständigen, Hilfe & FAQ, Landingpage, Installations- und Betriebsdoku, Sicherheits-Review; dazu das Login wieder mit E-Mail-Eingabe.

## Entscheidungen

**Landingpage an „/“:** Nicht Angemeldete sehen unter `/` die Landingpage, Angemeldete das Dashboard (Decorator `apps.core.decorators.landing_for_anonymous`). So bleibt die Startadresse der installierten App (`start_url: /`) gleich. Die Screenshots erzeugt `scripts/screenshots.py` (Selenium, Firefox ohne Fenster) aus den Beispieldaten; die Handybreite entsteht per CSS-Zoom, weil Firefox ohne Fenster nicht schmaler als 500 px wird.

**Rechtstexte im Django-Admin:** Modell `LegalPage` (Impressum, Datenschutz, Nutzungsbedingungen) in `apps/core` – Daten der Installation, nicht einer AG, deshalb ohne Änderungsprotokoll und Datenexport. Der Text wird escaped und nur mit Absätzen und anklickbaren Links dargestellt. Vorlagen mit den tatsächlich verarbeiteten Daten und Fristen in `docs/rechtliches/`, ausdrücklich ohne Rechtsberatung.

**Hilfe & FAQ als Datenliste** (`apps/core/help.py`) mit Rollenfilter; ausführliche Anleitungen in `docs/handbuch/`. „Über die App“ zeigt die Version aus `APP_VERSION` (im Image aus dem Git-Tag gesetzt), die Lizenz und den Link zum Quellcode.

**Content-Security-Policy** über eine eigene Middleware (Django 5.2 hat keine eingebaute): nur eigene Skripte, Styles und Bilder (`data:` für den 2FA-QR-Code), `form-action` zusätzlich für die Google-Anmeldung, `frame-ancestors 'none'`. Der Django-Admin ist ausgenommen. Ein Test verhindert Inline-Skripte und -Styles in Templates.

**Sicherheits-Test über alle Views:** `org_required` markiert seine Views (`checks_organization`); `tests/test_security.py` geht alle URL-Muster durch. Jede View ist entweder in der Liste der öffentlichen Views, in der Liste der Konto-Views ohne AG-Bezug oder prüft AG und Recht. Neue Views müssen bewusst eingeordnet werden.

**Push nur an bekannte Push-Dienste:** Der Endpunkt eines Geräts muss zu Google, Mozilla, Apple oder Microsoft gehören (Schutz vor Server-Side Request Forgery).

**Backups:** `deploy/backup/backup.sh` sichert die Datenbank (`pg_dump --format=custom`) und die `.env`, löscht nach 14 Tagen; `restore.sh` spielt ein. Dateien liegen im Google Drive der AGs und werden nicht gesichert. Caddy begrenzt Anfragen auf 30 MB.

**Login:** wieder `EmailField`; die Beispielkonten heißen `owner@example.org` usw., Passwort weiterhin der Name vor dem @.

Bericht des Reviews: `docs/sicherheit/review-2026-10.md`.
