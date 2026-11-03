# Einzelgeräte, QR-Scan und Materialausgabe

Die Materialfunktionen aus Technik HUB sind als Erweiterung der bestehenden Django-App `inventory` umgesetzt. Kategorien, Bestandsmengen, Materialsätze, Produktionsplanung, Packlisten, Dateien und Defektmeldungen bleiben erhalten. Es wird keine zweite Datenbank und kein Next.js-Server benötigt.

## Einrichtung

Die neuen Tabellen und Zusatzfelder werden mit den normalen Django-Migrationen angelegt:

```sh
make migrate
```

Bestehende Bestände werden nicht automatisch in Einzelgeräte umgewandelt. Unter **Material → Material auswählen → Einzelgeräte & QR-Etiketten** lassen sich physische Geräte erfassen. Beim Hinzufügen wird ein endlicher Bestand bei Bedarf auf die Anzahl aktiver Einzelgeräte erhöht. Ein Inventarcode kann angegeben oder automatisch erzeugt werden. Laufende persönliche Ausleihen müssen vor dem Anlegen von Einzelgeräten zurückgegeben werden.

## Verwendung

- **Etiketten:** Pro Material oder über „Alle QR-Etiketten“ anzeigen und mit der Druckfunktion des Browsers drucken. Die QR-Codes enthalten Geräteadressen; der Scanner akzeptiert auch reine Inventarcodes und ältere automatisch erzeugte Codes.
- **Material packen:** Der Schalter „Ausgabe | Rückgabe“ oben gilt für die ganze Seite. Oben öffnet „Kamera öffnen“ den Scanner, darunter steht die Liste mit Suche und Filtern. Geräte und Mengen lassen sich dort auch einzeln abhaken; ein versehentlicher Haken an einem Gerät lässt sich wieder lösen, bei Mengen zählt der Haken die ganze offene Anzahl, „Teilmenge“ nur einen Teil. Code-Eingabe und Foto liegen unter „Code eingeben oder Foto aufnehmen“.
- **Planung:** In der Produktion die benötigte Menge eintragen. Damit ist die Menge für die Tage der Produktion automatisch reserviert; welche Geräte es werden, entscheidet sich erst beim Packen. Wird mehr gescannt als geplant, erhöht die App die Planung und warnt deutlich. Ist der Rest für eine andere Produktion im selben Zeitraum reserviert, sperrt sie den Scan und nennt die Produktion; wer das Material trotzdem braucht, erhöht die Menge unter „Planung ändern“.
- **Ausgabe/Rückgabe:** QR-Code per Kamera scannen, Inventarcode eingeben oder einen USB-Scanner verwenden. Die Kamera öffnet sich als eigene Vollbild-Ansicht, in der sich Ausgabe und Rückgabe umschalten lassen, und bleibt für weitere Geräte offen; „Schließen“ oder der Zurück-Knopf des Handys führen zurück. Jeder Scan meldet sich mit Popup am unteren Rand („Name“ wurde gescannt), Ton und Vibration. Das Popup zeigt auch, wie viel von diesem Material noch offen ist, der Gesamtstand steht oben in der Kamera. Ein Code, der im Bild bleibt, zählt nur einmal. Ein Gerät kann nur eine offene Ausgabe haben. Vorzeitige Ausgaben sind nur zulässig, wenn keine frühere Reservierung blockiert wird. Rückgaben bleiben auch nach Abschluss des Abbaus möglich.
- **Defekte:** Ein Defekt am Einzelgerät zählt einmal im bestehenden Materialbestand. Nur dieses Gerät wird gesperrt. Allgemeine Defektmeldungen ohne Gerätezuordnung sperren die Ausgabe der Materialart vorsorglich. Reparaturen benötigen einen Vermerk. Die Defekthistorie bleibt erhalten.
- **Abbau:** Abbau starten, Rückgaben scannen und gegebenenfalls eine begründete Ausnahme dokumentieren. „Beschädigt“ erzeugt zusätzlich eine echte Defektmeldung. Der Abschluss ist erst möglich, wenn jede offene Ausgabe eine Ausnahme besitzt. Reservierungen werden dann freigegeben; vermisste Geräte bleiben bis zur tatsächlichen Rückgabe gesperrt. Das Abbauprotokoll enthält Zeiten, Personen und Ausnahmen und lässt sich über den Browser drucken oder als PDF speichern. Ein abgeschlossener Abbau lässt sich nach einer Rückfrage wieder öffnen; dokumentierte Ausnahmen bleiben dabei erhalten. Das Abbauprotokoll gibt es als kompaktes PDF.
- **Archiv:** Ausgegebene Geräte sind vor Archivierung geschützt. Geräte mit Historie können nur archiviert werden. Bestehende Mengenbestände werden durch Gerätearchivierung nicht automatisch geändert.

Die Rollenrechte des Planers gelten weiter: Materialverwaltung für Gerätepflege und Reparaturen, Produktionsverwaltung für den Abbau, Scans außerdem für alle mit einem zugesagten Job in der Produktion; Defektmeldungen entsprechend dem bestehenden Recht. Alle Zugriffe werden auf die aktive AG begrenzt.

## Kamera und Tests

Die Kamera benötigt HTTPS oder localhost und eine Kamera-Freigabe. `html5-qrcode` 2.3.8 wird samt Apache-2.0-Lizenz lokal ausgeliefert (`app/static/vendor/`); zur Laufzeit ist kein CDN nötig. Ein Wechsel des Scanmodus erfordert keinen Kameraneustart.

```sh
make test
```

`test_units.py` prüft Ausgabe/Rückgabe, Defekte, Rechte, AG-Trennung, Gerätehistorie und Abbau. Zwei zusätzliche Parallelzugriffstests benötigen PostgreSQL und werden auf SQLite übersprungen. Hardwaretests auf den eingesetzten Handys/Tablets bleiben erforderlich. Die Migrationen sind vor dem Start der aktualisierten Anwendung auszuführen.
## Materialmodus auswählen

Unter **Einstellungen → Materialverwaltung** wird genau ein Modus für die AG ausgewählt:

- **Klassische Liste:** Mengenplanung mit Abhaken für Ausgabe und Rückgabe. QR-Etiketten, Einzelgeräteverwaltung und Scanner sind ausgeblendet und auch über direkte Links deaktiviert.
- **Einzelgeräte & QR-Codes:** Einzelgeräte erfassen, per Kamera scannen und den Abbau dokumentieren. Das manuelle Abhaken der klassischen Liste ist deaktiviert. Der Packlisten-Link öffnet für Personen mit Produktionsverwaltungsrecht direkt die Scan-Verwaltung.

Der Standard ist die klassische Liste. Vor dem Wechsel zurück müssen Geräteausgaben zurückgegeben werden. Geräte, Ausgaben und Defekthistorien werden beim Wechsel nicht gelöscht.

Im QR-Modus lassen sich Geräte unter **Material → Material auswählen → Einzelgeräte & QR-Etiketten → Einzelgerät hinzufügen** anlegen. Bleibt der Inventarcode leer, wird automatisch ein Code erzeugt. Übersteigt die Anzahl aktiver Geräte den bisherigen endlichen Bestand, wird dieser entsprechend erhöht.
## Materialarten im QR-Modus

Im Materialformular lässt sich die Verwaltungsart auswählen:

- **Mengenmaterial:** beispielsweise „XLR-Kabel, 5 m“. In der Produktion wird die benötigte Menge geplant. Unter Ausgabe/Rückgabe werden Stückzahlen erfasst; Teilrückgaben sind möglich. Es werden keine bestimmten Kabel reserviert oder einzeln gescannt.
- **Einzelgeräte:** per Inventarcode scannen. Bestehende Einzelgeräte werden bei der Migration automatisch dieser Verwaltungsart zugeordnet.
- **Verbrauchsmaterial:** Entnahmen ohne Rückgabe erfassen. Ein endlicher Bestand wird bei der Entnahme verringert.

Die Ausgabe ist auf die geplante und verfügbare Menge begrenzt. Alle Mengenbewegungen sind im Abbauprotokoll dokumentiert. Offene Rückgaben von Mengenmaterial verhindern den Abbauabschluss und den Wechsel zurück zum klassischen Modus. Nach Geräteerfassung oder ersten Ausgaben ist die Verwaltungsart zum Schutz der Historie festgelegt.
