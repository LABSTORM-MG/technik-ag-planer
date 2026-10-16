from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.audit.context import acting_as
from apps.audit.models import AuditEntry
from apps.audit.tasks import purge_old_entries
from apps.organizations.permissions import Role


def test_changes_through_views_record_the_actor(org, owner, make_member, login):
    member = make_member(org, Role.STUDENT)
    AuditEntry.objects.all().delete()

    login(owner.user, org).post(
        reverse("organizations:member_role", args=[member.pk]), {"role": Role.ADMIN}
    )

    entry = AuditEntry.objects.get(object_type="Mitgliedschaft")
    assert entry.action == AuditEntry.Action.UPDATE
    assert entry.actor == owner.user
    assert entry.organization == org
    assert entry.changes == {"role": [Role.STUDENT, Role.ADMIN]}


def test_create_and_delete_are_logged(org, make_member):
    member = make_member(org)
    assert AuditEntry.objects.filter(action="create", object_type="Mitgliedschaft").exists()

    member.delete()
    deleted = AuditEntry.objects.get(action="delete", object_type="Mitgliedschaft")
    assert deleted.organization_label == org.name


def test_passwords_never_logged(make_user):
    user = make_user()
    with acting_as(user):
        user.set_password("Noch-ein-Passwort-1")
        user.display_name = "Neu"
        user.save()

    for entry in AuditEntry.objects.all():
        assert "password" not in entry.changes
        assert "pbkdf2" not in str(entry.changes)
        assert "md5" not in str(entry.changes)


def test_dissolving_an_org_keeps_log_entries(org, owner, login):
    login(owner.user, org).post(reverse("organizations:dissolve"), {"confirm_name": org.name})

    entry = AuditEntry.objects.get(action="delete", object_type="AG")
    assert entry.organization is None
    assert entry.organization_label == org.name


def test_purge_removes_entries_older_than_seven_days(org, make_member):
    make_member(org)
    old = AuditEntry.objects.first()
    AuditEntry.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(days=7, minutes=1)
    )
    recent_count = AuditEntry.objects.count() - 1

    purge_old_entries.delay()

    assert not AuditEntry.objects.filter(pk=old.pk).exists()
    assert AuditEntry.objects.count() == recent_count
