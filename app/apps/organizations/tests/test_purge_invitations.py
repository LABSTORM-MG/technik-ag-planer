"""Erledigte Einladungen werden nach 30 Tagen gelöscht (Datensparsamkeit, Abschnitt 11)."""

from datetime import timedelta

from django.utils import timezone

from apps.organizations import services
from apps.organizations.models import Invitation
from apps.organizations.tasks import purge_invitations


def _invite(org, email, **fields):
    invitation, _token = services.invite(org, email, "student", send=False)
    Invitation.objects.filter(pk=invitation.pk).update(**fields)
    return invitation


def test_purge_old_invitations(org, other_org):
    now = timezone.now()
    old = now - timedelta(days=31)
    young = now - timedelta(days=5)
    expired = _invite(org, "abgelaufen@example.org", expires_at=old)
    revoked = _invite(org, "zurueck@example.org", revoked_at=old)
    accepted = _invite(other_org, "angenommen@example.org", accepted_at=old)
    open_one = _invite(org, "offen@example.org")
    recent = _invite(org, "neu-abgelaufen@example.org", expires_at=young)

    assert purge_invitations() == 3

    remaining = set(Invitation.objects.values_list("pk", flat=True))
    assert remaining == {open_one.pk, recent.pk}
    assert not remaining & {expired.pk, revoked.pk, accepted.pk}
