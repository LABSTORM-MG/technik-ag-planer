from datetime import datetime, timedelta

from celery import shared_task
from django.utils import timezone

from apps.organizations.models import Membership, Organization
from apps.productions.models import CrewAssignment

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


def reminder_text(job, now):
    today = timezone.localtime(now).date()
    day = (
        "Heute"
        if job.date == today
        else "Morgen"
        if job.date == today + timedelta(1)
        else (f"{job.date:%d.%m.}")
    )
    title = f"{day} {job.start_time:%H:%M} Uhr: {job.name} {job.production.name}"
    body = f"Treffpunkt: {job.meeting_point}" if job.meeting_point else ""
    return title, body


@shared_task
def send_due_reminders(now=None):
    """Alle 10 Minuten: Erinnerungen an eigene zugesagte Jobs (Standard: Vorabend 18 Uhr)."""
    from django.urls import reverse

    from .services import notify

    now = now or timezone.now()
    today = timezone.localtime(now).date()
    assignments = CrewAssignment.objects.filter(
        status=CrewAssignment.Status.CONFIRMED,
        membership__isnull=False,
        job__production__deleted_at__isnull=True,
        job__date__range=(today, today + timedelta(days=3)),
    ).select_related("job", "job__production", "membership__user", "organization")
    sent = 0
    for a in assignments:
        start = a.job.start_datetime
        if start <= now or a.reminded_for == start:
            continue
        settings_obj = NotificationSettings.for_user(a.membership.user)
        if reminder_due(start, settings_obj) > now:
            continue
        title, body = reminder_text(a.job, now)
        url = reverse("productions:detail", args=[a.job.production_id])
        notify(
            a.organization,
            [a.membership.user],
            Kind.REMINDERS,
            title,
            body,
            url,
            actor=_nobody,
            tag=f"reminder-{a.pk}",
        )
        a.reminded_for = start
        a.save(update_fields=["reminded_for"])
        sent += 1
    return sent


class _Nobody:
    pk = None


_nobody = _Nobody()  # Erinnerungen löst niemand aus – niemand wird ausgelassen
