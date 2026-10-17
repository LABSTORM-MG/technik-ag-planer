import pytest
from django.core import mail
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from conftest import PASSWORD

PUBLIC_URLS = [
    reverse("productions:dashboard"),  # abgemeldet: Landingpage
    reverse("core:imprint"),
    reverse("accounts:login"),
    reverse("accounts:password_reset"),
    reverse("core:healthz"),
]
PROTECTED_URLS = [
    reverse("productions:list"),
    reverse("scheduling:calendar"),
    reverse("organizations:settings"),
    reverse("organizations:members"),
    reverse("accounts:profile"),
    reverse("accounts:two_factor"),
]


def _code(device):
    return f"{totp(device.bin_key, step=device.step, digits=device.digits):06d}"


@pytest.mark.django_db
@pytest.mark.parametrize("url", PROTECTED_URLS)
def test_protected_pages_redirect_to_login(client, url):
    response = client.get(url)

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


@pytest.mark.django_db
@pytest.mark.parametrize("url", PUBLIC_URLS)
def test_public_pages_are_reachable(client, url):
    assert client.get(url).status_code == 200


def test_login_with_email_and_password(client, owner):
    response = client.post(
        reverse("accounts:login"), {"email": owner.user.email.upper(), "password": PASSWORD}
    )

    assert response.status_code == 302
    assert client.get(reverse("productions:dashboard")).status_code == 200


def test_login_requires_email_address(client, org, make_member, make_user):
    """Seit M12 wieder eine echte E-Mail-Eingabe (vorher kurze Namen für die Beispielkonten)."""
    make_member(org, user=make_user(email="owner", password="owner"))  # noqa: S106
    response = client.post(reverse("accounts:login"), {"email": "owner", "password": "owner"})

    assert response.status_code == 200
    assert 'type="email"' in response.content.decode()


def test_login_respects_safe_next(client, owner):
    response = client.post(
        reverse("accounts:login") + "?next=/kalender/",
        {"email": owner.user.email, "password": PASSWORD, "next": "/kalender/"},
    )
    assert response.url == "/kalender/"


def test_login_ignores_external_next(client, owner):
    response = client.post(
        reverse("accounts:login"),
        {"email": owner.user.email, "password": PASSWORD, "next": "https://evil.example/"},
    )
    assert response.url == reverse("productions:dashboard")


def test_wrong_password_shows_german_error(client, owner):
    response = client.post(
        reverse("accounts:login"), {"email": owner.user.email, "password": "falsch"}
    )

    assert response.status_code == 200
    assert "E-Mail-Adresse oder Passwort ist falsch." in response.content.decode()


def test_login_blocked_after_five_failures(client, owner):
    for _ in range(5):
        client.post(reverse("accounts:login"), {"email": owner.user.email, "password": "falsch"})

    response = client.post(
        reverse("accounts:login"), {"email": owner.user.email, "password": PASSWORD}
    )

    assert "Zu viele Fehlversuche" in response.content.decode()
    assert client.get(reverse("productions:list")).status_code == 302


def test_locked_account_cannot_log_in(client, owner):
    owner.user.is_active = False
    owner.user.save()

    response = client.post(
        reverse("accounts:login"), {"email": owner.user.email, "password": PASSWORD}
    )
    assert response.status_code == 200


def test_logout_requires_post(member_client):
    assert member_client.get(reverse("accounts:logout")).status_code == 405
    member_client.post(reverse("accounts:logout"))
    assert member_client.get(reverse("productions:list")).status_code == 302


def test_login_with_2fa_requires_code(client, owner):
    device = TOTPDevice.objects.create(user=owner.user, name="App", confirmed=True)

    response = client.post(
        reverse("accounts:login"), {"email": owner.user.email, "password": PASSWORD}
    )
    assert response.url == reverse("accounts:login_2fa")
    # ohne Code noch nicht angemeldet
    assert client.get(reverse("productions:list")).status_code == 302

    response = client.post(reverse("accounts:login_2fa"), {"token": "000000"})
    assert "Der Code ist falsch" in response.content.decode()
    device.refresh_from_db()
    device.throttle_reset()  # django-otp bremst nach Fehlversuchen kurz

    response = client.post(reverse("accounts:login_2fa"), {"token": _code(device)})
    assert response.status_code == 302
    assert client.get(reverse("productions:dashboard")).status_code == 200


def test_2fa_step_without_password_step_redirects(client, db):
    assert client.get(reverse("accounts:login_2fa")).url == reverse("accounts:login")


def test_password_reset_sends_german_mail(client, owner):
    client.post(reverse("accounts:password_reset"), {"email": owner.user.email})

    assert len(mail.outbox) == 1
    assert "Neues Passwort" in mail.outbox[0].subject
    assert "/passwort-neu/" in mail.outbox[0].body


def test_password_reset_for_unknown_mail_sends_nothing(client, db):
    response = client.post(reverse("accounts:password_reset"), {"email": "x@example.org"})

    assert response.status_code == 302
    assert len(mail.outbox) == 0


def test_password_reset_full_flow(client, owner):
    client.post(reverse("accounts:password_reset"), {"email": owner.user.email})
    link = next(line for line in mail.outbox[0].body.splitlines() if "/passwort-neu/" in line)
    path = link.split("://", 1)[1].split("/", 1)[1]

    response = client.get("/" + path, follow=True)
    form_url = response.redirect_chain[-1][0]
    client.post(
        form_url, {"new_password1": "Neues-Passwort-987", "new_password2": "Neues-Passwort-987"}
    )

    owner.user.refresh_from_db()
    assert owner.user.check_password("Neues-Passwort-987")
