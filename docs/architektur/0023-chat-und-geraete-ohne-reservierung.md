# ADR 0023: Chat-Auswahl und Einzelgeräte ohne Reservierung

- **Status:** angenommen
- **Datum:** 2026-11-02

## Kontext

Beim Test auf dem Server war das Reservieren konkreter Geräte unnötige Arbeit: Für eine Produktion zählt, wie viele Geräte einer Art gebraucht werden, nicht welches. Im Chat lenkten dauerhaft sichtbare Bearbeiten- und Löschen-Links ab.

## Entscheidungen

**Keine Reservierung:** `UnitReservation` ist entfallen. Jedes freie, nicht defekte Gerät lässt sich scannen. Ist sein Material nicht eingeplant oder die Anzahl überschritten, legt `scan_unit` die Planung an oder erhöht sie und nennt das in der Meldung. Ein Gerät, das noch ausgegeben ist, bleibt gesperrt.

**Auswahl im Chat:** Gedrückthalten (ca. 450 ms, am PC Rechtsklick) startet die Auswahl mit Leiste. Bearbeiten und Kopieren nur bei genau einer Nachricht, Löschen nur, wenn alle gewählten löschbar sind. `board:delete_many` prüft jede Nachricht erneut über `can_delete` und innerhalb der AG. Ohne JavaScript bleiben die alten Links im `noscript`.

**Textauswahl:** Auf Touch-Geräten ist das Markieren von Nachrichten aus, weil Gedrückthalten sonst die Auswahl des Browsers auslöst. „Kopieren“ ersetzt das.

**Freistellungsliste als Tabelle:** `release_tables` liefert je Schultag eine Tabelle mit Personen in den Zeilen (aufsteigend nach Jahrgang) und allen Schulstunden in den Spalten. Ohne Stundenraster stehen die zusammengefassten Jobzeiten in den Spalten. Die Liste bleibt bewusst schwarz-weiß, damit sie sich gut kopieren lässt.

## Folgen

- Stehen mehrere Produktionen gleichzeitig an, verhindert nichts, dass Geräte zu früh für die erste verplant werden. Der Spitzenbedarf warnt weiter anhand der Mengen.
- Auf eine Datenmigration der Reservierungen wurde verzichtet: Sie sagten nichts aus, was noch gebraucht wird.
