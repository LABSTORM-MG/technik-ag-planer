"""Nach Änderungen an Kalendereinträgen einen Abgleich einplanen (gesammelt, siehe ADR 0012)."""

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save

from apps.productions.models import Category, CrewAssignment, Job, Production, ProductionStatus
from apps.scheduling.models import Event, Unavailability

from .models import GoogleConnection

WATCHED = [Production, Job, CrewAssignment, Event, Unavailability, Category, ProductionStatus]


def schedule_sync(organization_id):
    if (
        not GoogleConnection.objects.filter(organization_id=organization_id)
        .exclude(refresh_token_encrypted="")
        .exists()
    ):
        return
    from .tasks import PENDING, sync_calendar

    delay = settings.GOOGLE_SYNC_DELAY_SECONDS
    if cache.add(PENDING.format(organization_id), 1, timeout=delay * 4):
        transaction.on_commit(
            lambda: sync_calendar.apply_async(args=[organization_id], countdown=delay)
        )


def _changed(sender, instance, raw=False, **kwargs):
    if not raw and instance.organization_id:
        schedule_sync(instance.organization_id)


for model in WATCHED:
    uid = f"google-sync-{model._meta.label}"
    post_save.connect(_changed, sender=model, dispatch_uid=f"{uid}-save")
    post_delete.connect(_changed, sender=model, dispatch_uid=f"{uid}-delete")
