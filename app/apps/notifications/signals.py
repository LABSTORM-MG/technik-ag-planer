"""Auslöser für Push-Mitteilungen (Abschnitte 5, 6, 8, 9) – über Signale, damit die Fach-Apps
die Benachrichtigungen nicht kennen müssen."""

from django.db.models import Q
from django.db.models.signals import post_save, pre_delete, pre_save
from django.urls import reverse
from django.utils.formats import date_format

from apps.board.models import Message
from apps.inquiries.models import Inquiry
from apps.organizations.models import Membership
from apps.organizations.permissions import Perm
from apps.productions.models import CrewAssignment, Job, Production
from apps.scheduling.models import EventAttendee

from .models import Kind
from .services import notify

JOB_FIELDS = ("date", "start_time", "end_time", "meeting_point")
PRODUCTION_FIELDS = ("start_date", "end_date", "location_name", "status_id", "deleted_at")


def _when(job):
    return f"{date_format(job.date, 'D., d.m.')} {job.start_time:%H:%M}–{job.end_time:%H:%M} Uhr"


def _crew_users(jobs):
    return [
        a.membership.user
        for a in CrewAssignment.objects.filter(job__in=jobs, membership__isnull=False)
        .select_related("membership__user")
        .distinct()
    ]


def _detail(production):
    return reverse("productions:detail", args=[production.pk])


# ---------- Crew-Anfragen und Einteilungen ----------


def crew_added(sender, instance, created, raw=False, **kwargs):
    if raw or not created or instance.membership_id is None:
        return
    job = instance.job
    if instance.is_confirmed:
        title = f"Du bist eingeteilt: {job.name} {job.production.name}"
        url = _detail(job.production)
    else:
        title = f"Neue Crew-Anfrage: {job.name} {job.production.name}"
        url = reverse("productions:dashboard") + "?ansicht=jobs"
    body = _when(job) + (f" · {instance.role_label}" if instance.role_label else "")
    notify(
        instance.organization,
        [instance.membership.user],
        Kind.CREW,
        title,
        body,
        url,
        actor=instance.requested_by,
    )


def attendee_added(sender, instance, created, raw=False, **kwargs):
    if raw or not created or instance.membership_id is None:
        return
    event = instance.event
    verb = "Du bist eingeteilt" if instance.is_confirmed else "Neue Anfrage"
    when = date_format(event.date, "D., d.m.")
    if event.start_time:
        when += f" {event.start_time:%H:%M} Uhr"
    notify(
        instance.organization,
        [instance.membership.user],
        Kind.CREW,
        f"{verb}: {event.title}",
        when,
        reverse("scheduling:event_detail", args=[event.pk]),
    )


# ---------- Änderungen an eigenen Jobs ----------


def remember_job(sender, instance, raw=False, **kwargs):
    instance._push_old = None
    if not raw and instance.pk:
        instance._push_old = sender.objects.filter(pk=instance.pk).values(*JOB_FIELDS).first()


def job_changed(sender, instance, created, raw=False, **kwargs):
    old = getattr(instance, "_push_old", None)
    if raw or created or not old:
        return
    if all(old[f] == getattr(instance, f) for f in JOB_FIELDS):
        return
    body = _when(instance)
    if instance.meeting_point:
        body += f" · Treffpunkt: {instance.meeting_point}"
    notify(
        instance.organization,
        _crew_users([instance]),
        Kind.CHANGES,
        f"Geändert: {instance.name} {instance.production.name}",
        body,
        _detail(instance.production),
    )


def job_deleted(sender, instance, **kwargs):
    # pre_delete: die Crew ist danach schon weg
    production = Production.all_objects.filter(pk=instance.production_id).first()
    if production is None or production.deleted_at is not None:
        return
    notify(
        instance.organization,
        _crew_users([instance]),
        Kind.CHANGES,
        f"Abgesagt: {instance.name} {production.name}",
        _when(instance),
        _detail(production),
    )


def remember_production(sender, instance, raw=False, **kwargs):
    instance._push_old = None
    if not raw and instance.pk:
        instance._push_old = (
            sender.all_objects.filter(pk=instance.pk).values(*PRODUCTION_FIELDS).first()
        )


def production_changed(sender, instance, created, raw=False, **kwargs):
    old = getattr(instance, "_push_old", None)
    if raw or created or not old:
        return
    changes = []
    if old["deleted_at"] is None and instance.deleted_at is not None:
        title, url = f"Produktion gelöscht: {instance.name}", reverse("productions:dashboard")
    elif instance.deleted_at is not None:
        return
    else:
        if (old["start_date"], old["end_date"]) != (instance.start_date, instance.end_date):
            changes.append("neues Datum " + date_format(instance.start_date, "D., d.m.Y"))
        if old["location_name"] != instance.location_name:
            changes.append(f"neuer Ort {instance.location_name or '–'}")
        if old["status_id"] != instance.status_id:
            changes.append(f"Status {instance.status}")
        if not changes:
            return
        title, url = f"Geändert: {instance.name}", _detail(instance)
    notify(
        instance.organization,
        _crew_users(Job.objects.filter(production=instance)),
        Kind.CHANGES,
        title,
        ", ".join(changes),
        url,
    )


# ---------- Technik-Anfragen, Board und Chats ----------


def inquiry_received(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return
    roles = Perm.HANDLE_INQUIRIES.roles
    users = [
        m.user
        for m in Membership.objects.for_org(instance.organization)
        .filter(role__in=roles)
        .select_related("user")
    ]
    notify(
        instance.organization,
        users,
        Kind.INQUIRIES,
        f"Neue Technik-Anfrage: {instance.event_name or 'ohne Titel'}",
        f"{date_format(instance.date, 'D., d.m.Y')} · von {instance.requester_name}",
        reverse("inquiries:detail", args=[instance.pk]),
    )


def message_posted(sender, instance, created, raw=False, **kwargs):
    if raw or not created or instance.is_system:
        return
    org = instance.organization
    members = Membership.objects.for_org(org).select_related("user")
    production = instance.production
    if production is None:
        kind, title, url = Kind.BOARD, "Board", reverse("board:index")
    else:
        if not production.chat_enabled or production.deleted_at is not None:
            return
        # Wie im Navigations-Zähler: eingeteilt oder Aufsicht (ADR 0007)
        members = members.filter(
            Q(assignments__job__production=production) | Q(pk__in=production.supervisors.all())
        ).distinct()
        kind, title = Kind.CHATS, f"Chat: {production.name}"
        url = reverse("board:production", args=[production.pk])
    text = instance.text if len(instance.text) <= 140 else instance.text[:139] + "…"
    notify(
        org,
        [m.user for m in members],
        kind,
        title,
        f"{instance.author_name}: {text}",
        url,
        actor=instance.author,
        tag=f"chat-{production.pk if production else 'board'}",
    )


def connect():
    uid = "push"
    post_save.connect(crew_added, sender=CrewAssignment, dispatch_uid=f"{uid}-crew")
    post_save.connect(attendee_added, sender=EventAttendee, dispatch_uid=f"{uid}-attendee")
    pre_save.connect(remember_job, sender=Job, dispatch_uid=f"{uid}-job-pre")
    post_save.connect(job_changed, sender=Job, dispatch_uid=f"{uid}-job")
    pre_delete.connect(job_deleted, sender=Job, dispatch_uid=f"{uid}-job-delete")
    pre_save.connect(remember_production, sender=Production, dispatch_uid=f"{uid}-prod-pre")
    post_save.connect(production_changed, sender=Production, dispatch_uid=f"{uid}-prod")
    post_save.connect(inquiry_received, sender=Inquiry, dispatch_uid=f"{uid}-inquiry")
    post_save.connect(message_posted, sender=Message, dispatch_uid=f"{uid}-message")
