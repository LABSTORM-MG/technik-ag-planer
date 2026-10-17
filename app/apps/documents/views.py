"""Vorschau und PDF je Dokument (Abschnitt 9: „Vorschau vor dem Teilen oder Drucken“).

Jede View liefert ohne `as_pdf` die Vorschau im App-Layout, mit `as_pdf` das PDF –
beide aus demselben Template.
"""

from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.organizations.decorators import org_required, permission_required_in_org
from apps.organizations.permissions import Perm
from apps.productions.models import Job, Production
from apps.productions.services import with_jobs_and_crew
from apps.productions.views import hours_context, hours_membership
from apps.scheduling import periods as school_periods

from . import services
from .pdf import pdf_response, render_pdf

PRODUCTIONS = {"active_section": "productions"}


def _production(request, pk):
    return get_object_or_404(
        with_jobs_and_crew(Production.objects.for_org(request.organization)), pk=pk
    )


def _document(request, *, url, as_pdf, template, title, filename, context, back, hints=()):
    """`url` = (URL-Name, pk) der Vorschau; das PDF liegt unter „<URL-Name>_pdf“.
    `back` = (Link, Text) für „← zurück“."""
    url_name, pk = url
    context = {
        **context,
        "organization": request.organization,
        "doc_title": title,
        "created_at": timezone.localtime(),
        "created_by": request.user,
    }
    if as_pdf:
        content = render_pdf(request, template, context)
        return pdf_response(content, f"{filename}.pdf", download="download" in request.GET)
    return render(
        request,
        "documents/preview.html",
        {
            **PRODUCTIONS,
            **context,
            "body_template": template,
            "pdf_url": reverse(f"documents:{url_name}_pdf", args=[pk]) + _query(request),
            "download_url": reverse(f"documents:{url_name}_pdf", args=[pk])
            + _query(request, download="1"),
            "pdf_filename": f"{filename}.pdf",
            "back_url": back[0],
            "back_label": back[1],
            "hints": hints,
        },
    )


def _query(request, **extra):
    """Filter der Vorschau (z. B. Zeitraum) an die PDF-URL weitergeben."""
    params = request.GET.copy()
    params.pop("download", None)
    params.update(extra)
    return f"?{params.urlencode()}" if params else ""


@org_required
def production_call_sheet(request, pk, as_pdf=False):
    production = _production(request, pk)
    return _document(
        request,
        url=("production_call_sheet", production.pk),
        as_pdf=as_pdf,
        template="documents/call_sheet.html",
        title=f"Call Sheet – {production.name}",
        filename=f"call-sheet-{slugify(production.name)}",
        context={
            "production": production,
            "jobs": production.jobs.all(),
            "supervisors": production.supervisors.all(),
        },
        back=(reverse("productions:detail", args=[production.pk]), production.name),
    )


@org_required
def job_call_sheet(request, pk, as_pdf=False):
    job = get_object_or_404(
        Job.objects.for_org(request.organization).of_active_productions(), pk=pk
    )
    production = _production(request, job.production_id)
    job = next(j for j in production.jobs.all() if j.pk == job.pk)
    return _document(
        request,
        url=("job_call_sheet", job.pk),
        as_pdf=as_pdf,
        template="documents/call_sheet.html",
        title=f"Call Sheet – {production.name} – {job.name}",
        filename=f"call-sheet-{slugify(production.name)}-{slugify(job.name)}",
        context={
            "production": production,
            "job": job,
            "jobs": [job],
            "supervisors": production.supervisors.all(),
        },
        back=(reverse("productions:detail", args=[production.pk]), production.name),
    )


@permission_required_in_org(Perm.CREATE_RELEASE_LIST)
def release_list(request, pk, as_pdf=False):
    production = _production(request, pk)
    hints = ["Nur zugesagte Crew ohne Lehrkräfte; Wochenenden fallen weg."]
    if not school_periods.periods_for(request.organization):
        hints.append("Es ist noch kein Stundenraster eingetragen – die Liste bleibt deshalb leer.")
    return _document(
        request,
        url=("release_list", production.pk),
        as_pdf=as_pdf,
        template="documents/release_list.html",
        title=f"Freistellungsliste – {production.name}",
        filename=f"freistellungsliste-{slugify(production.name)}",
        context={
            "production": production,
            "rows": services.release_rows(production),
            "supervisors": production.supervisors.all(),
        },
        back=(reverse("productions:detail", args=[production.pk]), production.name),
        hints=hints,
    )


@org_required
def packing_list(request, pk, as_pdf=False):
    production = _production(request, pk)
    return _document(
        request,
        url=("packing_list", production.pk),
        as_pdf=as_pdf,
        template="documents/packing_list.html",
        title=f"Packliste – {production.name}",
        filename=f"packliste-{slugify(production.name)}",
        context={"production": production, "planned": services.packing_items(production)},
        back=(reverse("inventory:packing_list", args=[production.pk]), "Packliste"),
    )


@org_required
def hours(request, pk, as_pdf=False):
    membership = hours_membership(request, pk)
    context = hours_context(request, membership)
    return _document(
        request,
        url=("hours", membership.pk),
        as_pdf=as_pdf,
        template="documents/hours.html",
        title=f"Einsatzübersicht – {membership.user}",
        filename=f"einsatzuebersicht-{slugify(str(membership.user))}-{context['period'].start:%Y-%m-%d}",
        context=context,
        back=(
            reverse("productions:hours_member", args=[membership.pk]) + _query(request),
            "Einsatzübersicht",
        ),
    )
