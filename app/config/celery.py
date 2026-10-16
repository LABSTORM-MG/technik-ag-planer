"""Hintergrund-Tasks (Celery) – Erinnerungen, Kalender-Abgleich, Aufräumjobs."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("technik_ag_planer")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
