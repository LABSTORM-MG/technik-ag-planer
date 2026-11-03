# Materialverwaltung mit QR-Modus

Technische Übersicht für die Entwicklung. Die Bedienung steht im [Handbuch](../handbuch/material-scans.md). Die Idee stammt aus einem Beitrag von `JaPe2024` (PR #23), übernommen und umgebaut in PR #30 und folgenden. Entscheidungen: [ADR 0022](../architektur/0022-material-einzelgeraete.md), [0023](../architektur/0023-chat-und-geraete-ohne-reservierung.md), [0024](../architektur/0024-qr-mindestversion.md), [0025](../architektur/0025-reservierung-ueber-planung.md).

## Modi und Verwaltungsarten

`Organization.inventory_qr_enabled` schaltet je AG zwischen klassischer Packliste und QR-Verwaltung um (Standard: klassisch). Vor dem Wechsel zurück müssen offene Geräteausgaben und Mengenrückgaben erledigt sein. Der Wechsel löscht nichts, schreibende Abläufe prüfen den Modus in der Transaktion erneut (`lock_mode`).

`Material.tracking` gilt im QR-Modus:

| Wert | Verwendung | Ablauf |
| --- | --- | --- |
| `bulk` | Kabel, Adapter | Menge planen, Stückzahlen ausgeben und auch teilweise zurücknehmen |
| `individual` | Funkmikrofon, Lichtpult | Geräte erfassen, per Scan oder Haken ausgeben und zurücknehmen |
| `consumable` | Batterien, Gaffa | Geplante Menge entnehmen, Bestand sinkt, keine Rückgabe |

## Reservierung und Ausgabe

- Die Planung ist die Reservierung, gezählt wird die Anzahl je Tag (ADR 0025). Einzelne Geräte werden nie festgelegt.
- `unit_services.scan_unit` verarbeitet die Modi `issue`, `return`, `undo_issue` und `undo_return` und gibt ein `ScanResult` zurück.
- Über die Planung hinaus prüft `reservation_conflict`: Ist der Rest anderweitig reserviert, wird der Scan gesperrt.
- `undo_issue` löscht die versehentliche Ausgabe, `undo_return` öffnet sie wieder. So verfälscht ein gelöster Haken die Zählung nicht.
- `issue_rows` zählt je Gerät einmal, auch wenn es mehrfach draußen war.
- Transaktionen und Zeilensperren reihen Änderungen; eine bedingte Unique-Constraint verhindert zwei offene Ausgaben eines Geräts.
- QR-Codes enthalten nur den Inventarcode und sind mindestens Version 2 (ADR 0024). Alte Etiketten mit Adresse bleiben lesbar. Die Etiketten druckt `labels_pdf` als A4-PDF.

## Oberfläche

`inventory/scan.html` mit `static/js/material-scanner.js`: großer Knopf „Kamera öffnen“, Vollbild-Ansicht mit Schalter und Gesamtstand, darunter die filterbare Liste (`data-picker` aus `app.js`) mit Haken. Code-Eingabe und Foto sind eingeklappt. Die JSON-Antwort liefert `message`, bei Scans zusätzlich `name`, `action`, `detail` und `over_plan`; danach lädt das Skript nur die betroffenen Abschnitte nach. Die Produktionsseite zeigt nur die Statuskarte (`services.material_status`), die Planung steht in `inventory/includes/production_plan.html`.

## Defekte und Abbau

- Ein offener Gerätedefekt sperrt nur dieses Gerät, ein allgemeiner Materialdefekt die Ausgabe der ganzen Materialart.
- `ProductionTeardown` hält Beginn und Abschluss fest, `TeardownException` begründet eine offene Geräteausgabe („vermisst“, „beschädigt“, „sonstiges“). „Beschädigt“ legt zugleich einen Defekt an.
- Abschluss nur, wenn alle Geräte zurück oder begründet und alle Mengen zurück sind. Danach sind neue Ausgaben gesperrt, Rückgaben bleiben möglich.
- `teardown(..., "reopen")` nimmt den Abschluss zurück; Ausnahmen und Defekte bleiben bestehen.
- Das Protokoll ist ein PDF über `documents:teardown_protocol`.

## Rechte

- `MANAGE_INVENTORY`: Materialmodus, Gerätepflege, Reparaturen.
- `MANAGE_PRODUCTIONS`: Planung und Abbau.
- `ISSUE_MATERIAL` oder ein zugesagter Job in genau dieser Produktion (`unit_services.can_issue`): Ausgabe und Rückgabe.
- `REPORT_DEFECT`: Gerätedefekte melden.

## Löschen und Export

Historische Beziehungen nutzen `RESTRICT`, damit eine AG-Auflösung funktioniert. `UnitIssue.production` wird beim Löschen leer, der Name bleibt in `production_name`. Der Aufräumlauf überspringt Produktionen mit ausgegebenem Material. Alle Modelle sind in `inventory/apps.py` für Änderungsprotokoll und AG-Export angemeldet.

## Noch offen

- Mengenmaterial hat keine begründete Verlustausnahme beim Abbau: Fehlende Stücke blockieren den Abschluss.
- Haken bei Mengenmaterial lassen sich nicht lösen, nur über eine Rückgabe ausgleichen.
- Test auf echten Geräten über HTTPS: Kamera, Vollbild, Ton, Vibration, Etiketten auf Papier.
