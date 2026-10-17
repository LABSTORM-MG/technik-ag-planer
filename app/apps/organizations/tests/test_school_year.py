"""Schuljahreswechsel: Jahrgangsstufen eins hoch, Q2 → Extern, nur einmal je Schuljahr."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Grade
from apps.board.models import Message
from apps.organizations import services
from apps.organizations.models import Membership
from apps.organizations.permissions import Role


def test_promotes_all_grades(org, owner, make_member):
    grades = [value for value, _label in Grade.choices]
    members = {g: make_member(org, grade=g) for g in grades}
    teacher = make_member(org, Role.TEACHER)
    owner.user.grade = ""
    owner.user.save()

    assert services.change_school_year(org) == len(grades) - 1

    expected = dict(zip(grades, [*grades[1:], Grade.EXTERN], strict=True))
    for grade, member in members.items():
        member.user.refresh_from_db()
        assert member.user.grade == expected[grade]
    teacher.user.refresh_from_db()
    assert teacher.user.grade == ""
    assert Message.objects.for_org(org).filter(text__startswith="Schuljahreswechsel").exists()


def test_locked_for_180_days(org, owner, make_member):
    services.change_school_year(org)
    with pytest.raises(ValidationError):
        services.change_school_year(org)
    later = timezone.now() + timedelta(days=181)
    member = make_member(org, grade="7")
    services.change_school_year(org, now=later)
    member.user.refresh_from_db()
    assert member.user.grade == "8"


def test_account_in_two_orgs_promoted_once(org, other_org, owner, make_member):
    member = make_member(org, grade="9")
    Membership.objects.create(organization=other_org, user=member.user, role=Role.STUDENT)

    services.change_school_year(org)
    changes, skipped, _locked = services.school_year_preview(other_org)
    assert member.user in skipped
    services.change_school_year(other_org)

    member.user.refresh_from_db()
    assert member.user.grade == "10"


def test_page_preview_and_trigger(org, owner, make_member, login):
    make_member(org, grade="Q2", display_name="Abi Abgänger")
    client = login(owner.user, org)
    url = reverse("organizations:school_year")
    content = client.get(url).content.decode()
    assert "Q2 → Extern" in content and "Abi Abgänger" in content

    client.post(url, {})  # ohne Häkchen passiert nichts
    org.refresh_from_db()
    assert org.school_year_changed_at is None

    client.post(url, {"confirm": "on"})
    org.refresh_from_db()
    assert org.school_year_changed_at is not None
    assert "Erneut möglich ab" in client.get(url).content.decode()


@pytest.mark.parametrize("role", [Role.ADMIN, Role.TEACHER, Role.STUDENT])
def test_only_owner(org, make_member, login, role):
    client = login(make_member(org, role).user, org)
    url = reverse("organizations:school_year")
    assert client.get(url).status_code == 403
    assert client.post(url, {"confirm": "on"}).status_code == 403
