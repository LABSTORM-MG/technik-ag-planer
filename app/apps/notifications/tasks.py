from datetime import datetime, timedelta

from celery import shared_task
from django.utils import timezone

from apps.organizations.models import Membership, Organization
from apps.productions.models import CrewAssignment
from apps.scheduling.models import EventAttendee

from . import push
from .models import Kind, NotificationSettings, PushSubscription


@shared_task
def send_push(user_ids, organization_id, payload):
    """Verschickt eine Mitteilung an alle Geräte der Konten; abgemeldete Geräte fliegen raus."""
    organization = Organization.objects.filter(pk=organization_id).first()
    multi = set()
    if organization is not None:
        # Wer in mehreren AGs ist, sieht im Titel, um welche AG es geht
        counts = {}
        for user_id in Membership.objects.filter(user_id__in=user_ids).values_list(
            "user_id", flat=True
        ):
            counts[user_id] = counts.get(user_id, 0) + 1
        multi = {u for u, n in counts.items() if n > 1}
    sent = 0
    for subscription in PushSubscription.objects.filter(user_id__in=user_ids):
        data = dict(payload)
        if subscription.user_id in multi:
            data["title"] = f"{organization.name}: {payload['title']}"
        result = push.send(subscription, data)
        if result == push.GONE:
            subscription.delete()
        elif result == push.OK:
            subscription.last_used_at = timezone.now()
            subscription.save(update_fields=["last_used_at"])
            sent += 1
    return sent


def reminder_due(job_start, settings_obj):
    """Zeitpunkt der Erinnerung: am Vorabend um … bzw. … Stunden vor Beginn."""
    if settings_obj.reminder_mode == NotificationSettings.ReminderMode.HOURS:
        return job_start - timedelta(hours=max(1, min(48, settings_obj.reminder_hours)))
    day_before = timezone.localtime(job_start).date() - timedelta(days=1)
    return timezone.make_aware(datetime.combine(day_before, settings_obj.reminder_time))


def _day_label(day, now):
    today = timezone.localtime(now).date()
    if day == today:
        return "Heute"
    if day == today + timedelta(days=1):
        return "Morgen"
    return f"{day:%d.%m.}"


def reminder_text(job, now):
    title = (
        f"{_day_label(job.date, now)} {job.start_time:%H:%M} Uhr: {job.name} {job.production.name}"
    )
    body = f"Treffpunkt: {job.meeting_point}" if job.meeting_point else ""
    return title, body


def event_reminder_text(event, now):
    title = f"{_day_label(event.date, now)} {event.start_time:%H:%M} Uhr: {event.title}"
    body = f"Ort: {event.location}" if event.location else ""
    return title, body


def _remind(item, start, user, now, text, url):
    """Erinnert einmal je Startzeit, sobald der Zeitpunkt laut Einstellungen erreicht ist."""
    from .services import notify

    if start <= now or item.reminded_for == start:
        return False
    if reminder_due(start, NotificationSettings.for_user(user)) > now:
        return False
    title, body = text
    notify(
        item.organization,
        [user],
        Kind.REMINDERS,
        title,
        body,
        url,
        actor=_nobody,
        tag=f"reminder-{item._meta.model_name}-{item.pk}",
    )
    item.reminded_for = start
    item.save(update_fields=["reminded_for"])
    return True


@shared_task
def send_due_reminders(now=None):
    """Alle 10 Minuten: Erinnerungen an eigene zugesagte Jobs und Termine mit Uhrzeit
    (Standard: Vorabend 18 Uhr)."""
    from django.urls import reverse

    now = now or timezone.now()
    today = timezone.localtime(now).date()
    window = (today, today + timedelta(days=3))
    sent = 0
    assignments = CrewAssignment.objects.filter(
        status=CrewAssignment.Status.CONFIRMED,
        membership__isnull=False,
        job__production__deleted_at__isnull=True,
        job__date__range=window,
    ).select_related("job", "job__production", "membership__user", "organization")
    for a in assignments:
        url = reverse("productions:detail", args=[a.job.production_id])
        sent += _remind(
            a, a.job.start_datetime, a.membership.user, now, reminder_text(a.job, now), url
        )
    # Ganztägige Termine haben keine Startzeit und bekommen keine Erinnerung
    attendances = EventAttendee.objects.filter(
        status=EventAttendee.Status.CONFIRMED,
        membership__isnull=False,
        event__cancelled=False,
        event__start_time__isnull=False,
        event__date__range=window,
    ).select_related("event", "membership__user", "organization")
    for a in attendances:
        url = reverse("scheduling:event_detail", args=[a.event_id])
        sent += _remind(
            a,
            a.event.start_datetime,
            a.membership.user,
            now,
            event_reminder_text(a.event, now),
            url,
        )
    return sent


class _Nobody:
    pk = None


_nobody = _Nobody()  # Erinnerungen löst niemand aus – niemand wird ausgelassen
