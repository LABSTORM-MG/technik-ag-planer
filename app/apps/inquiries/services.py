"""Technik-Anfragen: Link verwalten, Spam-Schutz, Übernahme in eine Produktion."""

from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.throttle import client_ip

from .models import Inquiry, InquiryLink

HOUR = 60 * 60


def link_for(organization):
    """Anfrage-Link der AG (wird beim ersten Aufruf angelegt, zunächst nicht aktiv)."""
    link, _ = InquiryLink.objects.get_or_create(organization=organization)
    return link


def active_link(token):
    """Aktiver Link zu einem Token – oder None (unbekannt, nicht aktiv, AG deaktiviert)."""
    return (
        InquiryLink.objects.filter(token=token, is_active=True, organization__is_active=True)
        .select_related("organization")
        .first()
    )


# ---------- Spam-Schutz: Anfragen pro Stunde je IP und je Link ----------


def _keys(link, request):
    return (
        (f"anfrage:ip:{client_ip(request)}", settings.INQUIRY_MAX_PER_IP_HOUR),
        (f"anfrage:link:{link.pk}", settings.INQUIRY_MAX_PER_LINK_HOUR),
    )


def is_limited(link, request):
    return any(cache.get(key, 0) >= limit for key, limit in _keys(link, request))


def count_submission(link, request):
    for key, _limit in _keys(link, request):
        cache.add(key, 0, timeout=HOUR)
        try:
            cache.incr(key)
        except ValueError:  # gerade abgelaufen
            cache.set(key, 1, timeout=HOUR)


# ---------- Übernahme in eine Produktion ----------


def production_initial(inquiry):
    """Datum wird automatisch übernommen; alles andere per Kopieren und Einfügen."""
    return {"start_date": inquiry.date, "end_date": inquiry.date, "category": inquiry.category_id}


def suggested_jobs(inquiry):
    """Jobs aus den Zeiten der Anfrage – nur, wenn die nötigen Zeiten angegeben sind."""
    jobs = []

    def add(name, start, end):
        if start and end and end > start:
            jobs.append({"name": name, "date": inquiry.date, "start_time": start, "end_time": end})

    add("Aufbau", inquiry.setup_from, inquiry.start_time)
    add("Veranstaltung", inquiry.start_time, inquiry.end_time)
    add("Abbau", inquiry.end_time, inquiry.teardown_until)
    return jobs


# ---------- Erledigt ----------


def mark_done(inquiry, user):
    inquiry.done_at = timezone.now()
    inquiry.done_by = user
    inquiry.save(update_fields=["done_at", "done_by"])


def reopen(inquiry):
    inquiry.done_at = None
    inquiry.done_by = None
    inquiry.save(update_fields=["done_at", "done_by"])


def purge_cutoff(now=None):
    return (now or timezone.now()) - timedelta(days=settings.INQUIRY_KEEP_DONE_DAYS)


def purge_done(now=None):
    """Löscht erledigte Anfragen endgültig (Datensparsamkeit: Daten von Personen ohne Konto)."""
    deleted, _ = Inquiry.objects.filter(done_at__lt=purge_cutoff(now)).delete()
    return deleted
