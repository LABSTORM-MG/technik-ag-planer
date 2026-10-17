# Dokumentation

| Dokument | Inhalt |
| --- | --- |
| [feature-liste.md](feature-liste.md) | Verbindliche Spezifikation (Abschnitte 1–15) und Umsetzungsstand mit allen Entscheidungen (Abschnitt 16) |
| [architektur/](architektur/) | Architektur-Entscheidungen (ADRs), siehe unten |
| [installation/](installation/README.md) | Server einrichten, `.env`, Start, Updates |
| [betrieb/django-admin.md](betrieb/django-admin.md) | Django-Admin für den Betreiber: AGs und Owner anlegen, Konten, Datenexport, Protokoll |
| [handbuch/](handbuch/README.md) | Anleitungen für Owner und Mitglieder – folgt in Meilenstein 12 |
| [rechtliches/](rechtliches/README.md) | Datenschutzerklärung, Nutzungsbedingungen, Impressum – vor dem Start |

## Architektur-Entscheidungen

| Nr. | Titel |
| --- | --- |
| [0001](architektur/0001-repository-struktur.md) | Monorepo-Struktur |
| [0002](architektur/0002-stack.md) | Technischer Stack (Django, uv, Celery, kein JS-Build) |
| [0003](architektur/0003-core-app.md) | App `core` für Grundlayout |
| [0004](architektur/0004-konten-und-mandanten.md) | Konten, Mandantentrennung und Rechte |
| [0005](architektur/0005-produktionen.md) | Produktionen – Farben, Status, Löschen, Formulare |
| [0006](architektur/0006-kalender-und-zeiten.md) | Kalender, Serien, Schulstunden und ICS |
| [0007](architektur/0007-board.md) | Board, Produktions-Chats und Systemmeldungen |

Neue Entscheidungen bekommen die nächste Nummer und einen Eintrag in Abschnitt 16 der Feature-Liste.
