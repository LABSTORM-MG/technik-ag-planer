#!/bin/sh
# Beim Start des Web-Containers laufen Datenbank-Migrationen automatisch (Updates laut Abschnitt 14).
set -e

if [ "$1" = "gunicorn" ] && [ "${DJANGO_MIGRATE_ON_START:-true}" = "true" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
