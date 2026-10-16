# Beiträge

Danke für dein Interesse am Technik-AG Planer!

## Lizenz von Beiträgen

Der Code steht unter der [PolyForm Noncommercial License 1.0.0](LICENSE). Der Projektinhaber kann einzelnen Dritten gesondert eine kommerzielle Nutzung erlauben.

Mit dem Einreichen eines Pull Requests stimmst du zu, dass dein Beitrag

1. unter denselben Bedingungen (PolyForm Noncommercial 1.0.0) genutzt werden darf und
2. vom Projektinhaber zusätzlich gesondert lizenziert werden darf, auch für kommerzielle Nutzung durch Dritte.

Pull Requests ohne diese Zustimmung können nicht angenommen werden. Bitte bestätige sie in der PR-Vorlage.

## Branches

- `main` ist immer lauffähig.
- Neue Arbeit auf eigenem Branch, z. B. `feature/kalender`, `fix/login-weiterleitung`, `docs/installation`.
- Übernahme in `main` nur über Pull Request mit grüner CI.

## Commits

- Kurze, aussagekräftige Betreffzeile im Imperativ, z. B. „Einladungslink nach 7 Tagen ablaufen lassen“.
- Ein Commit pro zusammenhängender Änderung.

## Qualität

- Jede neue Funktion bekommt Tests.
- `make test` und `make lint` müssen grün sein.
- Mandantentrennung und Rechteprüfung beachten (siehe [CLAUDE.md](CLAUDE.md)).

## Sicherheitslücken

Bitte nicht als öffentliches Issue melden – siehe [SECURITY.md](SECURITY.md).
