#!/bin/sh
# Sicherung der Datenbank (komprimiert) und der .env; alte Sicherungen werden gelöscht.
# Dateien liegen im Google Drive der AGs und müssen hier nicht gesichert werden.
#
#   deploy/backup/backup.sh                       (aus dem Hauptverzeichnis des Repositorys)
#
# Täglich per cron, z. B. um 2:30 Uhr:
#   30 2 * * * cd /opt/technik-ag-planer && deploy/backup/backup.sh >> backups/backup.log 2>&1
#
# Einstellbar: BACKUP_DIR (Standard: backups), BACKUP_KEEP_DAYS (Standard: 14),
#              COMPOSE (Standard: docker compose -f deploy/docker-compose.yml)
set -eu
cd "$(dirname "$0")/../.."

BACKUP_DIR="${BACKUP_DIR:-backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
COMPOSE="${COMPOSE:-docker compose -f deploy/docker-compose.yml}"
STAMP="$(date +%Y-%m-%d_%H%M%S)"

umask 077  # Sicherungen enthalten personenbezogene Daten und Geheimnisse
mkdir -p "$BACKUP_DIR"

DUMP="$BACKUP_DIR/datenbank_$STAMP.dump"
# --format=custom ist bereits komprimiert und lässt sich mit pg_restore einspielen
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" --format=custom "$POSTGRES_DB"' > "$DUMP.tmp"
mv "$DUMP.tmp" "$DUMP"

if [ -f .env ]; then
  cp .env "$BACKUP_DIR/env_$STAMP"
fi

find "$BACKUP_DIR" -maxdepth 1 \( -name 'datenbank_*.dump' -o -name 'env_*' \) \
  -mtime +"$KEEP_DAYS" -delete

echo "Sicherung erstellt: $DUMP ($(du -h "$DUMP" | cut -f1))"
