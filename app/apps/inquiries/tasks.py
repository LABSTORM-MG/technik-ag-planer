from celery import shared_task

from . import services


@shared_task
def purge_done_inquiries():
    """Löscht erledigte Anfragen nach INQUIRY_KEEP_DONE_DAYS endgültig."""
    return services.purge_done()
