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

        self._productions(Organization.objects.get(name="Technik-AG Nord"))
        self._scheduling(Organization.objects.get(name="Technik-AG Nord"))

        self.stdout.write(self.style.SUCCESS("Beispieldaten angelegt."))
        self.stdout.write(f"Passwort für alle Konten: {PASSWORD}")
        for org_name, people in ORGS.items():
            self.stdout.write(f"\n{org_name}:")
            for email, _name, _grade, role in people:
                self.stdout.write(f"  {Role(role).label:<11} {email}")

    def _productions(self, org):
        from datetime import time, timedelta

        from django.utils import timezone

        from apps.productions.models import Category, Job, Production, ProductionStatus, Todo
        from apps.productions.services import assign

        if Production.all_objects.for_org(org).exists():
            return
        today = timezone.localdate()
        categories = {c.name: c for c in Category.objects.for_org(org)}
        planning = ProductionStatus.planning_for(org)
        confirmed = ProductionStatus.objects.for_org(org).get(system_key="confirmed")
        members = {m.user.email: m for m in Membership.objects.for_org(org).select_related("user")}

        plans = [
            (
                "Schulkonzert",
                "Konzert",
                2,
                2,
                confirmed,
                "Aula",
                "Schulstraße 1, 50667 Köln",
                [
                    ("Aufbau", 0, time(14), time(17), "Bühneneingang"),
                    ("Show", 1, time(18), time(21), "Technikpult"),
                    ("Abbau", 1, time(21), time(22, 30), "Aula"),
                ],
            ),
            (
                "Theater-Premiere",
                "Theater",
                9,
                1,
                planning,
                "Aula",
                "",
                [
                    ("Aufbau", 0, time(13), time(16), "Bühneneingang"),
                    ("Show", 0, time(19), time(21, 30), "Technikpult"),
                ],
            ),
            (
                "Sommerfest 2025",
                "Schulfest",
                -120,
                1,
                confirmed,
                "Schulhof",
                "",
                [("Aufbau", 0, time(9), time(11), "Hausmeisterei")],
            ),
        ]
        for name, cat, ahead, length, status, location, address, jobs in plans:
            start = today + timedelta(days=ahead)
            production = Production.objects.create(
                organization=org,
                name=name,
                category=categories[cat],
                start_date=start,
                end_date=start + timedelta(days=length - 1),
                status=status,
                location_name=location,
                address=address,
            )
            for i, (job_name, offset, begin, end, meeting) in enumerate(jobs):
                Job.objects.create(
                    organization=org,
                    production=production,
                    name=job_name,
                    date=start + timedelta(days=offset),
                    start_time=begin,
                    end_time=end,
                    meeting_point=meeting,
                    position=i,
                )
        concert = Production.objects.for_org(org).get(name="Schulkonzert")
        setup, show = concert.jobs.get(name="Aufbau"), concert.jobs.get(name="Show")
        assign(setup, members["emma@nord.example"], status="requested", role_label="Bühne")
        assign(setup, members["ben@nord.example"], status="confirmed", role_label="Licht")
        assign(show, members["admin@nord.example"], status="confirmed", role_label="FOH")
        assign(show, members["emma@nord.example"], status="confirmed", role_label="Monitor")
        for text in ["Funkmikros laden", "Bühnenplan drucken"]:
            Todo.objects.create(organization=org, production=concert, text=text)

    def _scheduling(self, org):
        from datetime import date, time, timedelta

        from django.utils import timezone

        from apps.scheduling.models import Event, SchoolPeriod, Unavailability
        from apps.scheduling.periods import DEFAULT_PERIODS
        from apps.scheduling.services import create_event

        if SchoolPeriod.objects.for_org(org).exists():
            return
        for number, start, end in DEFAULT_PERIODS:
            SchoolPeriod.objects.create(
                organization=org, number=number, start_time=start, end_time=end
            )
        today = timezone.localdate()
        # Nächster Donnerstag, wöchentlich bis Schuljahresende (30. Juni)
        first = today + timedelta(days=(3 - today.weekday()) % 7 or 7)
        until = date(first.year + (first.month >= 7), 6, 30)
        if not Event.objects.for_org(org).exists():
            create_event(
                org,
                {
                    "title": "AG-Treffen",
                    "date": first,
                    "start_time": time(14),
                    "end_time": time(15, 30),
                    "location": "Technikraum",
                    "notes": "",
                },
                frequency="weekly",
                until=until,
            )
        members = {m.user.email: m for m in Membership.objects.for_org(org).select_related("user")}
        # Emma schreibt eine Klausur (1.–4. Stunde), Ben ist zwei Tage auf Klassenfahrt
        klausur = today + timedelta(days=2)
        Unavailability.objects.create(
            organization=org,
            membership=members["emma@nord.example"],
            start_date=klausur,
            end_date=klausur,
            start_time=time(8),
            end_time=time(11, 20),
            note="Klausur",
        )
        trip = today + timedelta(days=5)
        Unavailability.objects.create(
            organization=org,
            membership=members["ben@nord.example"],
            start_date=trip,
            end_date=trip + timedelta(days=1),
            note="Klassenfahrt",
        )
