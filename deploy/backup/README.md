# Backups

Skripte für Sicherung und Wiederherstellung folgen in Meilenstein 12. Bis dahin lässt sich die Datenbank so sichern:

```sh
docker compose -f deploy/docker-compose.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup.sql
```
