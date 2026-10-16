from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Production


@shared_task
def purge_deleted_productions():
    """Entfernt Produktionen endgültig, die seit mehr als 7 Tagen gelöscht sind."""
    cutoff = timezone.now() - timedelta(days=settings.PRODUCTION_TRASH_DAYS)
    count = 0
    for production in Production.all_objects.filter(deleted_at__lt=cutoff):
        production.delete()
        count += 1
    return count
