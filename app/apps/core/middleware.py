"""Content-Security-Policy: Nur eigene Skripte, Styles und Bilder (Sicherheits-Review M12).

Die Templates nutzen keine Inline-Skripte und keine Inline-Styles. Der Django-Admin bleibt
ausgenommen; er bringt eigene Inline-Styles mit.
"""

from django.conf import settings

POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",  # data: für den QR-Code der Zwei-Faktor-Einrichtung
        "font-src 'self'",
        "connect-src 'self'",
        "manifest-src 'self'",
        "worker-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        # „Mit Google verbinden“ ist ein Formular, das zur Google-Anmeldung weiterleitet
        "form-action 'self' https://accounts.google.com",
    ]
)


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_prefix = "/" + settings.ADMIN_URL.lstrip("/")

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith(self.admin_prefix):
            response.headers.setdefault("Content-Security-Policy", POLICY)
        return response
