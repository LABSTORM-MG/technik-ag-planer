from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from apps.inventory.models import Material
from apps.organizations.decorators import org_required, permission_required_in_org
from apps.organizations.permissions import Perm
from apps.productions.models import Production

from . import drive, google_api, oauth, services
from .forms import IMAGE_TYPES, UploadForm
from .google_api import GoogleError
from .models import Attachment, GoogleConnection, SyncedEvent

SETTINGS = {"active_section": "settings"}


# ---------- Einstellungen → Google-Konto (nur Owner) ----------


@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def settings_page(request):
    connection = GoogleConnection.objects.filter(organization=request.organization).first()
    return render(
        request,
        "google_sync/settings.html",
        {
            **SETTINGS,
            "configured": google_api.is_configured(),
            "connection": connection,
            "redirect_uri": oauth.redirect_uri(),
            "subscribe_url": services.subscribe_url(connection),
            "synced_count": SyncedEvent.objects.for_org(request.organization).count(),
        },
    )


@require_POST
@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def connect(request):
    if not google_api.is_configured():
        messages.error(request, "Die Google-Anbindung ist auf diesem Server nicht eingerichtet.")
        return redirect("google_sync:settings")
    return redirect(oauth.authorization_url(request))


@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def callback(request):
    pending = request.session.pop(oauth.SESSION_KEY, None)
    if (
        not pending
        or pending.get("state") != request.GET.get("state")
        or pending.get("organization") != request.organization.pk
    ):
        messages.error(request, "Die Anmeldung bei Google ist abgelaufen. Bitte erneut verbinden.")
        return redirect("google_sync:settings")
    if "error" in request.GET or "code" not in request.GET:
        messages.info(request, "Die Verbindung mit Google wurde abgebrochen.")
        return redirect("google_sync:settings")
    try:
        tokens = oauth.exchange_code(request.GET["code"], pending.get("verifier"))
        services.connect(request.organization, request.user, **tokens)
    except GoogleError as error:
        messages.error(request, error.message)
    else:
        messages.success(
            request,
            f"Verbunden mit {tokens['email']}. Die Einträge werden jetzt in den Google-Kalender "
            "übertragen.",
        )
    return redirect("google_sync:settings")


@require_POST
@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def disconnect(request):
    connection = services.connection_for(request.organization)
    if connection:
        services.disconnect(connection)
        messages.success(
            request,
            "Google-Konto getrennt. Kalender und Dateien bleiben im Google-Konto erhalten.",
        )
    return redirect("google_sync:settings")


@require_POST
@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def sync_now(request):
    from .tasks import sync_calendar

    if services.connection_for(request.organization):
        sync_calendar.delay(request.organization.pk)
        messages.success(request, "Abgleich gestartet – das dauert meist nur wenige Sekunden.")
    return redirect("google_sync:settings")


# ---------- Dateien ----------


def _upload(request, *, target, back, title, max_mb=None):
    form = UploadForm(request.POST or None, request.FILES or None, max_mb=max_mb)
    connected = services.connection_for(request.organization) is not None
    if request.method == "POST" and form.is_valid():
        try:
            attachment = drive.upload(
                request.organization, form.cleaned_data["file"], user=request.user, **target
            )
        except GoogleError as error:
            messages.error(request, error.message)
        else:
            messages.success(request, f"„{attachment.name}“ hochgeladen.")
            return redirect(back)
    return render(
        request,
        "google_sync/upload_form.html",
        {"form": form, "title": title, "back": back, "connected": connected},
    )


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def production_upload(request, pk):
    production = get_object_or_404(Production.objects.for_org(request.organization), pk=pk)
    return _upload(
        request,
        target={"production": production},
        back=reverse("productions:detail", args=[pk]) + "#dateien",
        title=f"Datei für {production.name}",
    )


@permission_required_in_org(Perm.MANAGE_INVENTORY)
def material_upload(request, pk):
    material = get_object_or_404(Material.objects.for_org(request.organization), pk=pk)
    return _upload(
        request,
        target={"material": material},
        back=reverse("inventory:detail", args=[pk]),
        title=f"Datei für {material.name}",
    )


# Wer darf eine Datei öffnen bzw. löschen? (Ziel → Recht; None = alle Mitglieder)
OPEN_PERMS = {"inquiry": Perm.HANDLE_INQUIRIES}
DELETE_PERMS = {
    "production": Perm.MANAGE_PRODUCTIONS,
    "material": Perm.MANAGE_INVENTORY,
    "defect": Perm.MANAGE_INVENTORY,
    "inquiry": Perm.HANDLE_INQUIRIES,
}


def target_of(attachment):
    return next(t for t in Attachment.TARGETS if getattr(attachment, f"{t}_id"))


def _attachment(request, pk, perms):
    attachment = get_object_or_404(
        Attachment.objects.for_org(request.organization).exclude(
            production__deleted_at__isnull=False
        ),
        pk=pk,
    )
    perm = perms.get(target_of(attachment))
    if perm is not None and not request.membership.has_perm(perm):
        raise PermissionDenied
    return attachment


def _back(attachment):
    target = target_of(attachment)
    if target == "production":
        return reverse("productions:detail", args=[attachment.production_id]) + "#dateien"
    if target == "material":
        return reverse("inventory:detail", args=[attachment.material_id])
    if target == "defect":
        return reverse("inventory:detail", args=[attachment.defect.material_id])
    return reverse("inquiries:detail", args=[attachment.inquiry_id])


@org_required
def attachment_open(request, pk):
    attachment = _attachment(request, pk, OPEN_PERMS)
    try:
        content = drive.download(attachment)
    except GoogleError as error:
        messages.error(request, error.message)
        return redirect(_back(attachment))
    # Nur Fotos und PDFs im Browser anzeigen; alles andere (auch SVG, HTML) herunterladen,
    # damit hochgeladene Dateien nie als Seite der App ausgeführt werden
    image = attachment.mime_type in IMAGE_TYPES
    inline = image or attachment.mime_type == "application/pdf"
    content_type = attachment.mime_type if inline else "application/octet-stream"
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = content_disposition_header(not inline, attachment.name)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    if image:
        response["Content-Security-Policy"] = "default-src 'none'; img-src 'self'"
    return response


@require_POST
@org_required
def attachment_delete(request, pk):
    attachment = _attachment(request, pk, DELETE_PERMS)
    back = _back(attachment)
    if drive.delete(attachment):
        messages.success(request, f"„{attachment.name}“ gelöscht – auch im Google Drive.")
    else:
        messages.warning(
            request,
            f"„{attachment.name}“ aus der App entfernt. Im Google Drive konnte sie nicht gelöscht "
            "werden.",
        )
    return redirect(back)
