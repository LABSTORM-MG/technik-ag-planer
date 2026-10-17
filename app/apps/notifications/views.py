import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_POST

from apps.core.design import THEME_COLOR
from apps.organizations.permissions import Perm

from . import push
from .forms import SettingsForm
from .models import NotificationSettings, PushSubscription
from .tasks import send_push


def settings_page(request):
    notification_settings = NotificationSettings.for_user(request.user)
    membership = getattr(request, "membership", None)
    show_inquiries = any(m.has_perm(Perm.HANDLE_INQUIRIES) for m in request.user.memberships.all())
    form = SettingsForm(
        request.POST or None, instance=notification_settings, show_inquiries=show_inquiries
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Gespeichert.")
        return redirect("notifications:settings")
    return render(
        request,
        "notifications/settings.html",
        {
            "active_section": "settings",
            "form": form,
            "enabled": push.is_enabled(),
            "vapid_public_key": settings.VAPID_PUBLIC_KEY,
            "devices": request.user.push_subscriptions.order_by("-created_at"),
            "membership": membership,
        },
    )


@require_POST
def subscribe(request):
    """Gerät anmelden – Body: PushSubscription.toJSON() aus dem Browser."""
    try:
        data = json.loads(request.body)
        endpoint = data["endpoint"]
        keys = data["keys"]
        p256dh, auth = keys["p256dh"], keys["auth"]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"ok": False}, status=400)
    if not endpoint.startswith("https://") or len(endpoint) > 1000:
        return JsonResponse({"ok": False}, status=400)
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh": p256dh[:200],
            "auth": auth[:100],
            "user_agent": request.headers.get("User-Agent", "")[:300],
        },
    )
    return JsonResponse({"ok": True})


@require_POST
def unsubscribe(request):
    try:
        endpoint = json.loads(request.body)["endpoint"]
    except (ValueError, KeyError, TypeError):
        endpoint = request.POST.get("endpoint", "")
    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    if request.headers.get("Content-Type", "").startswith("application/json"):
        return JsonResponse({"ok": True})
    messages.success(request, "Gerät abgemeldet.")
    return redirect("notifications:settings")


@require_POST
def test(request):
    if not request.user.push_subscriptions.exists():
        messages.error(request, "Auf keinem Gerät aktiviert.")
    else:
        send_push.delay(
            [request.user.pk],
            None,
            {
                "title": "Test-Mitteilung",
                "body": "So sehen Push-Mitteilungen der App aus.",
                "url": reverse("notifications:settings"),
                "tag": "test",
            },
        )
        messages.success(request, "Test-Mitteilung verschickt – sie kommt in wenigen Sekunden.")
    return redirect("notifications:settings")


@login_not_required
@cache_control(max_age=3600, public=True)
def manifest(request):
    """Web-App-Manifest: installierbar, ohne Adressleiste (Abschnitt 1)."""
    icon = static("icons/icon-512.png")
    data = {
        "name": "Technik-AG Planer",
        "short_name": "AG Planer",
        "description": "Planung für Technik-AGs an Schulen",
        "lang": "de",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": THEME_COLOR,
        "theme_color": THEME_COLOR,
        "icons": [
            {"src": static("icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": icon, "sizes": "512x512", "type": "image/png"},
            {
                "src": static("icons/icon-maskable-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


@login_not_required
@cache_control(no_cache=True)
def service_worker(request):
    """Service Worker unter /sw.js, damit er für die ganze Seite gilt. Kein Offline-Modus."""
    response = HttpResponse(
        render(request, "notifications/sw.js", {"icon": static("icons/icon-192.png")}).content,
        content_type="application/javascript; charset=utf-8",
    )
    response["Service-Worker-Allowed"] = "/"
    return response
