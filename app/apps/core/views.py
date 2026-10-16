from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from . import navigation


def placeholder(request, section_key):
    """Platzhalterseite für Bereiche, die in späteren Meilensteinen entstehen."""
    section = navigation.BY_KEY[section_key]
    return render(
        request,
        "core/placeholder.html",
        {"section": section, "active_section": section.key},
    )


@never_cache
def healthz(request):
    """Health-Check für Docker und Caddy: prüft die Datenbankverbindung."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "fehler", "datenbank": False}, status=503)
    return JsonResponse({"status": "ok", "datenbank": True})
