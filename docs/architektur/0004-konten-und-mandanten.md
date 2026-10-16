# ADR 0004: Konten, Mandantentrennung und Rechte

- **Status:** angenommen
- **Datum:** 2026-10-16

## Kontext

Meilenstein 2 legt das Fundament: Konten nur auf Einladung, mehrere AGs je Konto, vier Rollen mit festen Rechten (Abschnitt 2) und strikte Trennung der Daten je AG (Abschnitt 11). Alle späteren Meilensteine bauen darauf auf.

## Entscheidungen

**Eigenes Benutzermodell** (`apps.accounts.User`): Login per E-Mail, frei wählbarer Name, Jahrgangsstufe am Konto. Die Rolle hängt dagegen an der Mitgliedschaft, weil sie je AG verschieden sein kann.

**Mandanten über Session und Middleware:**

- `OrganizationMiddleware` setzt `request.organization` und `request.membership` aus der aktiven AG in der Session.
- Eine ungültige AG in der Session (z. B. nach Austritt oder Manipulation) wird verworfen.
- Alle AG-Daten erben von `OrganizationScopedModel`; Abfragen laufen über `Model.objects.for_org(request.organization)`.
- Einzelne Objekte werden mit `get_object_or_404(Model.objects.for_org(...), pk=...)` geholt. Fremde IDs ergeben damit 404.

**Rechte-Tabelle als Code** (`apps/organizations/permissions.py`):

- Jede Zeile der Tabelle ist ein `Perm` mit den erlaubten Rollen.
- In Views prüft `@permission_required_in_org(Perm.X)`, in Templates `org_perms.X`.
- Ein Test liest die Tabelle aus `docs/feature-liste.md` und vergleicht sie mit dem Code. Ändert sich die Spezifikation, schlägt der Test fehl, bis der Code angepasst ist.

**2FA mit `django-otp`** (TOTP): bewährte Prüf- und Bremslogik, eigene deutsche Oberfläche. Der QR-Code entsteht lokal mit `qrcode`, ohne externen Dienst. Es gibt keine Wiederherstellungscodes: Der Betreiber setzt die 2FA bei Verlust im Admin zurück.

**Login-Pflicht über Djangos `LoginRequiredMiddleware`**: Jede Seite verlangt die Anmeldung, Ausnahmen werden ausdrücklich mit `@login_not_required` markiert. Das sind Anmeldung, Passwort vergessen, Einladung und Health-Check.

**Eigenes, schlankes Änderungsprotokoll** (`apps.audit`) statt einer Bibliothek:

- Modelle melden sich mit `register(Model)` an; Signale schreiben die Einträge.
- Der Auslöser kommt per `contextvars` aus dem Request.
- Felder mit `password`, `token`, `secret` oder `key` im Namen werden nie gespeichert.
- Ein Celery-Task löscht Einträge nach 7 Tagen.

## Folgen für spätere Meilensteine

- Neue AG-Daten: von `OrganizationScopedModel` erben, `audit.register(...)` und `export.register(...)` in `apps.py` aufrufen.
- Jede neue View braucht eine Rechteprüfung und Tests, dass Daten anderer AGs nicht erreichbar sind (Fixtures `org`, `other_org`, `make_member`, `login` in `app/conftest.py`).
