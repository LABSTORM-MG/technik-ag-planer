from datetime import timedelta

from celery import shared_task
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.productions.models import CrewAssignment, Job

from . import services

OPEN_JOB_DAYS_AHEAD = 3


@shared_task
def announce_open_jobs(today=None):
    """Systemmeldung für Jobs in 3 Tagen, für die noch Personen fehlen (je Job nur einmal)."""
    day = (today or timezone.localdate()) + timedelta(days=OPEN_JOB_DAYS_AHEAD)
    jobs = (
        Job.objects.of_active_productions()
        .filter(date=day, crew_needed__isnull=False)
        .annotate(confirmed=Count("crew", filter=Q(crew__status=CrewAssignment.Status.CONFIRMED)))
        .filter(confirmed__lt=F("crew_needed"))
        .select_related("production", "organization")
    )
    count = 0
    for job in jobs:
        free = job.crew_needed - job.confirmed
        places = "Platz" if free == 1 else "Plätze"
        message = services.post_system(
            job.organization,
            f"{job.name} {job.production.name}: noch {free} {places} frei",
            link_production=job.production,
            key=f"job-open-{job.pk}-{job.date.isoformat()}",
        )
        count += message is not None
    return count
