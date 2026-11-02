# ADR 0022: Optionaler QR-Modus und gemischte Materialverwaltung

- Datum: 2026-11-02
- Status: angenommen
- Ergänzt: [ADR 0008](0008-material.md)

## Kontext

Die bisherige Materialplanung verwaltet Mengen und Packlisten-Haken. Teure Geräte benötigen eine konkrete Zuordnung und nachvollziehbare Ausgabe. Bei Kabeln wäre derselbe Zwang pro Einzelstück im Alltag zu aufwendig. Bestehende AGs sollen ihren bisherigen Ablauf behalten können.

## Entscheidung

Ein exklusiver Modus je AG (`inventory_qr_enabled`, standardmäßig aus) erhält den klassischen Ablauf. Im QR-Modus unterscheidet `Material.tracking` Mengenmaterial, Einzelgeräte und Verbrauchsmaterial. Alle Daten bleiben in Django/PostgreSQL innerhalb der vorhandenen Fach-Apps.

Die gemeinsame Ausgabeansicht enthält Mengenaktionen beziehungsweise QR-Scan. Transaktionen, Zeilensperren und eine Constraint für höchstens eine offene Geräteausgabe sichern konkurrierende Änderungen ab.

Gerätedefekte erweitern `DefectReport`. Eigene Modelle erfassen Geräte, Ausgaben, Mengenbewegungen, Abbau und Ausnahmen. Historien verhindern unkontrolliertes Löschen. Fehlende Geräte bleiben auch nach dokumentiertem Abbauabschluss gesperrt. Verbrauchsmaterial reduziert endlichen Bestand ohne Rückgabepflicht.

QR-Erzeugung nutzt `qrcode`; Kameralesen erfolgt über lokal ausgeliefertes `html5-qrcode` 2.3.8 einschließlich Lizenz. Keine neue Buildpipeline oder Laufzeit-CDN-Abhängigkeit. Das Abbauprotokoll verwendet zunächst Browserdruck.

## Folgen und Grenzen

Der zusätzliche Modus erfordert eine Migration und Schutz beim Umschalten. Ein bestehender Bestandswert wird nicht automatisch in physische Geräte aufgeteilt; vorhandene Geräte erhalten dagegen die Verwaltungsart `individual`. Nach Geräteerfassung oder Mengenbewegungen ist die Verwaltungsart gesperrt.

Die sieben neuen Modelle sind beim bestehenden Audit-/Exportmechanismus registriert; gezielte Tests prüfen Export und Protokollierung. Löschpfade mit `PROTECT`, vollständige Regression, echte Mobilgeräte und Drucklayout sind vor Übernahme zu prüfen. Mengenverluste und Wiederöffnung eines abgeschlossenen Abbaus sind noch keine unterstützten Abläufe.

Details, Modellübersicht, Migrationen, Teststände und Restarbeiten: [Entwicklerübergabe](../entwicklung/materialerweiterung.md). Bedienung: [Handbuch](../handbuch/material-scans.md).

## Übernahme in das Hauptprojekt

- **Keine private Ausleihe:** `MaterialCheckout` ist entfallen. Material verlässt das Lager nur für eine Produktion.
- **Wer ausgeben darf:** Recht `ISSUE_MATERIAL` (Owner, Admin, Lehrkraft) und alle mit einem zugesagten Job in dieser Produktion, egal welchem. Eine bloße Anfrage reicht nicht. Der Abbau bleibt bei der Produktionsleitung.
- **Löschen:** `RESTRICT` statt `PROTECT`, damit AGs aufgelöst werden können und einzelnes Löschen trotzdem blockiert ist. `UnitIssue.production` wird beim endgültigen Löschen leer, der Name bleibt als Text. Der Aufräumlauf überspringt Produktionen, von denen noch Material draußen ist.
- **Inventarcodes:** eindeutig je AG, damit keine AG von den Codes einer anderen erfährt.
- **Kamera:** `camera=(self)` im Caddy-Header. Beim Einspielen muss Caddy neu laden.

Die anfängliche Reservierung einzelner Geräte ist mit [ADR 0023](0023-chat-und-geraete-ohne-reservierung.md) entfallen.
