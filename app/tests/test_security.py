"""Sicherheits-Review (M12): Jede View ist ausdrücklich öffentlich oder geschützt.

Kommt eine neue View hinzu, muss sie hier bewusst eingeordnet werden – sonst schlägt der Test
fehl. AG-Daten brauchen `org_required` bzw. `permission_required_in_org` (Markierung
`checks_organization`).
"""

import re

import pytest
from django.test import Client
from django.urls import URLResolver, get_resolver, reverse

from apps.core.middleware import POLICY

# Ohne Anmeldung erreichbar – jede Zeile ist eine bewusste Entscheidung
PUBLIC = {
    "accounts:login",
    "accounts:login_2fa",
    "accounts:password_reset",
    "accounts:password_reset_done",
    "accounts:password_reset_confirm",
    "accounts:password_reset_complete",
    "organizations:accept_invitation",  # Token in der URL
    "productions:dashboard",  # abgemeldet: Landingpage
    "inquiries:public",  # öffentlicher Anfrage-Link (Token, Spam-Schutz)
    "inquiries:public_thanks",
    "notifications:manifest",
    "notifications:service_worker",
    "core:healthz",
    "core:imprint",
    "core:privacy",
    "core:terms",
}

# Angemeldet, aber ohne AG-Bezug (eigenes Konto, eigene Geräte, Hilfe)
ACCOUNT_LEVEL = {
    "accounts:logout",
    "accounts:profile",
    "accounts:password_change",
    "accounts:two_factor",
    "accounts:two_factor_disable",
    "accounts:delete",
    "organizations:no_organization",
    "organizations:switch",  # prüft die Mitgliedschaft selbst
    "notifications:settings",
    "notifications:subscribe",
    "notifications:unsubscribe",
    "notifications:test",
    "core:help",
    "core:about",
}


def _views():
    def walk(patterns, namespace=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                if p.namespace == "admin":
                    continue
                ns = f"{namespace}{p.namespace}:" if p.namespace else namespace
                yield from walk(p.url_patterns, ns)
            elif p.name:
                yield f"{namespace}{p.name}", p

    return dict(walk(get_resolver().url_patterns))


VIEWS = _views()


def test_every_view_is_classified():
    public = {n for n, p in VIEWS.items() if getattr(p.callback, "login_required", True) is False}
    assert public == PUBLIC, "Öffentliche Views weichen von der Liste ab"
    unchecked = {
        n
        for n, p in VIEWS.items()
        if n not in PUBLIC and not getattr(p.callback, "checks_organization", False)
    }
    assert unchecked == ACCOUNT_LEVEL, "Views ohne AG- und Rechteprüfung"


def _sample_url(name, pattern):
    kwargs = {}
    for key in re.findall(r"<(?:\w+:)?(\w+)>", str(pattern.pattern)):
        kwargs[key] = "x" if key in ("token", "uidb64") else 1
    # feste Zusatzargumente (z. B. as_pdf) stecken im Muster selbst
    return reverse(name, kwargs=kwargs or None)


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(set(VIEWS) - PUBLIC))
def test_anonymous_is_sent_to_login(name):
    response = Client().get(_sample_url(name, VIEWS[name]))
    assert response.status_code == 302, name
    assert response.url.startswith(reverse("accounts:login")), name


@pytest.mark.django_db
def test_content_security_policy(member_client):
    for client, url in [
        (Client(), "/"),
        (member_client, "/"),
        (Client(), reverse("accounts:login")),
    ]:
        assert client.get(url)["Content-Security-Policy"] == POLICY
    assert "script-src 'self'" in POLICY and "unsafe-inline" not in POLICY


@pytest.mark.django_db
def test_admin_has_no_csp():
    assert "Content-Security-Policy" not in Client().get("/admin/login/")


def test_templates_have_no_inline_scripts_or_styles(settings):
    """Voraussetzung für die CSP ohne 'unsafe-inline' (E-Mails ausgenommen)."""
    offenders = []
    for path in (settings.BASE_DIR / "templates").rglob("*.html"):
        if "emails" in path.parts:
            continue
        text = path.read_text()
        if re.search(r"<script(?![^>]*\bsrc=)[^>]*>", text) or re.search(r'\sstyle="', text):
            offenders.append(str(path.relative_to(settings.BASE_DIR)))
        if re.search(r"\son(click|load|submit|change|input)=", text):
            offenders.append(str(path.relative_to(settings.BASE_DIR)))
    assert not offenders, offenders
