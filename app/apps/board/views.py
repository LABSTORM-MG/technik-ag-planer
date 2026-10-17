from django.contrib import messages as flash
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.decorators import permission_required_in_org
from apps.organizations.permissions import Perm

from . import services
from .forms import MessageForm
from .models import Message

PAGE_SIZE = 50
BOARD = {"active_section": "board"}


# ---------- Hilfen (immer nach AG gefiltert) ----------


def _chat_production(request, pk):
    """Produktion mit aktiviertem Chat; fremde, gelöschte oder ohne Chat → 404."""
    return get_object_or_404(services.chat_productions(request.organization), pk=pk)


def _production_from(request, value):
    if not value:
        return None
    try:
        pk = int(value)
    except (TypeError, ValueError):
        raise PermissionDenied from None
    return _chat_production(request, pk)


def _message(request, pk):
    return get_object_or_404(
        Message.objects.for_org(request.organization)
        .filter(production__deleted_at__isnull=True)
        .select_related("production"),
        pk=pk,
    )


def chat_url(production):
    if production is None:
        return reverse("board:index")
    return reverse("board:production", args=[production.pk])


def _day(message):
    return timezone.localtime(message.created_at).date()


def prepare(messages, membership, previous_day=None):
    """Ergänzt Datumstrenner, Absenderfarbe und Rechte für das Template."""
    for message in messages:
        day = _day(message)
        message.day = day if day != previous_day else None
        previous_day = day
        message.is_own = message.author_id == membership.user_id
        message.color = services.author_color(message.author_id)
        message.can_edit = services.can_edit(message, membership)
        message.can_delete = services.can_delete(message, membership)
    return messages


def _base_queryset(request, production):
    return services.channel_messages(request.organization, production).select_related(
        "author", "link_production"
    )


# ---------- Seiten ----------


def _chat_page(request, production):
    queryset = _base_queryset(request, production)
    before = request.GET.get("vor", "")
    if before.isdigit():
        queryset = queryset.filter(id__lt=int(before))
    page = list(queryset.order_by("-id")[: PAGE_SIZE + 1])
    has_older = len(page) > PAGE_SIZE
    page = page[:PAGE_SIZE][::-1]
    if page and not before:
        services.mark_read(request.membership, production, page[-1].pk)

    return render(
        request,
        "board/board.html",
        {
            **BOARD,
            "production": production,
            "chat_bar": services.chat_bar(request.membership),
            "chat_messages": prepare(page, request.membership),
            "has_older": has_older,
            "last_id": page[-1].pk if page else 0,
            "form": MessageForm(),
            "chat_url": chat_url(production),
        },
    )


@permission_required_in_org(Perm.USE_BOARD)
def index(request):
    return _chat_page(request, None)


@permission_required_in_org(Perm.USE_BOARD)
def production_chat(request, pk):
    return _chat_page(request, _chat_production(request, pk))


@require_GET
@permission_required_in_org(Perm.USE_BOARD)
def new_messages(request):
    """Neue Nachrichten seit `nach` als HTML-Fragment (für die Aktualisierung per JavaScript)."""
    production = _production_from(request, request.GET.get("produktion"))
    after = request.GET.get("nach", "")
    after = int(after) if after.isdigit() else 0
    queryset = _base_queryset(request, production)
    previous = queryset.filter(id__lte=after).order_by("-id").first()
    page = list(queryset.filter(id__gt=after).order_by("id")[:PAGE_SIZE])
    if not page:
        return HttpResponse(status=204)
    services.mark_read(request.membership, production, page[-1].pk)
    return render(
        request,
        "board/includes/messages.html",
        {
            "chat_messages": prepare(
                page, request.membership, previous_day=_day(previous) if previous else None
            ),
            "last_id": page[-1].pk,
        },
    )


# ---------- Aktionen ----------


@require_POST
@permission_required_in_org(Perm.USE_BOARD)
def send(request):
    production = _production_from(request, request.POST.get("produktion"))
    form = MessageForm(request.POST)
    is_script = bool(request.headers.get("X-Board"))
    if form.is_valid():
        services.post(request.organization, request.user, form.cleaned_data["text"], production)
        if is_script:
            return HttpResponse(status=204)
    else:
        if is_script:
            return HttpResponse(" ".join(form.errors["text"]), status=400)
        flash.error(request, " ".join(form.errors["text"]))
    return redirect(chat_url(production) + "#ende")


@permission_required_in_org(Perm.USE_BOARD)
def edit(request, pk):
    message = _message(request, pk)
    if not services.can_edit(message, request.membership):
        raise PermissionDenied
    form = MessageForm(request.POST or None, initial={"text": message.text})
    if request.method == "POST" and form.is_valid():
        services.edit(message, form.cleaned_data["text"])
        flash.success(request, "Nachricht geändert.")
        return redirect(f"{chat_url(message.production)}#nachricht-{message.pk}")
    form.fields["text"].widget.attrs.update(rows=4, autofocus=True)
    return render(
        request,
        "board/edit.html",
        {**BOARD, "form": form, "message": message, "chat_url": chat_url(message.production)},
    )


@require_POST
@permission_required_in_org(Perm.USE_BOARD)
def delete(request, pk):
    message = _message(request, pk)
    if not services.can_delete(message, request.membership):
        raise PermissionDenied
    production = message.production
    message.delete()
    flash.success(request, "Nachricht gelöscht.")
    return redirect(chat_url(production) + "#ende")
