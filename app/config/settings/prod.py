"""Betrieb hinter Caddy (HTTPS). `DJANGO_SECRET_KEY` ist Pflicht."""

from .base import *  # noqa: F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]
SITE_URL = env("SITE_URL", default=f"https://{ALLOWED_HOSTS[0]}")
# Caddy ersetzt X-Forwarded-For durch die echte Client-Adresse
TRUST_X_FORWARDED_FOR = env.bool("DJANGO_TRUST_X_FORWARDED_FOR", default=True)

# Caddy terminiert TLS und reicht das Protokoll weiter
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# Kein HSTS-Preload: Die Domain gehört evtl. der Schule; Preload ist kaum rückgängig zu machen.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
