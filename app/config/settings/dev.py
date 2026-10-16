"""Entwicklung: läuft ohne `.env`, Mails gehen an Mailpit."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "nur-fuer-die-entwicklung-nicht-geheim")

from .base import *  # noqa: E402, F403
from .base import env  # noqa: E402

DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*"])

EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Statische Dateien direkt aus static/ ausliefern, ohne collectstatic
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True
