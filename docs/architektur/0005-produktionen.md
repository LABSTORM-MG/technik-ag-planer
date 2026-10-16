# ADR 0005: Produktionen – Farben, Status, Löschen, Formulare

- **Status:** angenommen
- **Datum:** 2026-10-16

## Kontext

Meilenstein 3 bringt Produktionen mit Jobs, Crew, Kategorien, Status-Werten und To-dos (Abschnitte 3 und 5). Dabei waren einige Grundsatzfragen zu klären, die auch spätere Formulare betreffen.

## Entscheidungen

**Feste Farbpalette statt freier Farbwahl:**

- Kategorien und Status speichern nur einen Schlüssel (`apps/productions/palette.py`).
- Die Farbwerte stehen als `--palette-…` in `tokens.css`; im HTML setzt die Klasse `color-<schlüssel>` die Variable `--item-color`.
- So bleiben alle Farben zentral, der Kontrast auf dem dunklen Grund stimmt, und die Zuordnung zu den Google-Kalender-Farben (M10) ist eindeutig.

**System-Status:**

- „In Planung“ und „Bestätigt“ sind feste System-Status (`system_key`). Sie lassen sich umbenennen und umfärben, aber nicht löschen, weil Kalender und Dashboard sie brauchen.
- Weitere Status legt der Owner an. Wird einer gelöscht, fallen seine Produktionen auf „In Planung“ zurück.
- Jede neue AG bekommt per Signal die Standard-Kategorien und System-Status; eine Datenmigration ergänzt sie für ältere AGs.

**Weiches Löschen:**

- `Production.deleted_at`. `Production.objects` blendet gelöschte aus, `Production.all_objects` zeigt alle und ist zugleich der Basis-Manager.
- Ein Celery-Task entfernt sie nach 7 Tagen endgültig (`PRODUCTION_TRASH_DAYS`).
- Jobs, Crew und To-dos gelöschter Produktionen werden in allen Abfragen über `production__deleted_at__isnull=True` ausgeblendet.

**Formulare im Bottom-Sheet:**

- Jede Formularseite funktioniert eigenständig.
- Links mit `data-sheet-url` laden sie per JavaScript mit der Kopfzeile `X-Sheet: 1`; der Context-Processor setzt dann `layout = "fragment.html"` statt `base.html`.
- Templates, die das unterstützen, beginnen mit `{% extends layout %}`. Abgeschickt wird normal.

**Entwürfe im Browser:**

- `<form data-draft="schlüssel">` speichert Eingaben in `localStorage` und stellt sie beim nächsten Öffnen wieder her.
- „Entwurf verwerfen“ löscht den Entwurf, nach dem Speichern verschwindet er ebenfalls.
- Auf dem Server liegt kein Entwurf.

**Konflikte bei der Crew:**

- Überschneiden sich Jobs zeitlich, zeigt die App eine Warnung; nach Bestätigung lässt sich trotzdem einteilen.
- „Nicht verfügbar“ (M4) wird in `services.overlapping_assignments` bzw. daneben ergänzt.

## Folgen

- Neue farbige Dinge (z. B. Material-Kategorien in M6) nutzen dieselbe Palette.
- M5 hängt die Board-Systemmeldung „Neue Produktion“ an das Speichern an; `chat_enabled` ist schon gespeichert.
