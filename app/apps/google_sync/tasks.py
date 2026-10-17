from celery import shared_task
from django.core.cache import cache

from apps.organizations.models import Organization

from . import calendar_sync
from .models import GoogleConnection

PENDING = "google-sync-pending:{}"


@shared_task
def sync_calendar(organization_id):
    cache.delete(PENDING.format(organization_id))
    organization = Organization.objects.filter(pk=organization_id, is_active=True).first()
    if organization is None:
        return None
    return calendar_sync.sync_calendar(organization)


@shared_task
def sync_all_calendars():
    """Nächtlicher Abgleich – fängt auch Änderungen auf, die kein Signal ausgelöst haben."""
    ids = GoogleConnection.objects.exclude(refresh_token_encrypted="").values_list(
        "organization_id", flat=True
    )
    for organization_id in ids:
        sync_calendar.delay(organization_id)
    return len(ids)
