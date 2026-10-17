"""Push-Mitteilungen auslösen (Abschnitt 9). Nur Push, keine E-Mails."""

from django.db import transaction

from apps.audit.context import get_current_user

from . import push
from .models import NotificationSettings, PushSubscription


def notify(organization, users, kind, title, body="", url="/", *, actor=None, tag=""):
    """Plant eine Mitteilung an `users` (Konten) ein – nach dem Speichern, im Worker.

    Ausgelassen werden: die auslösende Person (`actor`, sonst wer den Request ausgelöst hat),
    Konten, die diese Art abgeschaltet haben, und Konten ohne angemeldetes Gerät.
    """
    if not push.is_enabled():
        return []
    actor = actor or get_current_user()
    ids = {u.pk if hasattr(u, "pk") else u for u in users if u is not None}
    if actor is not None:
        ids.discard(actor.pk)
    ids &= set(PushSubscription.objects.filter(user_id__in=ids).values_list("user_id", flat=True))
    muted = set(
        NotificationSettings.objects.filter(user_id__in=ids, **{kind: False}).values_list(
            "user_id", flat=True
        )
    )
    recipients = sorted(ids - muted)
    if recipients:
        from .tasks import send_push

        payload = {"title": title, "body": body, "url": url, "tag": tag or kind}
        transaction.on_commit(
            lambda: send_push.delay(recipients, organization.pk if organization else None, payload)
        )
    return recipients
