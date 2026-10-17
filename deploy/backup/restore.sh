#!/bin/sh
# Spielt eine Sicherung der Datenbank wieder ein – ALLE aktuellen Daten werden ersetzt.
#
#   deploy/backup/restore.sh backups/datenbank_2026-10-18_023000.dump
#
# Die .env aus der Sicherung (env_…) bei Bedarf vorher von Hand zurückkopieren.
set -eu
cd "$(dirname "$0")/../.."

COMPOSE="${COMPOSE:-docker compose -f deploy/docker-compose.yml}"
DUMP="${1:-}"

if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "Aufruf: deploy/backup/restore.sh <datei.dump>" >&2
  exit 1
fi

if [ "${RESTORE_CONFIRM:-}" != "JA" ]; then
  printf 'Alle aktuellen Daten werden durch %s ersetzt. Zum Fortfahren JA eingeben: ' "$DUMP"
  read -r answer
  [ "$answer" = "JA" ] || { echo "Abgebrochen."; exit 1; }
fi

echo "Stoppe Web und Worker …"
$COMPOSE stop web worker
$COMPOSE exec -T db sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --exit-on-error' \
  < "$DUMP"
echo "Starte Web und Worker (Migrationen laufen beim Start automatisch) …"
$COMPOSE start web worker
echo "Wiederhergestellt aus $DUMP"
