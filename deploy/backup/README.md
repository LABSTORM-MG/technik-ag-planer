# Backups

- `backup.sh` sichert die Datenbank (`pg_dump`, komprimiert) und die `.env` nach `backups/` und löscht Sicherungen, die älter als 14 Tage sind.
- `restore.sh <datei.dump>` spielt eine Sicherung wieder ein (mit Sicherheitsabfrage).

Anleitung, cron-Eintrag und Hinweise zur Aufbewahrung: [docs/betrieb/README.md](../../docs/betrieb/README.md#backups).
