from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import AuditEntry


@shared_task
def purge_old_entries():
    """Löscht Protokolleinträge, die älter als AUDIT_RETENTION_DAYS (7 Tage) sind."""
    cutoff = timezone.now() - timedelta(days=settings.AUDIT_RETENTION_DAYS)
    deleted, _ = AuditEntry.objects.filter(created_at__lt=cutoff).delete()
    return deleted
