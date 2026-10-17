"""Google-Anmeldung (OAuth 2.0, Authorization Code mit PKCE)."""

import os

from django.conf import settings
from django.urls import reverse

from .google_api import SCOPES, TOKEN_URI, GoogleError

# Google meldet bei teilweiser Zustimmung andere Scopes zurück – das prüfen wir selbst
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

SESSION_KEY = "google_oauth"


def redirect_uri():
    return settings.SITE_URL.rstrip("/") + reverse("google_sync:callback")


def _flow(**kwargs):
    from google_auth_oauthlib.flow import Flow

    config = {
        "web": {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": TOKEN_URI,
        }
    }
    return Flow.from_client_config(config, scopes=SCOPES, redirect_uri=redirect_uri(), **kwargs)


def authorization_url(request):
    """Adresse der Google-Anmeldung; `state` und PKCE-Verifier landen in der Session."""
    flow = _flow(autogenerate_code_verifier=True)
    url, state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="false"
    )
    request.session[SESSION_KEY] = {
        "state": state,
        "verifier": flow.code_verifier,
        "organization": request.organization.pk,
    }
    return url


def exchange_code(code, verifier):
    """Tauscht den Code gegen Tokens. Gibt {refresh_token, scopes, email} zurück."""
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    flow = _flow(code_verifier=verifier)
    try:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        info = id_token.verify_oauth2_token(
            credentials.id_token, Request(), settings.GOOGLE_OAUTH_CLIENT_ID
        )
    except Exception as error:  # noqa: BLE001 – jede Störung als verständlicher Fehler
        raise GoogleError(
            "Die Anmeldung bei Google hat nicht geklappt. Bitte erneut versuchen."
        ) from error
    return {
        "refresh_token": credentials.refresh_token or "",
        "scopes": sorted(credentials.granted_scopes or credentials.scopes or []),
        "email": info.get("email", ""),
    }
