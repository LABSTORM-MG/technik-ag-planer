# ADR 0011: Team-Funktionen – Fähigkeiten, Einsatzübersicht, Schuljahreswechsel, Konto löschen

- **Status:** angenommen
- **Datum:** 2026-10-17

## Kontext

Meilenstein 9 (Abschnitte 2, 5, 10): Fähigkeiten mit Filter und Vorschlägen beim Einteilen, Einsatzübersicht mit Stundenkorrektur und PDF, Schuljahreswechsel und „Konto löschen“, bei dem Einsätze, Board-Nachrichten und Einträge in Call Sheets anonymisiert erhalten bleiben.

## Entscheidungen

**Anonymisierung über `SET_NULL`:**

- `CrewAssignment.membership` und `EventAttendee.membership` sind nullable mit `on_delete=SET_NULL`. Board-Nachrichten hatten das schon (`author`).
- Bisher löschten „Mitglied entfernen“ und „AG verlassen“ alle Einsätze per CASCADE. Jetzt bleiben sie in allen drei Fällen erhalten (Konto löschen, Mitglied entfernen, AG verlassen).
- Angezeigt wird überall `person`, bei leerer Mitgliedschaft „Ehemaliges Mitglied“ (`apps.accounts.models.FORMER_MEMBER`).
- Die Aufsicht (M2M) entfällt beim Austritt; sie ist keine eigene Leistung.

**Konto löschen:**

- Das Konto wird wirklich gelöscht (`user.delete()`), nicht nur unkenntlich gemacht. So bleiben keine personenbezogenen Daten zurück (Abschnitt 11).
- Mitgliedschaften, „Nicht verfügbar“, Lesestand, Fähigkeiten und 2FA-Geräte verschwinden mit dem Konto; Einladungen an die E-Mail-Adresse löscht der Service.
- Owner müssen vorher die Ownership übertragen.
- Bestätigt wird mit Passwort und Häkchen.

**Fähigkeiten:**

- Modell `Skill` in `apps/productions` (Abschnitt 14) mit `members` (M2M zu `Membership`, also je AG).
- Den Datenexport habe ich dafür allgemein um Mehrfach-Zuordnungen als ID-Listen erweitert. Davon profitieren auch Aufsicht und Fähigkeiten.
- Vorschläge beim Einteilen: bis zu 3 Mitglieder mit der gewählten Fähigkeit, noch nicht im Job und ohne Überschneidung. Wer im Schuljahr die wenigsten zugesagten Einsätze hat, steht vorne – so verteilt sich die Arbeit.

**Einsatzübersicht:**

- Gezählt werden zugesagte Jobs nicht gelöschter Produktionen und zugesagte, nicht abgesagte Termine, **nur bis heute**: Die Übersicht ist ein Nachweis geleisteter Einsätze.
- Termine ohne Uhrzeit zählen 0 Stunden und lassen sich korrigieren.
- Die Korrektur steht als `corrected_hours` am Einsatz (Crew-Eintrag bzw. Termin-Teilnahme); wer sie geändert hat, hält das Änderungsprotokoll fest.
- Zeiträume: Schuljahr vom 1.8. bis 31.7., 2. Halbjahr ab 1.2., dazu „Letztes Schuljahr“ und ein eigener Zeitraum.
- PDF über `apps/documents` mit Zeilen für Ort, Datum und Unterschrift – als Grundlage für eine AG-Bescheinigung.

**Schuljahreswechsel:**

- Die Jahrgangsstufe hängt am Konto, ein Konto kann aber in mehreren AGs sein. Damit niemand doppelt hochgestuft wird, merkt sich das Konto `grade_promoted_at`; Konten, die in den letzten 180 Tagen hochgestuft wurden, werden übersprungen.
- Eine AG kann den Wechsel nur einmal in 180 Tagen auslösen (`Organization.school_year_changed_at`).
- Vor dem Auslösen zeigt eine Vorschau die Wechsel je Stufe; danach erscheint eine Systemmeldung im Board.
- Jedes Konto wird einzeln gespeichert, damit das Änderungsprotokoll jede Änderung erfasst.

## Später

- Ferien kennt die App nicht; die Freistellungsliste lässt deshalb nur Wochenenden weg.
