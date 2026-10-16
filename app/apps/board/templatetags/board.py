from datetime import timedelta

from django import template
from django.utils import timezone
from django.utils.formats import date_format

register = template.Library()


@register.filter
def board_day(day):
    """Datumstrenner im Chat: „Heute“, „Gestern“ oder „Mi., 14.10.2026“."""
    today = timezone.localdate()
    if day == today:
        return "Heute"
    if day == today - timedelta(days=1):
        return "Gestern"
    return date_format(day, "D., d.m.Y")
