# ADR 0007: Board, Produktions-Chats und Systemmeldungen

- **Status:** angenommen
- **Datum:** 2026-10-16

## Kontext

Meilenstein 5 (Abschnitt 8) bringt das Board als gemeinsamen Chat der AG, Chats je Produktion, Systemmeldungen, Moderation und einen Zähler für ungelesene Nachrichten. Push-Mitteilungen folgen in M11.

## Entscheidungen

**Ein Modell für alle Chats:** `Message` mit `production` leer (Board) oder gesetzt (Produktions-Chat). Systemmeldungen sind Nachrichten der Art `system` ohne Absender; `link_production` führt zur Produktion. Ein `system_key` verhindert doppelte Meldungen.

**Polling statt WebSockets:**

- Die Seite fragt alle 10 Sekunden `board/neu/` nach neuen Nachrichten, solange der Tab sichtbar ist.
- WebSockets bräuchten Django Channels und einen ASGI-Server – zu viel Betrieb für den Nutzen.
- Bearbeitete oder gelöschte Nachrichten anderer erscheinen erst nach dem Neuladen.
- Ohne JavaScript funktioniert das Board über normale Formulare.

**Systemmeldungen über Signale:**

- `apps/board/signals.py` hört auf das Speichern von `Production` und `Membership`.
- Meldungen gibt es für: neue Produktion (auch Kopie), Status, Datum oder Ort geändert, gelöscht, wiederhergestellt und neues Mitglied.
- So müssen die anderen Apps das Board nicht kennen.
- „Noch X Plätze frei“ prüft ein täglicher Celery-Task (`announce_open_jobs`, 7:00 Uhr) für Jobs in 3 Tagen.
- Für Material (M6) steht `services.post_system()` bereit.

**Benötigte Personen je Job:** Ein neues, optionales Feld `Job.crew_needed`. Gezählt werden nur zugesagte Personen. Ohne Angabe gibt es keine Meldung.

**Lesestand:**

- `ReadMarker` speichert je Mitglied und Chat die id der zuletzt gelesenen Nachricht.
- Ohne Lesestand gilt nur als ungelesen, was seit dem Beitritt geschrieben wurde.
- Eigene Nachrichten zählen nie.

**Zähler in der Navigation:** Er zählt das Board und die Chats der Produktionen, in denen die Person eingeteilt (Crew) oder als Aufsicht eingetragen ist – dieselbe Regel wie für Push in Abschnitt 8. Die Chat-Leiste im Board zeigt die Zähler aller Chats.

**Absenderfarbe:** Der Name erscheint in einer festen Palette-Farbe, die sich aus der Konto-id ergibt (ohne Grau). Es gibt keine Farbwahl und keine neuen Tokens.

**Löschen:**

- Nachrichten werden endgültig gelöscht, ohne den Platzhalter „Nachricht gelöscht“.
- Systemmeldungen darf nur die Moderation (Lehrkraft, Admin, Owner) löschen; bearbeiten kann sie niemand.
- Ohne Absender (Konto gelöscht) steht „Ehemaliges Mitglied“; das bereitet M9 vor.

## Folgen

- Bei vielen gleichzeitigen Nutzern entstehen regelmäßige, kleine Anfragen; für AG-Größen unkritisch.
- M6 schließt die Meldungen „Material defekt“ und „wieder verfügbar“ an, M11 die Push-Mitteilungen.
