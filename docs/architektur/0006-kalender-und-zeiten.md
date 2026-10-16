# ADR 0006: Kalender, Serien, Schulstunden und ICS

- **Status:** angenommen
- **Datum:** 2026-10-16

## Kontext

Meilenstein 4 (Abschnitte 4 und 9) bringt Kalender, Termine mit Serien, das Stundenraster, „Nicht verfügbar“, Konfliktwarnungen und den Export einzelner Einträge. Die Lösungen sollen einfach bleiben und M10 (Google Kalender) vorbereiten.

## Entscheidungen

**Serien als einzelne Termine:**

- Eine `EventSeries` (wöchentlich, alle 2 Wochen, monatlich; Enddatum, höchstens ca. ein Schuljahr) erzeugt beim Anlegen alle Termine als eigene Datensätze.
- Einzelne Termine lassen sich verschieben oder absagen; sie werden dabei als `is_detached` markiert.
- „Diesen und alle folgenden“ ändert nur Termine ab diesem Datum, die nicht einzeln geändert wurden.
- Das ist einfacher als Wiederholungsregeln mit Ausnahmen und passt eins zu eins zu einzelnen Google-Terminen.
- Monatlich heißt „gleicher Tag im Monat“; gibt es ihn nicht (31.), entfällt der Termin in diesem Monat.
- Abgesagte Termine bleiben sichtbar (durchgestrichen).

**„Nicht verfügbar“ als durchgehender Zeitraum:** Von (Datum, Uhrzeit) bis (Datum, Uhrzeit); ohne Uhrzeit gilt der ganze Tag. Die Einträge sind im AG-Kalender für alle sichtbar, ändern kann sie nur die Person selbst.

**Schulstunden:**

- Zeitfelder haben eine zusätzliche Auswahl „Stunde“ (`PeriodTimesMixin` in `apps/scheduling/forms.py`). Der Server rechnet sie über das Stundenraster in Uhrzeiten um, per JavaScript werden die Zeitfelder sofort sichtbar mit ausgefüllt.
- `periods.affected_periods()` liefert die betroffenen Stunden eines Zeitraums für die Freistellungsliste (M8).

**Konflikte:** `services.find_conflicts(membership, start, end)` prüft Jobs, Termine und „Nicht verfügbar“. Crew- und Termin-Einteilung warnen damit; nach Bestätigung lässt sich trotzdem einteilen.

**Eine Quelle für Kalendereinträge:** `calendar.calendar_entries(org, start, end, membership=None)` liefert einheitliche `Entry`-Objekte für Produktionen, Jobs, Termine und Abwesenheiten. Die Kalenderansichten nutzen sie, in M10 auch die Übertragung in den Google Kalender.

**ICS ohne Abhängigkeit:**

- `apps/scheduling/ics.py` schreibt RFC 5545 direkt: Zeiten in UTC, ganztägig als `VALUE=DATE`, Zeilen auf 75 Byte umgebrochen.
- Die UIDs sind stabil (`<art>-<id>@<domain>`), damit ein erneuter Import den Eintrag aktualisiert statt ihn zu verdoppeln.

**Wochenansicht ohne Stundenraster-Grafik:** Sieben Spalten (am Handy untereinander) mit Einträgen in zeitlicher Reihenfolge – gut lesbar auf kleinen Bildschirmen.

## Folgen

- Die Wiederholung einer bestehenden Serie (Rhythmus, Enddatum) lässt sich nicht nachträglich ändern; dafür „alle folgenden“ löschen und neu anlegen.
- Weitere Stellen mit Zeitfeldern sollen `PeriodTimesMixin` und `includes/time_or_period.html` nutzen.
