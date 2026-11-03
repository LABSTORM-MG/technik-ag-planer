"""Gestaltete E-Mails: Einladung und „Passwort vergessen“ (ADR 0026)."""

import re
from urllib.parse import urlsplit

import pytest
from django.core import mail
from django.template import Context, Template
from django.urls import reverse

from apps.core.templatetags.mail import _tokens
from apps.organizations import services
from apps.organizations.permissions import Role


def _html(message):
    return next(body for body, kind in message.alternatives if kind == "text/html")


def _invite(org, owner, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        services.invite(org, "emma@example.org", Role.TEACHER, invited_by=owner.user)
    return mail.outbox[-1]


def _assert_styled(html):
    assert "var(" not in html  # Mail-Programme kennen keine CSS-Variablen
    assert "border:" not in html  # Gmail hellt Rahmen im Dunkelmodus auf (ADR 0026)
    for name in ["color-bg", "color-surface", "color-primary", "color-on-primary", "color-accent"]:
        assert _tokens()[name] in html
    # Fußzeile mit absoluten Links
    assert re.search(r'href="https?://[^"]+/impressum/"', html)
    assert re.search(r'href="https?://[^"]+/datenschutz/"', html)


def test_invitation_mail_is_styled(org, owner, django_capture_on_commit_callbacks):
    message = _invite(org, owner, django_capture_on_commit_callbacks)
    html = _html(message)
    link = next(line for line in message.body.splitlines() if "/einladung/" in line)

    _assert_styled(html)
    assert f'<a href="{link}"' in html
    assert "Einladung annehmen" in html
    assert Role.TEACHER.label in html and Role.TEACHER.label in message.body
    assert str(owner.user) in html and org.name in html


def test_invitation_mail_escapes_names(org, owner, django_capture_on_commit_callbacks):
    org.name = "<b>Technik</b>"
    org.save()

    message = _invite(org, owner, django_capture_on_commit_callbacks)

    assert "<b>Technik</b>" not in _html(message)
    assert "&lt;b&gt;Technik&lt;/b&gt;" in _html(message)
    assert "<b>Technik</b>" in message.body  # Text-Teil ist unmaskiert


def test_password_reset_mail_is_styled(client, owner):
    client.post(reverse("accounts:password_reset"), {"email": owner.user.email})

    message = mail.outbox[-1]
    html = _html(message)
    link = next(line for line in message.body.splitlines() if "/passwort-neu/" in line)

    _assert_styled(html)
    assert f'<a href="{link}"' in html
    assert str(owner.user) in html
    # Der Link aus der Mail funktioniert: Django leitet zum Formular weiter
    assert client.get(urlsplit(link).path).status_code == 302


def test_unknown_token_fails_loudly():
    template = Template('{% load mail %}{% token "gibt-es-nicht" %}')
    with pytest.raises(KeyError):
        template.render(Context())
