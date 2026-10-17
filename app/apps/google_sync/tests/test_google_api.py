"""Die echte Google-Hülle: Fehlerübersetzung, Verschlüsselung, Aufbau der Dienste (ohne Netz)."""

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import Response

from apps.google_sync import crypto
from apps.google_sync.google_api import (
    EXPIRED,
    NOT_CONNECTED,
    QUOTA,
    GoogleApi,
    GoogleError,
    _translate,
)
from apps.google_sync.models import GoogleConnection


def _http_error(status, reason=""):
    return HttpError(Response({"status": status}), reason.encode(), uri="https://x")


def test_translate_errors():
    assert _translate(RefreshError("invalid_grant")).message == EXPIRED
    quota = _translate(
        _http_error(403, '{"error": {"errors": [{"reason": "storageQuotaExceeded"}]}}')
    )
    assert (quota.kind, quota.message) == ("quota", QUOTA)
    assert _translate(_http_error(404)).kind == "not_found"
    assert _translate(_http_error(410)).kind == "not_found"
    assert _translate(_http_error(401)).kind == "expired"
    assert _translate(_http_error(500)).kind == "other"


def test_encryption_roundtrip(settings):
    secret = crypto.encrypt("refresh-123")
    assert secret != "refresh-123" and crypto.decrypt(secret) == "refresh-123"
    settings.SECRET_KEY = "anderer-schluessel"
    assert crypto.decrypt(secret) == ""  # neuer Secret Key → neu verbinden


def test_api_needs_token(org):
    with pytest.raises(GoogleError) as error:
        GoogleApi(GoogleConnection(organization=org))
    assert error.value.message == NOT_CONNECTED


def test_services_build_offline(org, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "secret"  # noqa: S105 – nur Test
    connection = GoogleConnection(organization=org)
    connection.refresh_token = "token"  # noqa: S105 – nur Test
    api = GoogleApi(connection)
    assert api._service("drive", "v3").files()
    assert api._service("calendar", "v3").events()
