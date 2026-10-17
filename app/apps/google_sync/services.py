"""Verbinden und Trennen des Google-Kontos der AG (Abschnitt 2)."""

import contextlib

from django.db import transaction
from django.utils import timezone

from . import google_api
from .google_api import CALENDAR_SCOPE, DRIVE_SCOPE, GoogleError
from .models import GoogleConnection, SyncedEvent

REQUIRED_SCOPES = {DRIVE_SCOPE: "Google Drive", CALENDAR_SCOPE: "Google Kalender"}


def connection_for(organization):
    """Die aktive Verbindung der AG oder None."""
    connection = GoogleConnection.objects.filter(organization=organization).first()
    return connection if connection and connection.is_connected else None


def api_for(organization):
    """GoogleApi der AG – ohne Verbindung GoogleError „Kein Google-Konto verbunden …“."""
    return google_api.for_connection(connection_for(organization))


def missing_scopes(scopes):
    return [label for scope, label in REQUIRED_SCOPES.items() if scope not in scopes]


@transaction.atomic
def connect(organization, user, *, refresh_token, scopes, email):
    """Speichert die Verbindung. Bei einem anderen Google-Konto als zuvor werden Kalender und
    Ordner neu angelegt (die alten bleiben in jenem Konto)."""
    if not refresh_token:
        raise GoogleError("Google hat keinen dauerhaften Zugang erteilt. Bitte erneut verbinden.")
    missing = missing_scopes(scopes)
    if missing:
        raise GoogleError(
            f"Es fehlt die Zustimmung für: {', '.join(missing)}. Bitte erneut verbinden und "
            "alle Häkchen setzen."
        )
    connection, _ = GoogleConnection.objects.get_or_create(
        organization=organization, defaults={"account_email": email}
    )
    if connection.account_email.lower() != email.lower():
        connection.calendar_id = ""
        connection.root_folder_id = ""
        connection.folder_ids = {}
        SyncedEvent.objects.for_org(organization).delete()
    connection.account_email = email
    connection.refresh_token = refresh_token
    connection.scopes = scopes
    connection.connected_at = timezone.now()
    connection.connected_by = user
    connection.last_error = ""
    connection.save()

    from .tasks import sync_calendar

    transaction.on_commit(lambda: sync_calendar.delay(organization.pk))
    return connection


def disconnect(connection):
    """Widerruft den Zugang. Kalender und Dateien bleiben im Google-Konto (Abschnitte 2, 9)."""
    with contextlib.suppress(GoogleError):
        google_api.for_connection(connection).revoke()
    connection.refresh_token = ""
    connection.save(update_fields=["refresh_token_encrypted"])


def subscribe_url(connection):
    """Link zum Abonnieren in Google Kalender (klappt, sobald der Owner freigegeben hat)."""
    from urllib.parse import quote

    if not connection or not connection.calendar_id:
        return ""
    return f"https://calendar.google.com/calendar/r?cid={quote(connection.calendar_id)}"
