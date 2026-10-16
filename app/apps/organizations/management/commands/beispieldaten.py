"""Legt Beispieldaten zum lokalen Durchklicken an: zwei AGs mit Konten in allen Rollen.

    make beispieldaten   (bzw. python manage.py beispieldaten)

Alle Konten haben das Passwort „technik-ag-planer“. Nur in der Entwicklung (DEBUG) erlaubt.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization
from apps.organizations.permissions import Role

PASSWORD = "technik-ag-planer"  # noqa: S105 – nur lokale Beispieldaten

ORGS = {
    "Technik-AG Nord": [
        ("owner@nord.example", "Olivia Owner", "Q1", Role.OWNER),
        ("admin@nord.example", "Ali Admin", "EF", Role.ADMIN),
        ("lehrkraft@nord.example", "Frau Lehmann", "", Role.TEACHER),
        ("emma@nord.example", "Emma", "8", Role.STUDENT),
        ("ben@nord.example", "Ben", "10", Role.STUDENT),
    ],
    "Technik-AG Süd": [
        ("owner@sued.example", "Sam Süd", "Q2", Role.OWNER),
        ("emma@nord.example", "Emma", "8", Role.STUDENT),  # Mitglied in zwei AGs
    ],
}


class Command(BaseCommand):
    help = "Legt Beispieldaten für die lokale Entwicklung an."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Auch ohne DEBUG ausführen.")

    @transaction.atomic
    def handle(self, *args, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError("Nur in der Entwicklung (DEBUG) – oder mit --force.")

        for org_name, people in ORGS.items():
            org, _ = Organization.objects.get_or_create(name=org_name)
            for email, name, grade, role in people:
                user, created = User.objects.get_or_create(
                    email=email, defaults={"display_name": name, "grade": grade}
                )
                if created:
                    user.set_password(PASSWORD)
                    user.save()
                Membership.objects.get_or_create(
                    organization=org, user=user, defaults={"role": role}
                )

        self.stdout.write(self.style.SUCCESS("Beispieldaten angelegt."))
        self.stdout.write(f"Passwort für alle Konten: {PASSWORD}")
        for org_name, people in ORGS.items():
            self.stdout.write(f"\n{org_name}:")
            for email, _name, _grade, role in people:
                self.stdout.write(f"  {Role(role).label:<11} {email}")
