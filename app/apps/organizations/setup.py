"""Einrichtungs-Checkliste für den Owner einer neuen AG."""

from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class SetupStep:
    label: str
    hint: str
    url: str
    done: bool


def setup_steps(organization):
    from apps.google_sync.services import connection_for
    from apps.inquiries.models import InquiryLink
    from apps.inventory.models import Material
    from apps.productions.models import Skill
    from apps.scheduling.models import SchoolPeriod

    from .models import Membership

    return [
        SetupStep(
            "Stundenraster eintragen",
            "Damit Jobs in Schulstunden planbar sind und die Freistellungsliste Stunden nennt",
            reverse("scheduling:periods"),
            SchoolPeriod.objects.for_org(organization).exists(),
        ),
        SetupStep(
            "Mitglieder einladen",
            "Crew und Lehrkräfte per E-Mail einladen",
            reverse("organizations:members"),
            Membership.objects.for_org(organization).count() > 1,
        ),
        SetupStep(
            "Fähigkeiten anlegen",
            "Zum Beispiel Licht, Ton, Bühne, damit ihr Crew passend einteilen könnt",
            reverse("productions:skills"),
            Skill.objects.for_org(organization).exists(),
        ),
        SetupStep(
            "Material erfassen",
            "Damit ihr es für Produktionen einplanen und packen könnt",
            reverse("inventory:list"),
            Material.objects.for_org(organization).exists(),
        ),
        SetupStep(
            "Google-Konto verbinden",
            "Für Datei-Uploads und die Übertragung in den Google Kalender",
            reverse("google_sync:settings"),
            connection_for(organization) is not None,
        ),
        SetupStep(
            "Technik-Anfragen freischalten",
            "Link aktivieren, damit Lehrkräfte ohne Konto Technik anfragen können",
            reverse("inquiries:settings"),
            InquiryLink.objects.for_org(organization).filter(is_active=True).exists(),
        ),
    ]
