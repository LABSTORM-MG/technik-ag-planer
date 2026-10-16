"""Gemeinsame Test-Helfer. Auch für spätere Meilensteine gedacht (Mandantentrennung)."""

import itertools

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization
from apps.organizations.permissions import Role

pytest_plugins = ["tests.fixtures_productions"]

_counter = itertools.count(1)
PASSWORD = "Sicheres-Passwort-123"  # noqa: S105 – nur für Tests


@pytest.fixture(autouse=True)
def _clear_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_user(db):
    def factory(email=None, password=PASSWORD, **extra):
        n = next(_counter)
        extra.setdefault("display_name", f"Person {n}")
        return User.objects.create_user(
            email=email or f"person{n}@example.org", password=password, **extra
        )

    return factory


@pytest.fixture
def make_org(db):
    def factory(name=None, **extra):
        return Organization.objects.create(name=name or f"Technik-AG {next(_counter)}", **extra)

    return factory


@pytest.fixture
def make_member(make_user):
    def factory(organization, role=Role.STUDENT, user=None, **user_extra):
        if user is None:
            if role != Role.TEACHER:
                user_extra.setdefault("grade", "9")
            user = make_user(**user_extra)
        return Membership.objects.create(organization=organization, user=user, role=role)

    return factory


@pytest.fixture
def login():
    """Gibt einen angemeldeten Test-Client für ein Konto zurück."""

    def factory(user, organization=None):
        client = Client()
        client.force_login(user)
        if organization is not None:
            session = client.session
            session["active_organization_id"] = organization.pk
            session.save()
        return client

    return factory


@pytest.fixture
def org(make_org):
    return make_org(name="Technik-AG Nord")


@pytest.fixture
def other_org(make_org):
    return make_org(name="Technik-AG Süd")


@pytest.fixture
def owner(org, make_member):
    return make_member(org, Role.OWNER)


@pytest.fixture
def member_client(org, make_member, login):
    """Angemeldete/r Schüler/in der Technik-AG Nord."""
    membership = make_member(org, Role.STUDENT)
    return login(membership.user, org)
