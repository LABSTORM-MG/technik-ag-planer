# ADR 0009: Technik-Anfragen über einen öffentlichen Link

- **Status:** angenommen
- **Datum:** 2026-10-17

## Kontext

Meilenstein 7 (Abschnitt 6): Lehrkräfte und Schulleitung ohne Konto fragen über einen öffentlichen Link Technik an. Owner, Admins und Lehrkräfte sehen die Anfragen oben in der Produktionsliste und legen daraus in einer geteilten Ansicht eine Produktion an. Es ist die erste Seite der App, die ohne Anmeldung Daten annimmt.

## Entscheidungen

**Neue App `apps/inquiries/`** laut Abschnitt 14 mit `InquiryLink` (genau einer je AG) und `Inquiry`.

**Token im Klartext:** Anders als Einladungen (nur Hash gespeichert) muss der Anfrage-Link in den Einstellungen immer wieder angezeigt und weitergegeben werden. Der Token ist zufällig (`secrets.token_urlsafe(16)`); „Neuen Link erzeugen“ macht den alten ungültig. Unbekannte, deaktivierte Links und Links deaktivierter AGs liefern dieselbe Seite „Dieser Link ist nicht aktiv“ (404) – so lässt sich nicht erkennen, ob ein Token existiert.

**Spam-Schutz ohne Captcha:**

- Unsichtbares Feld (Honeypot): Ist es ausgefüllt, zeigt die App die Danke-Seite, speichert aber nichts.
- Begrenzung über den Cache: höchstens 5 Anfragen pro Stunde je IP und 30 pro Stunde je Link (`INQUIRY_MAX_PER_IP_HOUR`, `INQUIRY_MAX_PER_LINK_HOUR`). Die IP kommt wie beim Login aus `apps.accounts.throttle.client_ip`.
- Bei hartnäckigem Spam hilft „Neuen Link erzeugen“.

**Öffentliche Seite zeigt nur das Nötigste:** den Namen der AG und ihre Produktions-Kategorien als „Art der Veranstaltung“. Sprache in Sie-Form; Pflicht sind nur Name, E-Mail und Datum.

**Geteilte Ansicht:**

- Ab 900 px Breite nebeneinander, darunter ein Umschalter „Anfrage | Produktion“. Ohne JavaScript stehen beide untereinander.
- Automatisch übernommen werden das Datum (Von/Bis) und die Uhrzeiten – als vorgeschlagene Jobs „Aufbau“ (Aufbau ab → Beginn), „Veranstaltung“ (Beginn → Ende) und „Abbau“ (Ende → Abbau bis), jeweils nur, wenn beide Zeiten da sind. Eine Produktion selbst hat keine Uhrzeiten.
- Alle anderen Felder per „Kopieren“ und „Einfügen“. Einfügen nimmt zuerst den zuletzt auf der Seite kopierten Text: Das Lesen der Zwischenablage ist nicht in jedem Browser erlaubt.
- Die Felder der Produktion stehen in einem gemeinsamen Include (`productions/includes/production_fields.html`), das Speichern in `apps.productions.services.save_production()`.
- Die Anfrage merkt sich die daraus angelegte Produktion; erledigt wird sie erst über „Erledigt“.

**Aufbewahrung:** Anfragen enthalten Kontaktdaten von Personen ohne Konto. Erledigte Anfragen löscht ein täglicher Celery-Task 180 Tage nach „Erledigt“ endgültig (`INQUIRY_KEEP_DONE_DAYS`). Offene Anfragen bleiben, bis jemand sie erledigt.

**Rechte:** Link verwalten: „Kategorien und ‚Technik anfragen‘-Link verwalten“ (Owner, Admins). Anfragen sehen, übernehmen und erledigen: „Technik-Anfragen sehen, übernehmen und als erledigt markieren“ (Owner, Admins, Lehrkräfte).

## Später

- PDF-Upload für den Ablauf: M10 (Google Drive). Bis dahin Freitext und Link.
- Push-Mitteilung bei neuer Anfrage: M11.
