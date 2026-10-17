"""Geräte, Einstellungen, Manifest/Service Worker und echter Web-Push-Versand (ohne Netz)."""

import base64
import json
import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.core.design import THEME_COLOR
from apps.notifications import push
from apps.notifications.models import Kind, NotificationSettings, PushSubscription
from apps.notifications.services import notify
from apps.notifications.tasks import send_push

from .conftest import titles


def test_manifest_and_service_worker(settings):
    client = Client()
    manifest = client.get(reverse("notifications:manifest"))
    data = json.loads(manifest.content)
    assert manifest["Content-Type"] == "application/manifest+json"
    assert data["display"] == "standalone" and data["start_url"] == "/"
    assert data["theme_color"] == THEME_COLOR == data["background_color"]
    assert {i.get("purpose", "any") for i in data["icons"]} == {"any", "maskable"}
    for icon in data["icons"]:
        path = settings.BASE_DIR / icon["src"].lstrip("/").replace("static/", "static/", 1)
        assert path.exists(), icon["src"]

    sw = client.get("/sw.js")
    assert sw["Content-Type"].startswith("application/javascript")
    assert sw["Service-Worker-Allowed"] == "/"
    assert "showNotification" in sw.content.decode() and "fetch" not in sw.content.decode()


def test_pages_link_manifest_and_icons(member_client):
    for client, url in [(Client(), reverse("accounts:login")), (member_client, "/")]:
        content = client.get(url).content.decode()
        assert reverse("notifications:manifest") in content
        assert "apple-touch-icon" in content


def test_subscribe_and_unsubscribe(org, student, student_client):
    url = reverse("notifications:subscribe")
    body = {"endpoint": "https://push.example.org/abc", "keys": {"p256dh": "p", "auth": "a"}}
    for _ in range(2):  # dasselbe Gerät nur einmal
        response = student_client.post(url, json.dumps(body), content_type="application/json")
        assert response.json() == {"ok": True}
    assert PushSubscription.objects.get().user == student.user

    bad = {"endpoint": "http://unsicher.example.org", "keys": {"p256dh": "p", "auth": "a"}}
    assert (
        student_client.post(url, json.dumps(bad), content_type="application/json").status_code
        == 400
    )

    student_client.post(
        reverse("notifications:unsubscribe"),
        json.dumps({"endpoint": body["endpoint"]}),
        content_type="application/json",
    )
    assert not PushSubscription.objects.exists()


def test_cannot_unsubscribe_others(org, student, planner_client, device):
    subscription = device(student)
    planner_client.post(reverse("notifications:unsubscribe"), {"endpoint": subscription.endpoint})
    assert PushSubscription.objects.exists()


def test_settings_page(org, student, student_client, pushed):
    url = reverse("notifications:settings")
    content = student_client.get(url).content.decode()
    assert "Auf diesem Gerät aktivieren" in content
    assert Kind.INQUIRIES.label not in content  # nur für Owner, Admins, Lehrkräfte

    student_client.post(
        url,
        {"crew": "on", "reminder_mode": "hours", "reminder_time": "18:00", "reminder_hours": "3"},
    )
    s = NotificationSettings.objects.get(user=student.user)
    assert (s.crew, s.board, s.reminder_mode, s.reminder_hours) == (True, False, "hours", 3)


def test_settings_page_without_vapid(student_client, settings):
    settings.VAPID_PUBLIC_KEY = ""
    content = student_client.get(reverse("notifications:settings")).content.decode()
    assert "noch nicht eingerichtet" in content


def test_notify_respects_settings_and_actor(
    org, student, planner, pushed, device, django_capture_on_commit_callbacks
):
    device(student)
    device(planner)
    with django_capture_on_commit_callbacks(execute=True):
        notify(org, [student.user, planner.user], Kind.BOARD, "Hallo", actor=planner.user)
    assert titles(pushed) == ["Hallo"] and pushed[0][0] == student.user

    NotificationSettings.objects.create(user=student.user, board=False)
    with django_capture_on_commit_callbacks(execute=True):
        notify(org, [student.user], Kind.BOARD, "Nochmal", actor=planner.user)
    assert titles(pushed) == ["Hallo"]


def test_gone_devices_are_removed(org, student, device, monkeypatch, settings):
    settings.VAPID_PUBLIC_KEY = settings.VAPID_PRIVATE_KEY = "x"
    device(student)
    monkeypatch.setattr(push, "send", lambda subscription, payload: push.GONE)
    send_push([student.user_id], org.pk, {"title": "x"})
    assert not PushSubscription.objects.exists()


def test_title_names_org_for_members_of_several(org, other_org, student, pushed, device):
    from apps.organizations.models import Membership

    Membership.objects.create(organization=other_org, user=student.user)
    device(student)
    send_push([student.user_id], org.pk, {"title": "Board"})
    assert titles(pushed) == ["Technik-AG Nord: Board"]


def test_test_message(student, student_client, pushed, device):
    device(student)
    student_client.post(reverse("notifications:test"))
    assert titles(pushed) == ["Test-Mitteilung"]


def test_real_webpush_signing_and_encryption(org, student, settings, monkeypatch):
    """Mit echten VAPID-Schlüsseln aus `vapid_schluessel` verschlüsseln und signieren –
    nur der HTTP-Aufruf an den Push-Dienst ist abgefangen."""
    import io

    out = io.StringIO()
    call_command("vapid_schluessel", stdout=out)
    keys = dict(
        line.split("=", 1) for line in out.getvalue().splitlines() if line.startswith("VAPID_")
    )
    settings.VAPID_PUBLIC_KEY = keys["VAPID_PUBLIC_KEY"]
    settings.VAPID_PRIVATE_KEY = keys["VAPID_PRIVATE_KEY"]

    client_key = ec.generate_private_key(ec.SECP256R1())
    p256dh = client_key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    subscription = PushSubscription.objects.create(
        user=student.user,
        endpoint="https://fcm.googleapis.com/fcm/send/abc",
        p256dh=base64.urlsafe_b64encode(p256dh).decode().rstrip("="),
        auth=base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip("="),
    )
    captured = {}

    class Response:
        status_code = 201
        text = ""
        headers = {}  # noqa: RUF012 – Attrappe

    def fake_post(url, data=None, headers=None, timeout=None, **kwargs):
        captured.update(url=url, data=data, headers=headers)
        return Response()

    import requests

    monkeypatch.setattr(requests, "post", fake_post)
    assert push.send(subscription, {"title": "Hallo"}) == push.OK
    assert captured["url"] == subscription.endpoint
    assert captured["headers"]["content-encoding"] == "aes128gcm"
    assert captured["headers"]["authorization"].startswith("vapid t=")
    assert b"Hallo" not in captured["data"]  # verschlüsselt


@pytest.mark.parametrize("name", ["settings", "test"])
def test_login_required(name):
    response = Client().get(reverse(f"notifications:{name}"))
    assert response.status_code == 302
