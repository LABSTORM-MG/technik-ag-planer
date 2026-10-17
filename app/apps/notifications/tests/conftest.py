import pytest

from apps.notifications import push
from apps.notifications.models import PushSubscription


@pytest.fixture
def pushed(monkeypatch, settings):
    """Fängt alle Push-Mitteilungen ab: Liste von (Konto, Payload)."""
    settings.VAPID_PUBLIC_KEY = "public"
    settings.VAPID_PRIVATE_KEY = "private"
    sent = []

    def fake_send(subscription, payload):
        sent.append((subscription.user, payload))
        return push.OK

    monkeypatch.setattr(push, "send", fake_send)
    return sent


@pytest.fixture
def device():
    def factory(membership_or_user, name="1"):
        user = getattr(membership_or_user, "user", membership_or_user)
        return PushSubscription.objects.create(
            user=user,
            endpoint=f"https://push.example.org/{user.pk}/{name}",
            p256dh="p",
            auth="a",
        )

    return factory


def titles(sent, user=None):
    return [p["title"] for u, p in sent if user is None or u == user]
