# Changelog

Alle wichtigen Änderungen an diesem Projekt. Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach [Semantic Versioning](https://semver.org/lang/de/). Bis zur ersten Version sind die Einträge nach Meilensteinen gegliedert.

## [Unveröffentlicht]

### Hinzugefügt

**Meilenstein 7 – Technik-Anfragen**

- Öffentlicher Link „Technik anfragen“ je AG, ohne Anmeldung nutzbar; in den Einstellungen aktivieren, deaktivieren und neu erzeugen (Owner, Admins)
- Anfrage-Formular in Alltagssprache: Name, E-Mail und Datum Pflicht, sonst Freitext, Art aus den Kategorien der AG, Ankreuzliste für Technik
- Spam-Schutz mit unsichtbarem Feld und Begrenzung pro Stunde je IP und je Link
- Bereich „Anfragen“ mit Zähler oben in der Produktionsliste (Owner, Admins, Lehrkräfte)
- Geteilte Ansicht Anfrage | neue Produktion: Datum und Zeiten werden übernommen (Jobs Aufbau, Veranstaltung, Abbau), alles andere per Kopieren und Einfügen; Umschalter auf dem Handy
- „Erledigt“ archiviert Anfragen; erledigte Anfragen lassen sich wieder öffnen und werden nach 180 Tagen gelöscht

**Meilenstein 6 – Material**

- Materialliste mit Suche, Kategorie-Filter und den Ansichten „Defekt“ und „Archiviert“
- Material mit Kategorie (eigene Material-Kategorien), Bestand oder „beliebig“, Notizen und Links; archivieren statt löschen
- Defekt melden (alle Mitglieder) mit Menge und Beschreibung; Status „defekt“ → „in Reparatur“ → „repariert“; defekte Geräte fehlen im verfügbaren Bestand; Systemmeldungen im Board
- Materialsätze (Owner und Admins): anlegen, bearbeiten, kopieren, löschen; ganzen Satz in eine Produktion übernehmen
- Material in der Produktion einplanen, Menge ändern, entfernen; Konfliktwarnung nach Spitzenbedarf je Tag; Überbuchungen in Produktion und Material markiert („Geplant“)
- Packliste je Produktion zum Abhaken von Ausgabe und Rückgabe
- Beim Kopieren einer Produktion wird das geplante Material übernommen

### Geändert

- Beispielkonten melden sich mit kurzen Namen an (`owner`/`owner`, `lehrer`/`lehrer`, `schueler`/`schueler` …); das Login-Feld nimmt dafür bis M12 auch Namen ohne @ an

**Meilenstein 5 – Board** (#7)

- Board als gemeinsamer Chat der AG: Nachrichten mit farbigem Namen und Uhrzeit, Datumstrenner, eigene Nachrichten rechts; neue Nachrichten erscheinen ohne Neuladen
- Eigene Nachrichten bearbeiten („bearbeitet“) und löschen; Lehrkräfte, Admins und Owner können alle Nachrichten löschen
- Systemmeldungen: neue Produktion, Status, Datum oder Ort geändert, gelöscht und wiederhergestellt, neues Mitglied, „noch X Plätze frei“ 3 Tage vor einem Job
- Chats je Produktion: Leiste mit Kreisen oben im Board, ungelesene zuerst; Button „Chat“ in der Produktion
- Zähler ungelesener Nachrichten in Seitenleiste und „Mehr“
- Jobs mit „Benötigte Personen“ und Anzeige „x von y besetzt“

**Meilenstein 4 – Kalender und Zeiten** (#5)

- Kalender mit Monats-, Wochen- und Agenda-Ansicht, Filter „Alle“/„Meine“, Tagesdetail und „+ Termin an diesem Tag“
- Termine, auch als Serie (wöchentlich, alle 2 Wochen, monatlich) mit Enddatum; einzelne Termine verschieben oder absagen; Leute einteilen oder anfragen
- Stundenraster (Owner); Zeiten bei Jobs, Terminen und „Nicht verfügbar“ wahlweise als Schulstunde
- „Nicht verfügbar“ für alle Mitglieder, sichtbar im Kalender; Konfliktwarnung beim Einteilen zu Jobs und Terminen
- Export einzelner Einträge als `.ics` („In Kalender übernehmen“)

**Meilenstein 3 – Produktionen** (#3, #4)

- Produktionen mit Kategorie, Zeitraum, Status, Ort und Adresse („Navigation starten“), Notizen; Liste mit Suche, Kategorie-Filter und vergangenen Produktionen
- Jobs mit Datum, Zeiten und Treffpunkt; Crew anfragen oder direkt einteilen mit Position, Konfliktwarnung bei Überschneidungen; Anfragen annehmen oder ablehnen
- To-dos je Produktion (alle Mitglieder dürfen anlegen, abhaken und löschen), Lehrkräfte als Aufsicht, Kopieren von Produktionen
- „Kürzlich gelöscht“: 7 Tage wiederherstellbar, danach automatisch entfernt
- Kategorien (Owner, Admins) und Status-Werte (Owner) mit fester Palette aus 12 Farben
- Dashboard „Was steht an?“ mit nächster Produktion, Kacheln und „Meine Jobs“
- Formulare öffnen sich auf dem Handy im Bottom-Sheet; Entwürfe werden im Browser zwischengespeichert

**Meilenstein 2 – Konten und Organisationen** (#2)

- Konten nur auf Einladung: Einladungslinks (einmalig, 7 Tage gültig), Name und Jahrgangsstufe beim Beitritt, erneut senden und zurückziehen
- Anmeldung mit E-Mail und Passwort, Sperre nach 5 Fehlversuchen, „Passwort vergessen“, Abmelden
- Zwei-Faktor-Anmeldung per Authenticator-App (TOTP), auf Wunsch Pflicht für alle Mitglieder einer AG
- AGs mit Rollen Owner, Admin, Lehrkraft, Schüler/in; Rechte-Tabelle als Code, gegen die Feature-Liste getestet
- Mandantentrennung mit Tests; AG wechseln, Mitgliederliste, Rollen ändern, Mitglied entfernen, Ownership übertragen, AG verlassen und auflösen
- Einstellungen in den fünf Gruppen aus Abschnitt 10 mit Rollen-Badge
- Django-Admin für den Betreiber: AG mit Owner-Einladung anlegen, Owner wechseln, Konten sperren, 2FA zurücksetzen, Datenexport als ZIP; im Betrieb nur mit 2FA
- Internes Änderungsprotokoll, Einträge werden nach 7 Tagen gelöscht
- `make beispieldaten` und `make reset-db` für die lokale Entwicklung

**Meilenstein 1 – Grundgerüst** (#1)

- Repository-Grundstruktur, Feature-Liste, Lizenz und Projektregeln
- Django-Projekt (Django 5.2, Python 3.13) mit Settings für Entwicklung, Tests und Betrieb
- Grundlayout: Seitenleiste (Tablet quer, Computer), Leiste unten (Handy, Tablet hochkant), Bottom-Sheets für „+ Neu“ und „Mehr“
- Design-Tokens als CSS-Variablen; ein Test verhindert Farbwerte außerhalb der Tokens
- Docker-Setup für Betrieb (Web, Worker, PostgreSQL, Redis, Caddy mit HTTPS) und Entwicklung (Live-Reload, Mailpit)
- Health-Check `/healthz/`, Celery-Worker mit Beat
- Makefile, CI (Lint, Tests, Sicherheits-Check, Docker-Build) und Release-Workflow (Image nach GHCR)

### Entfernt

- `CONTRIBUTING.md` und `SECURITY.md`: Die Lizenz-Zustimmung steht in der Pull-Request-Vorlage, Sicherheitslücken werden privat über GitHub gemeldet
