from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import Invitation


@shared_task
def purge_invitations(now=None):
    """Löscht Einladungen, die seit INVITATION_KEEP_DAYS abgelaufen, zurückgezogen oder angenommen
    sind – sie enthalten E-Mail-Adressen und werden nicht mehr gebraucht (Abschnitt 11)."""
    cutoff = (now or timezone.now()) - timedelta(days=settings.INVITATION_KEEP_DAYS)
    deleted, _ = Invitation.objects.filter(
        Q(expires_at__lt=cutoff) | Q(revoked_at__lt=cutoff) | Q(accepted_at__lt=cutoff)
    ).delete()
    return deleted
