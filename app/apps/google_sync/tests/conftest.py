import pytest

from apps.google_sync import google_api
from apps.google_sync.models import GoogleConnection
from apps.inventory.tests.conftest import make_material  # noqa: F401 – auch hier gebraucht

from .fake_google import FakeGoogle, factory


@pytest.fixture
def google(monkeypatch, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "client-id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "client-secret"  # noqa: S105 – nur Test
    fake = FakeGoogle()
    monkeypatch.setattr(google_api, "for_connection", factory(fake))
    return fake


@pytest.fixture
def connected(org, owner, google):
    connection = GoogleConnection(
        organization=org,
        account_email="technik-ag@gmail.com",
        scopes=list(google_api.SCOPES),
        connected_by=owner.user,
    )
    connection.refresh_token = "geheimer-refresh-token"  # noqa: S105 – nur Test
    connection.save()
    return connection
