"""Board und Produktions-Chats: senden, bearbeiten, löschen, Lesestand und Zähler."""

from datetime import timedelta
from functools import reduce
from operator import or_

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.organizations.permissions import Perm
from apps.productions.models import CrewAssignment, Production
from apps.productions.palette import Color

from .models import Message, ReadMarker

# Produktions-Chats verschwinden so viele Tage nach dem Ende aus der Leiste
CHAT_BAR_DAYS_AFTER_END = 3
# Farben für Absender-Namen: die Palette ohne Grau (zu nah an „gedämpft“)
AUTHOR_COLORS = [c.value for c in Color if c != Color.GREY]


def author_color(user_id):
    """Fester Palette-Schlüssel je Konto, damit Namen im Chat wiedererkennbar sind."""
    if not user_id:
        return Color.GREY.value
    return AUTHOR_COLORS[user_id % len(AUTHOR_COLORS)]


# ---------- Nachrichten ----------


def post(organization, author, text, production=None):
    return Message.objects.create(
        organization=organization, author=author, text=text.strip(), production=production
    )


def post_system(organization, text, *, link_production=None, link_material=None, key=""):
    """Systemmeldung im Board. Mit `key` wird dieselbe Meldung nur einmal geschrieben."""
    if key and Message.objects.for_org(organization).filter(system_key=key).exists():
        return None
    try:
        with transaction.atomic():
            return Message.objects.create(
                organization=organization,
                kind=Message.Kind.SYSTEM,
                text=text[:500],
                link_production=link_production,
                link_material=link_material,
                system_key=key,
            )
    except IntegrityError:  # gleichzeitig schon geschrieben
        return None


def edit(message, text):
    message.text = text.strip()
    message.edited_at = timezone.now()
    message.save(update_fields=["text", "edited_at"])


def can_edit(message, membership):
    return not message.is_system and message.author_id == membership.user_id


def can_delete(message, membership):
    if membership.has_perm(Perm.MODERATE_MESSAGES):
        return True
    return not message.is_system and message.author_id == membership.user_id


# ---------- Chats ----------


def chat_productions(organization):
    """Produktionen mit eigenem Chat (nicht gelöscht)."""
    return Production.objects.for_org(organization).filter(chat_enabled=True)


def channel_messages(organization, production=None):
    return Message.objects.for_org(organization).filter(production=production)


# ---------- Lesestand und Zähler ----------


def mark_read(membership, production, last_id):
    if not last_id:
        return
    marker, _ = ReadMarker.objects.get_or_create(
        organization=membership.organization, membership=membership, production=production
    )
    if marker.last_read_id < last_id:
        marker.last_read_id = last_id
        marker.save(update_fields=["last_read_id"])


def _unread_filter(membership, production_ids):
    """Q-Ausdruck für ungelesene Nachrichten in Board (None) und den angegebenen Chats.

    Ohne Lesestand gilt alles als ungelesen, was seit dem Beitritt geschrieben wurde.
    """
    markers = dict(
        ReadMarker.objects.filter(membership=membership).values_list(
            "production_id", "last_read_id"
        )
    )
    parts = []
    for production_id in production_ids:
        channel = (
            Q(production__isnull=True) if production_id is None else Q(production_id=production_id)
        )
        if production_id in markers:
            parts.append(channel & Q(id__gt=markers[production_id]))
        else:
            parts.append(channel & Q(created_at__gte=membership.joined_at))
    return reduce(or_, parts)


def _unread(membership, production_ids):
    return (
        Message.objects.for_org(membership.organization)
        .filter(_unread_filter(membership, production_ids))
        .exclude(author_id=membership.user_id)
    )


def unread_count(membership, production=None):
    return _unread(membership, [production.pk if production else None]).count()


def my_chat_production_ids(membership):
    """Chats, die für den Zähler in der Navigation zählen: eingeteilt oder Aufsicht."""
    crew = CrewAssignment.objects.for_org(membership.organization).filter(membership=membership)
    return list(
        chat_productions(membership.organization)
        .filter(
            Q(pk__in=crew.values("job__production_id")) | Q(supervisors=membership),
        )
        .values_list("pk", flat=True)
        .distinct()
    )


def nav_unread_count(membership):
    """Board plus die Chats der eigenen Produktionen (wie die Regel für Push in Abschnitt 8)."""
    return _unread(membership, [None, *my_chat_production_ids(membership)]).count()


def chat_bar(membership, today=None):
    """Kreise oben im Board: Chats mit neuen Nachrichten zuerst, danach nach Datum."""
    today = today or timezone.localdate()
    productions = list(
        chat_productions(membership.organization)
        .filter(end_date__gte=today - timedelta(days=CHAT_BAR_DAYS_AFTER_END))
        .select_related("category")
        .order_by("start_date", "name")
    )
    if not productions:
        return []
    counts = dict(
        _unread(membership, [p.pk for p in productions])
        .values("production_id")
        .annotate(n=Count("id"))
        .values_list("production_id", "n")
    )
    for production in productions:
        production.unread = counts.get(production.pk, 0)
    # sort ist stabil: innerhalb der Gruppen bleibt die Reihenfolge nach Datum
    productions.sort(key=lambda p: p.unread == 0)
    return productions
