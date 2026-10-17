"""Systemmeldungen im Board (Abschnitt 8) – ausgelöst über Signale, damit Produktionen und
Mitgliedschaften das Board nicht kennen müssen."""

from django.utils.formats import date_format

from . import services

TRACKED = ("status_id", "start_date", "end_date", "location_name", "deleted_at")


def _period(production):
    if production.start_date == production.end_date:
        return date_format(production.start_date, "D., d.m.Y")
    start = date_format(production.start_date, "D., d.m.")
    return f"{start} – {date_format(production.end_date, 'D., d.m.Y')}"


def remember_production(sender, instance, raw=False, **kwargs):
    instance._board_old = None
    if raw or instance._state.adding or instance.pk is None:
        return
    instance._board_old = sender.all_objects.filter(pk=instance.pk).values(*TRACKED).first()


def announce_production(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    org = instance.organization
    if created:
        services.post_system(org, f"Neue Produktion: {instance.name}", link_production=instance)
        return
    old = getattr(instance, "_board_old", None)
    if not old:
        return
    if old["deleted_at"] is None and instance.deleted_at is not None:
        services.post_system(org, f"Produktion gelöscht: {instance.name}")
        return
    if old["deleted_at"] is not None and instance.deleted_at is None:
        services.post_system(
            org, f"Produktion wiederhergestellt: {instance.name}", link_production=instance
        )
        return
    if instance.deleted_at is not None:
        return
    if old["status_id"] != instance.status_id:
        services.post_system(
            org, f"{instance.name}: Status jetzt {instance.status}", link_production=instance
        )
    if (old["start_date"], old["end_date"]) != (instance.start_date, instance.end_date):
        services.post_system(
            org, f"{instance.name}: neues Datum {_period(instance)}", link_production=instance
        )
    if old["location_name"] != instance.location_name:
        text = (
            f"{instance.name}: neuer Ort {instance.location_name}"
            if instance.location_name
            else f"{instance.name}: kein Ort mehr angegeben"
        )
        services.post_system(org, text, link_production=instance)


def announce_member(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        services.post_system(instance.organization, f"Neues Mitglied: {instance.user}")
