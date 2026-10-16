from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from apps.organizations.decorators import org_required

from . import navigation


@org_required
def placeholder(request, section_key):
    """Platzhalterseite für Bereiche, die in späteren Meilensteinen entstehen."""
    section = navigation.BY_KEY[section_key]
    return render(
        request,
        "core/placeholder.html",
        {"section": section, "active_section": section.key},
    )


@login_not_required
@never_cache
def healthz(request):
    """Health-Check für Docker und Caddy: prüft die Datenbankverbindung."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "fehler", "datenbank": False}, status=503)
    return JsonResponse({"status": "ok", "datenbank": True})
