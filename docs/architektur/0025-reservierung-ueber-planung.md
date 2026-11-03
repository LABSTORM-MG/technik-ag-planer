# ADR 0025: Reservierung über die Planung

**Status:** angenommen, 2026-11-03. Ersetzt in diesem Punkt [ADR 0023](0023-chat-und-geraete-ohne-reservierung.md).

## Kontext

Seit ADR 0023 werden keine einzelnen Geräte mehr reserviert. Beim Scannen über die Planung hinaus erhöhte die App die Planung ohne Prüfung und nahm dadurch anderen Produktionen im selben Zeitraum womöglich Material weg. Das Reservieren von Hand soll trotzdem nicht zurückkommen.

## Entscheidung

Die Planung ist die Reservierung: Eingeplantes Material ist automatisch für die Tage der Produktion belegt, und zwar als Anzahl, nicht als bestimmtes Gerät. Es gibt kein neues Modell, gerechnet wird über den vorhandenen Tagesbedarf (`inventory.services.peak_demand`).

- **Scan innerhalb der Planung:** Jedes freie Gerät geht.
- **Scan über die Planung hinaus oder ohne Planung:** `scan_unit` prüft mit `services.check`. Ist der Rest für eine andere Produktion im Zeitraum reserviert, wird der Scan gesperrt, und die Meldung nennt die Produktion. Sonst steigt die Planung, und die Kamera warnt in eigener Farbe, mit eigenem Ton und längerer Vibration.
- **Einplanen:** Bleibt bei Warnung und „Trotzdem“, etwa für geliehenes Material. Wer den Scan-Konflikt wirklich braucht, erhöht die Menge bewusst unter „Planung ändern“.

## Folgen

- Bewusst überbuchtes Material ist für beide Produktionen eingeplant. Wer zuerst packt, bekommt es; die Markierung „überbucht“ zeigt das vorher.
- Ein Gerät, das noch von einer früheren Produktion draußen ist, belegt in der Bedarfsrechnung nichts. Es lässt sich aber auch nicht scannen.
- Material ohne Bestandsangabe hat weiter keine Grenze.
