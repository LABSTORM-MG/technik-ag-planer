"""Logik rund um Produktionen: Kopieren, Crew, Konflikte."""

from django.db import transaction
from django.utils import timezone

from .models import CrewAssignment, Job, Production, ProductionStatus, Todo


def overlapping_assignments(membership, job):
    """Andere Jobs, in denen die Person zur selben Zeit eingeteilt oder angefragt ist."""
    return (
        CrewAssignment.objects.for_org(job.organization)
        .filter(
            membership=membership,
            job__date=job.date,
            job__start_time__lt=job.end_time,
            job__end_time__gt=job.start_time,
            job__production__deleted_at__isnull=True,
        )
        .exclude(job=job)
        .select_related("job", "job__production")
    )


def assign(job, membership, *, status, role_label="", requested_by=None):
    """Fragt an oder teilt ein. Bestehender Eintrag wird aktualisiert."""
    assignment, created = CrewAssignment.objects.get_or_create(
        organization=job.organization,
        job=job,
        membership=membership,
        defaults={"status": status, "role_label": role_label, "requested_by": requested_by},
    )
    if not created:
        changed = []
        if assignment.status != status:
            assignment.status = status
            changed.append("status")
        if role_label and assignment.role_label != role_label:
            assignment.role_label = role_label
            changed.append("role_label")
        if changed:
            assignment.save(update_fields=changed)
    return assignment


def respond(assignment, accept: bool):
    """Antwort auf eine Anfrage: annehmen → zugesagt, ablehnen → Eintrag entfällt."""
    if accept:
        assignment.status = CrewAssignment.Status.CONFIRMED
        assignment.save(update_fields=["status"])
    else:
        assignment.delete()


@transaction.atomic
def copy_production(production, user=None):
    """Kopiert Produktion, Jobs und offene To-dos – ohne Crew, Status „In Planung“."""
    jobs = list(production.jobs.all())
    todos = list(production.todos.filter(done=False))
    copy = Production.objects.create(
        organization=production.organization,
        name=f"{production.name} (Kopie)"[:120],
        category=production.category,
        start_date=production.start_date,
        end_date=production.end_date,
        status=ProductionStatus.planning_for(production.organization),
        location_name=production.location_name,
        address=production.address,
        notes=production.notes,
        chat_enabled=production.chat_enabled,
        created_by=user,
    )
    for job in jobs:
        Job.objects.create(
            organization=copy.organization,
            production=copy,
            name=job.name,
            date=job.date,
            start_time=job.start_time,
            end_time=job.end_time,
            meeting_point=job.meeting_point,
            position=job.position,
        )
    for todo in todos:
        Todo.objects.create(
            organization=copy.organization,
            production=copy,
            text=todo.text,
            position=todo.position,
        )
    return copy


def delete_status(status):
    """Löscht einen eigenen Status; betroffene Produktionen fallen auf „In Planung“ zurück."""
    if status.is_system:
        raise ValueError("System-Status können nicht gelöscht werden.")
    planning = ProductionStatus.planning_for(status.organization)
    for production in Production.all_objects.filter(status=status):
        production.status = planning
        production.save(update_fields=["status", "updated_at"])
    status.delete()


def set_todo_done(todo, done, user):
    todo.done = done
    todo.done_by = user if done else None
    todo.done_at = timezone.now() if done else None
    todo.save(update_fields=["done", "done_by", "done_at"])


def move(obj, direction, queryset):
    """Verschiebt ein Objekt in der Reihenfolge nach oben (-1) oder unten (+1)."""
    items = list(queryset)
    for i, item in enumerate(items):
        if item.position != i:
            item.position = i
            item.save(update_fields=["position"])
    index = next(i for i, item in enumerate(items) if item.pk == obj.pk)
    other = index + direction
    if 0 <= other < len(items):
        a, b = items[index], items[other]
        a.position, b.position = b.position, a.position
        a.save(update_fields=["position"])
        b.save(update_fields=["position"])
