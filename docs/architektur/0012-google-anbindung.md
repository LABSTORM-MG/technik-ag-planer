# ADR 0012: Google-Anbindung – Drive-Ablage und Kalender-Übertragung

- **Status:** angenommen
- **Datum:** 2026-10-18

## Kontext

Meilenstein 10 (Abschnitte 2 und 9): Der Owner verbindet ein normales Google-Konto der AG. Darüber speichert die App hochgeladene Dateien im Google Drive und überträgt alle Kalendereinträge in einen eigenen Google-Kalender, nur in eine Richtung (App → Google). Jede selbst gehostete Installation braucht dafür ein eigenes Google-Cloud-Projekt (Anleitung: `docs/installation/google-cloud.md`).

## Entscheidungen

**So wenig Rechte wie möglich:** Die App fragt nur nach `openid`, `userinfo.email`, `drive.file` (nur selbst angelegte Dateien) und `calendar.app.created` (nur der selbst angelegte Kalender und dessen Termine). Den Kalender für Mitglieder freigeben macht der Owner direkt in Google Kalender – so braucht die App kein Recht auf Freigaben (`calendar.acls`). Die App zeigt den Link zum Abonnieren.

**Token verschlüsselt:** Der Refresh-Token liegt verschlüsselt in der Datenbank (Fernet, Schlüssel aus `DJANGO_SECRET_KEY` abgeleitet). Ein neuer Secret Key macht die Verbindung ungültig; der Owner verbindet dann neu. Der Token ist vom Änderungsprotokoll und vom Datenexport ausgenommen. Die Anmeldung nutzt den Authorization-Code-Flow mit PKCE und `state` in der Session; fehlt die Zustimmung für Drive oder Kalender, speichert die App nichts und sagt, was fehlt.

**Neue App `apps/google_sync/`** (Abschnitt 14). Alle Google-Aufrufe laufen über `google_api.py`; Tests ersetzen sie durch eine Attrappe im Speicher. Google-Fehler werden zu `GoogleError` mit deutschem Text („Kein Google-Konto verbunden – bitte den Owner fragen“, „Google-Drive-Speicher ist voll“, „Verbindung zu Google abgelaufen …“).

**Kalender als Gesamtvergleich:** `sync_calendar(org)` berechnet den Soll-Stand aller Einträge ab einem Jahr zurück (Produktionen ganztägig, Jobs mit Uhrzeit, Termine, „Nicht verfügbar“) und vergleicht ihn über `SyncedEvent` (App-Schlüssel → Google-Termin-ID + Prüfsumme) mit dem Google-Kalender: anlegen, nur bei geänderter Prüfsumme ändern, löschen. Ausgelöst wird er gebündelt nach Änderungen (Signal → Celery-Task, 15 Sekunden gesammelt), nach dem Verbinden und nachts. Eine Sperre im Cache verhindert parallele Läufe. Vorteil: Verpasste Signale, Massenänderungen und Änderungen direkt in Google werden beim nächsten Lauf korrigiert. Die App-ID steht unsichtbar am Google-Termin (`extendedProperties.private.app_key`). Ist der Kalender in Google gelöscht worden, legt die App ihn neu an.

**Inhalt:** Beschreibung mit Status, Notizen, Treffpunkt, Jobs mit Crew und Link in die App; Ort mit Adresse; Farbe nach Kategorie (die 12 Palette-Farben auf die 11 Google-Farben abgebildet, Pink und Koralle teilen sich „Flamingo“), Termine in Lavendel. „Nicht verfügbar“ in Graphit mit „Nicht verfügbar: Name“ – ohne die private Notiz. Abgesagte Termine bleiben mit „Abgesagt: “ sichtbar (wie in der App).

**Drive-Ablage:** Ordner „Technik-AG Planer – <AG>“ mit „Produktionen/<Name (Datum)>“, „Material“ (auch Defektfotos) und „Anfragen“. Modell `Attachment` hängt an genau einem Eintrag (Produktion, Material, Defektmeldung, Anfrage). Geöffnet wird über die App, die die Datei mit Rechteprüfung aus dem Drive weiterreicht – Mitglieder brauchen keinen Google-Zugang. Nur Fotos und PDFs zeigt der Browser direkt an; alles andere wird heruntergeladen, damit hochgeladene Dateien nie als Seite der App laufen. Höchstgröße 25 MB, im öffentlichen Anfrage-Formular 10 MB und nur echte PDFs. Wird ein Ordner im Drive gelöscht, legt die App ihn beim nächsten Upload neu an.

**Löschen im Drive nur ausdrücklich:** Datei löschen, Produktion nach 7 Tagen endgültig löschen und Anfrage nach 180 Tagen löschen entfernen auch die Drive-Datei. AG auflösen und Konto trennen lassen alles im Drive (Abschnitt 2) – deshalb kein Löschen per Signal bei Kaskaden.

**Trennen:** Token bei Google widerrufen; Kalender und Dateien bleiben. Wird später dasselbe Konto verbunden, nutzt die App Kalender und Ordner weiter; bei einem anderen Konto legt sie beides neu an.

**Rechte:** Verbinden, Trennen, Abgleichen: „Google-Konto … verwalten“ (Owner). Dateien an Produktionen und Links: „Produktionen anlegen und bearbeiten“; Dateien zum Material: „Material anlegen, bearbeiten, archivieren“; Defektfoto: „Defekt melden“; PDF einer Anfrage öffnen: „Technik-Anfragen sehen …“. Öffnen sonst für alle Mitglieder.

**Nebenbei behoben:** `Production.status` ist jetzt `RESTRICT` statt `PROTECT`. Vorher scheiterte „Organisation auflösen“, sobald es Produktionen gab; ein benutzter Status lässt sich weiterhin nicht einzeln löschen.

## Später

- Dateien optional als Drive-Anhang am Google-Termin (Abschnitt 9, „optional“) – bisher nicht umgesetzt.
