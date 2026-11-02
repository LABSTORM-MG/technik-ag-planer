import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Production

logger = logging.getLogger(__name__)


@shared_task
def purge_deleted_productions():
    """Entfernt Produktionen endgültig, die seit mehr als 7 Tagen gelöscht sind."""
    cutoff = timezone.now() - timedelta(days=settings.PRODUCTION_TRASH_DAYS)
    count = 0
    from apps.google_sync import drive
    from apps.inventory.unit_services import has_outstanding_material

    for production in Production.all_objects.filter(deleted_at__lt=cutoff):
        # Ausgegebenes Material bliebe sonst ohne Rückgabeweg; die anderen laufen trotzdem weiter
        if has_outstanding_material(production):
            logger.warning("Produktion %s bleibt: Material ist noch ausgegeben", production.pk)
            continue
        drive.delete_all(production.attachments.all())  # Abschnitt 2: auch im Drive löschen
        drive.trash_production_folder(production)
        production.delete()
        count += 1
    return count
