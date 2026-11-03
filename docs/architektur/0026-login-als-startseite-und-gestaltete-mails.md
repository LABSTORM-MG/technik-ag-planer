# ADR 0026: Login als Startseite, gestaltete E-Mails

**Status:** angenommen, 2026-11-03. Ersetzt in Bezug auf die Landingpage [ADR 0014](0014-abschluss.md).

## Kontext

Die App richtet sich nur an eingeladene Mitglieder, eine öffentliche Werbeseite braucht sie nicht. Die Einladungs- und Passwort-Mails waren bisher nur Text mit einem Link. Mail-Programme kennen außerdem keine CSS-Variablen, die Regel „Farben nur über Design-Tokens“ war für Mails also ungeklärt.

## Entscheidung

**Startseite:** Nicht Angemeldete landen unter `/` beim Login, Angemeldete beim Dashboard. Das erledigt die `LoginRequiredMiddleware`. Landingpage, Screenshots und `scripts/screenshots.py` sind entfernt.

Ohne Anmeldung bleiben nur die Seiten erreichbar, die anders nicht funktionieren: Rechtstexte, Einladung annehmen, „Passwort vergessen“, Technik-Anfrage per Link, Manifest, Service Worker und Health-Check.

**E-Mails:** Gerüst in `templates/emails/base.html`, Button in `emails/includes/button.html`. Tabellen-Layout mit Inline-Styles und ohne Bilder, weil Mail-Programme externes CSS ignorieren und Bilder oft blocken. Die Mails sehen aus wie die App, also dunkel. Der Text-Teil bleibt erhalten.

**Farben in E-Mails:** Das Template-Tag `{% token "color-primary" %}` (`apps/core/templatetags/mail.py`) liest den Wert beim Rendern aus `tokens.css`. So bleibt die Datei die einzige Stelle mit Farbwerten, und der Farbtest braucht keine Ausnahme. Ein unbekannter Name löst einen Fehler aus.

## Folgen

- Eine spätere Verifizierung der App bei Google verlangt eine öffentliche Seite, die die App beschreibt. Für den aktuellen Betrieb ohne Verifizierung ist sie nicht nötig; bei Bedarf käme eine kleine Info-Seite zurück.
- Dark Mode und Darstellung unterscheiden sich je Mail-Programm. Abgerundete Ecken fehlen zum Beispiel in Outlook für Windows, Inhalt und Button bleiben dort nutzbar.
