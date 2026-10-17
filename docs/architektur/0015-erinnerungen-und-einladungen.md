# ADR 0015: Erinnerungen vor Terminen, Einladungen aufräumen

- **Status:** angenommen
- **Datum:** 2026-10-18

## Kontext

Wartung nach Meilenstein 12: Punkte aus „Ideen für später“ (Feature-Liste, Abschnitt 16).

## Entscheidungen

**Erinnerungen auch vor Terminen:** Wer zu einem Termin (z. B. AG-Treffen) zugesagt hat, bekommt dieselbe Erinnerung wie vor Jobs – nach denselben Einstellungen (Vorabend um …, oder … Stunden vorher), mit Uhrzeit und Ort. Ganztägige und abgesagte Termine bekommen keine Erinnerung. `EventAttendee.reminded_for` verhindert Doppelte und sorgt bei verschobenen Terminen für eine neue Erinnerung. Jobs und Termine nutzen dieselbe Logik (`apps.notifications.tasks._remind`).

**Einladungen aufräumen:** Ein täglicher Task löscht Einladungen 30 Tage nach Ablauf, Rückzug oder Annahme (`INVITATION_KEEP_DAYS`). Sie enthalten E-Mail-Adressen und werden danach nicht mehr gebraucht (Datensparsamkeit, Abschnitt 11). Offene, gültige Einladungen bleiben.

**Kein Drive-Anhang am Google-Termin:** Die Dateien liegen privat im Drive der AG (Scope `drive.file`, keine Freigaben). Mitglieder, die den Kalender abonnieren, könnten angehängte Dateien nicht öffnen; dafür müsste die App jede Datei für alle freigeben, was den Zugriff auf Dateien über die App (mit Rechteprüfung) umgehen würde. Der Termin enthält stattdessen den Link in die App, wo die Dateien liegen.
