# ADR 0024: QR-Codes mindestens in Version 2

**Status:** angenommen, 2026-11-03

## Kontext

Kurze Inventarcodes wie `TAG-77567C79C0` passen in QR-Version 1 (21 × 21 Module). Der Kamerascan erkannte solche Etiketten nicht, obwohl das Bild scharf war.

Ein Handy-Foto eines Etiketts wurde vermessen. Rechnerisch entzerrt stimmten alle 441 Module mit dem erzeugten Code überein, und `html5-qrcode` (ZXing) las das entzerrte Foto. Ohne Entzerrung las es das Foto nicht. Version 1 hat kein Ausrichtungsmuster, ZXing setzt die vierte Ecke deshalb als Parallelogramm an. Bei der Schräglage des Fotos liegen damit 46 Module falsch, mehr als die Fehlerkorrektur ausgleicht.

Gegenprobe mit sauberem Code in derselben Geometrie, weichgezeichnet, bei einfacher, doppelter und dreifacher Abweichung der vierten Ecke, jeweils als Datei und im Live-Scan:

| Code | Datei | Live |
| --- | --- | --- |
| Version 1, Korrekturstufe M | 0 von 3 | 0 von 3 |
| Version 2, Korrekturstufe M | 3 von 3 | 3 von 3 |
| Version 3, Korrekturstufe M | 1 von 3 | 3 von 3 |
| Version 3, Korrekturstufe Q | 1 von 3 | 3 von 3 |

## Entscheidung

`apps.inventory.unit_services.qr_png` erzeugt mindestens Version 2 mit Korrekturstufe M. Längere Codes wachsen wie bisher. Der Inhalt bleibt der reine Inventarcode.

## Folgen

- Keine neue Bibliothek und keine Änderung am Scanner oder an der CSP.
- Die Module werden bei gleicher Etikettgröße etwas kleiner (25 statt 21 je Seite).
- Der Inhalt bleibt gleich, bestehende Codes bleiben gültig. Bereits gedruckte Etiketten mit Version 1 sollten neu gedruckt werden, sie sind weiterhin nur annähernd gerade lesbar.
- Die Messung beruht auf einem echten Foto und synthetischen Bildern. Die Bestätigung mit einem echten Handy steht aus. Reicht das nicht, ist ein anderer Decoder die nächste Option.
