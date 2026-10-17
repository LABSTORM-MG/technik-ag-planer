# Google-Cloud-Projekt für die Google-Anbindung einrichten

Die App legt hochgeladene Dateien im Google Drive der AG ab und überträgt den Kalender in einen eigenen Google-Kalender (Abschnitte 2 und 9 der Feature-Liste). Dafür braucht **jede Installation** einmalig ein eigenes Google-Cloud-Projekt. Das richtet der Betreiber ein; die Owner der AGs klicken danach nur noch in den Einstellungen auf „Mit Google verbinden“.

Dauer: etwa 15 Minuten. Benötigt wird ein Google-Konto für die Verwaltung des Projekts (z. B. das des Betreibers) – nicht zwingend das Konto einer AG.

## 1. Projekt anlegen

1. [console.cloud.google.com](https://console.cloud.google.com/) öffnen und anmelden.
2. Oben in der Projektauswahl **Neues Projekt** → Name z. B. „Technik-AG Planer“ → **Erstellen**.
3. Sicherstellen, dass das neue Projekt oben ausgewählt ist.

## 2. APIs aktivieren

**APIs & Dienste → Bibliothek**, nacheinander suchen und jeweils **Aktivieren**:

- **Google Drive API**
- **Google Calendar API**

## 3. Zustimmungsbildschirm (Google Auth Platform)

**APIs & Dienste → OAuth-Zustimmungsbildschirm** (heißt je nach Oberfläche auch „Google Auth Platform“). Die Bezeichnungen können sich leicht unterscheiden.

1. **Branding:** App-Name (z. B. „Technik-AG Planer“), Support-E-Mail, unter **Autorisierte Domains** die eigene Domain (z. B. `example.org`). Startseite und Datenschutzerklärung können später ergänzt werden.
2. **Zielgruppe:** Nutzertyp **Extern**.
3. **Datenzugriff → Bereiche hinzufügen** – genau diese vier, keine weiteren:

   | Bereich | Wofür |
   | --- | --- |
   | `openid` | Anmeldung |
   | `.../auth/userinfo.email` | Anzeige des verbundenen Kontos |
   | `.../auth/drive.file` | Nur Dateien, die die App selbst anlegt – kein Zugriff auf das restliche Drive |
   | `.../auth/calendar.app.created` | Nur der Kalender, den die App selbst anlegt – kein Zugriff auf andere Kalender |

4. **Veröffentlichungsstatus auf „In Produktion“ setzen** (Zielgruppe → **App veröffentlichen**). Wichtig: Im Status „Test“ laufen Verbindungen nach 7 Tagen ab.

Eine Überprüfung (Verifizierung) durch Google ist **nicht nötig**. Ohne sie sehen Owner beim Verbinden den Hinweis „Google hat diese App nicht überprüft“ und klicken auf **Erweitert → Weiter zu Technik-AG Planer (unsicher)**. Ohne Verifizierung sind höchstens 100 Google-Konten erlaubt – je AG verbindet sich nur ein Konto, das reicht. Eine Verifizierung kann später jederzeit beantragt werden.

## 4. Zugangsdaten (OAuth-Client) anlegen

**Clients** (bzw. **APIs & Dienste → Anmeldedaten**) → **Client erstellen** → Anwendungstyp **Webanwendung**:

- Name: z. B. „Technik-AG Planer – Server“
- **Autorisierte Weiterleitungs-URIs:** `https://<eure-domain>/einstellungen/google/rueckmeldung/`
  (genau so, mit `https` und Schrägstrich am Ende; `<eure-domain>` wie `SITE_URL` in der `.env`)

Nach **Erstellen** zeigt Google **Client-ID** und **Clientschlüssel**. Beide in die `.env` auf dem Server eintragen:

```sh
GOOGLE_OAUTH_CLIENT_ID=1234567890-abc.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-…
```

Danach die App neu starten:

```sh
docker compose -f deploy/docker-compose.yml up -d
```

Der Clientschlüssel ist ein Geheimnis – nur in der `.env`, nie im Repository.

## 5. Verbinden (durch den Owner einer AG)

1. Das Google-Konto der AG bereithalten – ein **normales Google-Konto** (z. B. `technik-ag.musterschule@gmail.com`), **kein** Schulkonto aus Google Workspace for Education.
2. In der App: **Einstellungen → Google-Konto → Mit Google verbinden**.
3. Mit dem AG-Konto anmelden, den Hinweis „nicht überprüft“ wie oben bestätigen und **beide Häkchen** (Drive und Kalender) setzen.
4. Die App legt im Google-Konto den Kalender „Technik-AG Planer – <AG>“ an und überträgt alle Einträge; Dateien landen im Drive-Ordner „Technik-AG Planer – <AG>“.

**Kalender für Mitglieder freigeben:** In Google Kalender (mit dem AG-Konto) beim Kalender „Technik-AG Planer – <AG>“ → **Einstellungen und Freigabe → Für bestimmte Personen freigeben** → Google-Adressen der Mitglieder mit „Alle Termindetails sehen“ eintragen. Die App zeigt den Mitgliedern dann in der Kalender-Ansicht einen Link zum Abonnieren. Den Kalender bitte **nicht öffentlich** machen – er enthält Namen von Schülerinnen und Schülern.

## Lokal testen (Entwicklung)

Im selben Client zusätzlich die Weiterleitungs-URI `http://localhost:8000/einstellungen/google/rueckmeldung/` eintragen (für `localhost` erlaubt Google `http`). Dann:

```sh
export GOOGLE_OAUTH_CLIENT_ID=…
export GOOGLE_OAUTH_CLIENT_SECRET=…
make dev
```

Der Kalender-Abgleich läuft im `worker`-Container; „Jetzt abgleichen“ in den Einstellungen stößt ihn sofort an.

## Probleme

| Meldung | Ursache und Lösung |
| --- | --- |
| „redirect_uri_mismatch“ bei Google | Die Weiterleitungs-URI im Client stimmt nicht exakt mit `<SITE_URL>/einstellungen/google/rueckmeldung/` überein (https, Domain, Schrägstrich am Ende) |
| „Es fehlt die Zustimmung für: …“ | Beim Verbinden wurde ein Häkchen nicht gesetzt – erneut verbinden |
| „Verbindung zu Google abgelaufen“ | Das Projekt steht noch auf „Test“ (Ablauf nach 7 Tagen), jemand hat den Zugriff im Google-Konto entfernt oder der `DJANGO_SECRET_KEY` wurde geändert – Projekt auf „In Produktion“ stellen und neu verbinden |
| „Google-Drive-Speicher ist voll“ | Speicher des AG-Kontos voll (15 GB kostenlos) – alte Dateien löschen oder Speicher erweitern |
| Termine erscheinen nicht | Läuft der `worker`-Container? `docker compose -f deploy/docker-compose.yml logs worker` |

**Trennen:** Einstellungen → Google-Konto → Trennen. Kalender und Dateien bleiben im Google-Konto erhalten. Wird später dasselbe Konto wieder verbunden, nutzt die App sie weiter.
