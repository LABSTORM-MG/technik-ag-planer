from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache


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
