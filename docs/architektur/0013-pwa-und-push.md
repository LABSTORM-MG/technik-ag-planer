# ADR 0013: PWA und Push-Mitteilungen

- **Status:** angenommen
- **Datum:** 2026-10-18

## Kontext

Meilenstein 11 (Abschnitte 1, 5, 6, 8, 9): Die App soll sich auf dem Home-Bildschirm installieren lassen (eigenes Icon, ohne Adressleiste) und Push-Mitteilungen schicken – zu Anfragen, Änderungen und als Erinnerung vor eigenen Jobs. Benachrichtigungen kommen nur als Push, nie per E-Mail.

## Entscheidungen

**Manifest und Service Worker aus Django:** `/manifest.webmanifest` (Farben aus `apps.core.design.THEME_COLOR`, `display: standalone`) und `/sw.js` mit `Service-Worker-Allowed: /`, damit der Service Worker für die ganze Seite gilt. Der Service Worker zeigt nur Mitteilungen an und öffnet beim Antippen die passende Seite – **kein Offline-Modus** (Abschnitt 1), kein Zwischenspeichern von Seiten. Vollbild und Push funktionieren nur über HTTPS; auf dem iPhone kommt Push nur in der zum Home-Bildschirm hinzugefügten App an.

**App-Icon:** schlicht, ohne Logo oder Schulnamen, in den Farben der Design-Tokens. Drei Entwürfe (Kalender, Mischpult-Fader, Scheinwerfer) zeichnet `scripts/app_icon.py`; Vorschau in `docs/design/app-icon/`. Voreingestellt ist Entwurf B (Fader). Die Icons sind Bilder (PNG) – der Farb-Test für CSS, JS und HTML gilt für sie nicht.

**Web Push mit VAPID** (`pywebpush`). Schlüssel nur in der `.env`; `python manage.py vapid_schluessel` erzeugt sie. Ohne Schlüssel ist Push aus und die Einstellungsseite sagt das.

**Abo je Gerät, Einstellungen je Konto:** `PushSubscription` (Endpoint, Schlüssel, Gerät) und `NotificationSettings` hängen am Konto, nicht an der AG – ein Handy gehört einer Person, auch wenn sie in mehreren AGs ist. Wer in mehreren AGs ist, sieht den Namen der AG im Titel. Beide sind keine AG-Daten und deshalb weder im Änderungsprotokoll noch im Datenexport; beim Löschen des Kontos verschwinden sie mit.

**Wer bekommt was** (alles einzeln abschaltbar, Standard „an“):

| Art | Empfänger | Auslöser |
| --- | --- | --- |
| Crew-Anfragen | angefragte bzw. eingeteilte Person | Anfrage oder direkte Einteilung (Jobs und Termine) |
| Änderungen | alle Eingeteilten | Datum, Uhrzeit, Treffpunkt eines Jobs; Job gelöscht; Datum, Ort, Status oder Löschen der Produktion |
| Erinnerungen | eigene zugesagte Jobs | Standard Vorabend 18 Uhr, einstellbar „am Vorabend um …“ oder „… Stunden vorher“ |
| Technik-Anfragen | Owner, Admins, Lehrkräfte | neue Anfrage über den öffentlichen Link |
| Board | alle außer dem Absender | neue Board-Nachricht |
| Chats | Eingeteilte und Aufsicht (wie der Zähler, ADR 0007) | neue Nachricht im Produktions-Chat |

Wer etwas auslöst, bekommt dazu keine Mitteilung (über den Auslöser aus `apps.audit.context`). Ausgelöst wird über Signale – die Fach-Apps kennen die Benachrichtigungen nicht. Verschickt wird nach dem Speichern im Celery-Worker; Geräte, die der Push-Dienst als abgemeldet meldet (404/410), werden entfernt.

**Erinnerungen:** Ein Task alle 10 Minuten schickt fällige Erinnerungen mit Job, Uhrzeit und Treffpunkt („Morgen 14:00 Uhr: Aufbau Schulkonzert – Treffpunkt: Aula“). `CrewAssignment.reminded_for` merkt sich die Startzeit, für die erinnert wurde; wird der Job verschoben, kommt eine neue Erinnerung. Wer erst nach dem Erinnerungszeitpunkt eingeteilt wird, bekommt sie beim nächsten Lauf.

## Später

- Erinnerungen auch vor Terminen (AG-Treffen) – bisher nur vor Jobs, wie in Abschnitt 9 beschrieben.
