"""Mandantentrennung: Eine AG sieht nie Daten einer anderen."""

import pytest
from django.urls import reverse

from apps.organizations import services
from apps.organizations.models import Invitation, Membership
from apps.organizations.permissions import Role


@pytest.fixture
def setup(org, other_org, make_member, login):
    """Owner in Nord, Mitglieder und Einladung in Süd."""
    nord_owner = make_member(org, Role.OWNER, display_name="Nora Nord")
    sued_owner = make_member(other_org, Role.OWNER, display_name="Sam Süd")
    sued_member = make_member(other_org, Role.STUDENT, display_name="Svenja Süd")
    sued_invitation, _ = services.invite(
        other_org, "neu-sued@example.org", Role.STUDENT, send=False
    )
    return {
        "client": login(nord_owner.user, org),
        "sued_owner": sued_owner,
        "sued_member": sued_member,
        "sued_invitation": sued_invitation,
    }


def test_member_list_shows_only_own_organization(setup):
    content = setup["client"].get(reverse("organizations:members")).content.decode()

    assert "Nora Nord" in content
    assert "Sam Süd" not in content
    assert "Svenja Süd" not in content
    assert "neu-sued@example.org" not in content


@pytest.mark.parametrize(
    ("url_name", "target"),
    [
        ("organizations:member_role", "sued_member"),
        ("organizations:member_remove", "sued_member"),
        ("organizations:invitation_resend", "sued_invitation"),
        ("organizations:invitation_revoke", "sued_invitation"),
    ],
)
def test_foreign_ids_return_404(setup, url_name, target):
    obj = setup[target]
    response = setup["client"].post(reverse(url_name, args=[obj.pk]), {"role": Role.ADMIN})

    assert response.status_code == 404
    assert Membership.objects.filter(pk=setup["sued_member"].pk, role=Role.STUDENT).exists()
    assert Invitation.objects.get(pk=setup["sued_invitation"].pk).is_open


def test_switch_only_to_organizations_with_membership(setup, other_org):
    client = setup["client"]
    client.post(reverse("organizations:switch"), {"org": other_org.pk})

    assert client.session["active_organization_id"] != other_org.pk
    content = client.get(reverse("organizations:members")).content.decode()
    assert "Sam Süd" not in content


def test_session_with_foreign_org_falls_back_to_own(org, other_org, make_member, login):
    membership = make_member(org, Role.STUDENT, display_name="Nils Nord")
    make_member(other_org, Role.OWNER, display_name="Sam Süd")
    client = login(membership.user, other_org)  # manipulierte Session

    content = client.get(reverse("organizations:members")).content.decode()

    assert "Nils Nord" in content
    assert "Sam Süd" not in content


def test_switch_between_own_organizations(org, other_org, make_member, login):
    membership = make_member(org, Role.STUDENT)
    make_member(other_org, Role.ADMIN, user=membership.user)
    make_member(other_org, Role.OWNER, display_name="Sam Süd")
    client = login(membership.user, org)

    client.post(reverse("organizations:switch"), {"org": other_org.pk})

    assert client.session["active_organization_id"] == other_org.pk
    assert "Sam Süd" in client.get(reverse("organizations:members")).content.decode()


def test_deactivated_organization_is_not_reachable(org, make_member, login):
    membership = make_member(org, Role.OWNER)
    org.is_active = False
    org.save()

    response = login(membership.user, org).get(reverse("core:dashboard"))

    assert response.status_code == 302
    assert response.url == reverse("organizations:no_organization")


def test_for_org_with_none_returns_nothing(org, make_member):
    make_member(org)
    assert not Membership.objects.for_org(None).exists()
    assert Membership.objects.for_org(org).count() == 1
