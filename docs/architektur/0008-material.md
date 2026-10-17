# ADR 0008: Material, Defekte, Materialsätze und Packliste

- **Status:** angenommen
- **Datum:** 2026-10-17

## Kontext

Meilenstein 6 (Abschnitt 7, dazu Material und Packliste aus Abschnitt 5) bringt die Verwaltung der Technik: Material mit Kategorien und Bestand, Defektmeldungen, Materialsätze und die Planung je Produktion mit Konfliktwarnung. Dateien und Fotos brauchen das Google Drive der AG (M10), die Packliste als PDF folgt in M8.

## Entscheidungen

**Neue App `apps/inventory/`** laut Abschnitt 14 mit den Modellen `MaterialCategory`, `Material`, `MaterialLink`, `DefectReport`, `Kit`, `KitItem` und `PlannedMaterial`.

**Bestand und Defekte:**

- `Material.quantity` leer bedeutet „beliebig“ (z. B. Gaffa-Tape). Solches Material löst nie eine Konfliktwarnung aus.
- Verfügbar = Bestand − Menge der Defekte mit Status „defekt“ oder „in Reparatur“. Ab „repariert“ zählt das Gerät wieder.
- Defekt melden dürfen alle; den Status ändern dürfen alle mit „Material anlegen, bearbeiten, archivieren“.
- Bei einer Meldung und bei „repariert“ schreibt das Board eine Systemmeldung (Signal in `apps/board/signals.py`, wie bei Produktionen). Systemmeldungen bekommen dafür einen optionalen Link zum Material (`Message.link_material`).

**Konfliktwarnung als Spitzenbedarf je Tag:**

- Material gehört zur Produktion, gerechnet wird über deren Zeitraum (Von–Bis).
- Für jeden Tag zählt die App die Mengen aller nicht gelöschten Produktionen, die diesen Tag abdecken. Ein Konflikt besteht, wenn der höchste Tageswert den verfügbaren Bestand übersteigt.
- Einfach alle überlappenden Produktionen zu addieren wäre zu streng: Zwei Produktionen, die nacheinander liegen und nur eine dritte gemeinsam überlappen, bräuchten das Material nie gleichzeitig.
- Wie bei der Crew warnt die App beim Einplanen und erlaubt „Trotzdem einplanen“. Überbuchungen sind in der Produktion und beim Material („Geplant“) markiert.
- Alle Produktionen zählen, unabhängig vom Status – eigene Status wie „Abgesagt“ kann die App nicht deuten.

**Materialsätze werden kopiert:** Beim Einplanen eines Satzes legt die App je Position eine normale Zeile an (`source_kit` nur zur Anzeige „aus Satz …“). Ist das Material schon geplant, erhöht sich die Menge. Änderungen am Satz oder sein Löschen ändern bestehende Planungen nicht. Archiviertes Material wird übersprungen und gemeldet.

**Rechte:**

- Material-Kategorien sind getrennt von den Produktions-Kategorien, werden aber mit demselben Recht verwaltet („Kategorien und ‚Technik anfragen‘-Link verwalten“: Owner und Admins).
- Material einer Produktion planen: „Produktionen anlegen und bearbeiten“.
- Materialsätze ansehen: alle; anlegen, bearbeiten, kopieren und löschen: Owner und Admins.
- Die Packliste dürfen alle Mitglieder abhaken (wie To-dos): Beim Packen helfen meist Schülerinnen und Schüler.

**Archivieren statt Löschen:** Archiviertes Material ist nicht mehr planbar und nicht in Sätzen wählbar; bestehende Planungen und Sätze bleiben.

**Produktion kopieren** übernimmt das geplante Material mit Mengen, ohne Packlisten-Haken.

## Später

- Dateien zum Material und Fotos bei Defektmeldungen: M10 (Google Drive). Bis dahin nur Links.
- Packliste als PDF: M8.
