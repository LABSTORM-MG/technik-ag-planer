from celery import shared_task


@shared_task
def ping():
    """Prüft, ob der Worker Aufgaben annimmt."""
    return "pong"
