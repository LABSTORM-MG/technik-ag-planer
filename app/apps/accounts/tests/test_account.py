import pytest
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.organizations.permissions import Role
from conftest import PASSWORD


def _code(device):
    return f"{totp(device.bin_key, step=device.step, digits=device.digits):06d}"


def test_setup_2fa(member_client):
    response = member_client.get(reverse("accounts:two_factor"))
    assert "data:image/svg+xml" in response.content.decode()

    device = TOTPDevice.objects.get(confirmed=False)
    member_client.post(reverse("accounts:two_factor"), {"token": _code(device)})

    device.refresh_from_db()
    assert device.confirmed


def test_setup_2fa_with_wrong_code(member_client):
    member_client.get(reverse("accounts:two_factor"))
    response = member_client.post(reverse("accounts:two_factor"), {"token": "123456"})

    assert "Der Code passt nicht" in response.content.decode()
    assert not TOTPDevice.objects.filter(confirmed=True).exists()


def test_disable_2fa_needs_password(org, make_member, login):
    membership = make_member(org)
    TOTPDevice.objects.create(user=membership.user, name="App", confirmed=True)
    client = login(membership.user, org)

    client.post(reverse("accounts:two_factor_disable"), {"password": "falsch"})
    assert TOTPDevice.objects.exists()

    client.post(reverse("accounts:two_factor_disable"), {"password": PASSWORD})
    assert not TOTPDevice.objects.exists()


def test_org_requiring_2fa_redirects_members_without_device(org, make_member, login):
    org.require_2fa = True
    org.save()
    membership = make_member(org)
    client = login(membership.user, org)

    response = client.get(reverse("core:dashboard"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:two_factor"))
    assert client.get(reverse("accounts:two_factor")).status_code == 200


def test_org_requiring_2fa_blocks_disabling(org, make_member, login):
    org.require_2fa = True
    org.save()
    membership = make_member(org)
    TOTPDevice.objects.create(user=membership.user, name="App", confirmed=True)

    response = login(membership.user, org).post(
        reverse("accounts:two_factor_disable"), {"password": PASSWORD}
    )

    assert response.status_code == 403
    assert TOTPDevice.objects.exists()


def test_owner_toggles_2fa_requirement(org, owner, login):
    login(owner.user, org).post(reverse("organizations:require_2fa"), {"require_2fa": "on"})
    org.refresh_from_db()
    assert org.require_2fa


def test_profile_change_name_and_grade(org, make_member, login):
    membership = make_member(org, Role.STUDENT)
    client = login(membership.user, org)

    client.post(reverse("accounts:profile"), {"display_name": "Spitzname", "grade": "EF"})

    membership.user.refresh_from_db()
    assert membership.user.display_name == "Spitzname"
    assert membership.user.grade == "EF"


def test_profile_hides_grade_for_teachers(org, make_member, login):
    membership = make_member(org, Role.TEACHER)
    response = login(membership.user, org).get(reverse("accounts:profile"))

    assert "grade" not in response.context["form"].fields


@pytest.mark.parametrize("password", ["kurz", "12345678901"])
def test_password_change_validates(member_client, password):
    response = member_client.post(
        reverse("accounts:password_change"),
        {"old_password": PASSWORD, "new_password1": password, "new_password2": password},
    )
    assert response.status_code == 200
    assert response.context["form"].errors


def test_user_without_membership_sees_no_org_page(make_user, login):
    client = login(make_user())

    response = client.get(reverse("core:dashboard"), follow=True)

    assert "Keine AG" in response.content.decode()
    # Konto-Einstellungen bleiben erreichbar
    assert client.get(reverse("accounts:two_factor")).status_code == 200
