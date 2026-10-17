from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.accounts.models import FORMER_MEMBER
from apps.organizations.models import OrganizationQuerySet, OrganizationScopedModel

from .palette import Color

DEFAULT_CATEGORIES = [
    ("Schulfest", Color.YELLOW),
    ("Theater", Color.PINK),
    ("Konzert", Color.BLUE),
    ("Sonstiges", Color.GREY),
]


class Category(OrganizationScopedModel):
    name = models.CharField("Name", max_length=60)
    color = models.CharField("Farbe", max_length=10, choices=Color.choices, default=Color.BLUE)
    position = models.PositiveIntegerField("Reihenfolge", default=0)

    class Meta:
        verbose_name = "Kategorie"
        verbose_name_plural = "Kategorien"
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


class ProductionStatus(OrganizationScopedModel):
    """Status einer Produktion. „In Planung“ und „Bestätigt“ sind System-Status (nicht löschbar)."""

    PLANNING = "planning"
    CONFIRMED = "confirmed"
    SYSTEM_DEFAULTS = [
        (PLANNING, "In Planung", Color.ORANGE),
        (CONFIRMED, "Bestätigt", Color.GREEN),
    ]

    name = models.CharField("Name", max_length=40)
    color = models.CharField("Farbe", max_length=10, choices=Color.choices, default=Color.GREY)
    position = models.PositiveIntegerField("Reihenfolge", default=0)
    system_key = models.CharField(
        max_length=20,
        blank=True,
        choices=[(PLANNING, "In Planung"), (CONFIRMED, "Bestätigt")],
        editable=False,
    )

    class Meta:
        verbose_name = "Status"
        verbose_name_plural = "Status-Werte"
        ordering = ["position", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "system_key"],
                condition=~models.Q(system_key=""),
                name="status_unique_system_key",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def is_system(self):
        return bool(self.system_key)

    @property
    def is_planning(self):
        return self.system_key == self.PLANNING

    @classmethod
    def planning_for(cls, organization):
        return cls.objects.for_org(organization).get(system_key=cls.PLANNING)


def ensure_defaults(organization):
    """Legt Standard-Kategorien und System-Status für eine AG an (idempotent)."""
    if not Category.objects.for_org(organization).exists():
        Category.objects.bulk_create(
            Category(organization=organization, name=name, color=color, position=i)
            for i, (name, color) in enumerate(DEFAULT_CATEGORIES)
        )
    for i, (key, name, color) in enumerate(ProductionStatus.SYSTEM_DEFAULTS):
        ProductionStatus.objects.get_or_create(
            organization=organization,
            system_key=key,
            defaults={"name": name, "color": color, "position": i},
        )


class ProductionQuerySet(OrganizationQuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def upcoming(self, today=None):
        return self.filter(end_date__gte=today or timezone.localdate())

    def past(self, today=None):
        return self.filter(end_date__lt=today or timezone.localdate())


class ActiveProductionManager(models.Manager.from_queryset(ProductionQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Production(OrganizationScopedModel):
    """Eine Schulveranstaltung mit Jobs und Crew."""

    name = models.CharField("Name der Produktion", max_length=120)
    category = models.ForeignKey(
        Category,
        verbose_name="Kategorie",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="productions",
    )
    start_date = models.DateField("Von", default=timezone.localdate)
    end_date = models.DateField("Bis", default=timezone.localdate)
    status = models.ForeignKey(
        ProductionStatus, verbose_name="Status", on_delete=models.RESTRICT, related_name="+"
    )
    location_name = models.CharField("Ort", max_length=120, blank=True, help_text="z. B. Aula")
    address = models.CharField("Adresse", max_length=200, blank=True)
    notes = models.TextField("Notizen", blank=True)
    chat_enabled = models.BooleanField("Eigener Chat für die Produktion", default=False)
    supervisors = models.ManyToManyField(
        "organizations.Membership", verbose_name="Aufsicht", blank=True, related_name="+"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="angelegt von",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField("angelegt am", auto_now_add=True)
    updated_at = models.DateTimeField("geändert am", auto_now=True)
    deleted_at = models.DateTimeField("gelöscht am", null=True, blank=True)

    objects = ActiveProductionManager()
    all_objects = ProductionQuerySet.as_manager()

    class Meta:
        verbose_name = "Produktion"
        verbose_name_plural = "Produktionen"
        ordering = ["start_date", "name"]
        base_manager_name = "all_objects"

    def __str__(self):
        return self.name

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "„Bis“ darf nicht vor „Von“ liegen."})

    @property
    def is_multi_day(self):
        return self.start_date != self.end_date

    @property
    def purge_at(self):
        if self.deleted_at is None:
            return None
        return self.deleted_at + timedelta(days=settings.PRODUCTION_TRASH_DAYS)

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])

    def next_job(self, now=None):
        """Nächster noch nicht beendeter Job, sonst der erste."""
        now = timezone.localtime(now or timezone.now())
        jobs = list(self.jobs.all())
        upcoming = [j for j in jobs if j.end_datetime >= now]
        return (upcoming or jobs or [None])[0]


class JobQuerySet(OrganizationQuerySet):
    def of_active_productions(self):
        return self.filter(production__deleted_at__isnull=True)


class Job(OrganizationScopedModel):
    production = models.ForeignKey(
        Production, verbose_name="Produktion", on_delete=models.CASCADE, related_name="jobs"
    )
    name = models.CharField("Job", max_length=80, help_text="z. B. Aufbau, Show, Abbau")
    date = models.DateField("Datum")
    start_time = models.TimeField("Beginn")
    end_time = models.TimeField("Ende")
    meeting_point = models.CharField(
        "Treffpunkt", max_length=120, blank=True, help_text="z. B. Bühneneingang"
    )
    crew_needed = models.PositiveSmallIntegerField(
        "Benötigte Personen",
        null=True,
        blank=True,
        help_text="Optional. Fehlen 3 Tage vorher noch Zusagen, erscheint eine Meldung im Board.",
    )
    position = models.PositiveIntegerField(default=0)

    objects = JobQuerySet.as_manager()

    class Meta:
        verbose_name = "Job"
        verbose_name_plural = "Jobs"
        ordering = ["date", "start_time", "position"]

    def __str__(self):
        return f"{self.production} – {self.name}"

    def clean(self):
        errors = {}
        production = getattr(self, "production", None)
        if (
            production
            and self.date
            and not (production.start_date <= self.date <= production.end_date)
        ):
            errors["date"] = "Das Datum muss im Zeitraum der Produktion liegen."
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            errors["end_time"] = "Das Ende muss nach dem Beginn liegen."
        if errors:
            raise ValidationError(errors)

    def _aware(self, t):
        return timezone.make_aware(datetime.combine(self.date, t))

    @property
    def confirmed_count(self):
        return sum(1 for a in self.crew.all() if a.is_confirmed)

    @property
    def start_datetime(self):
        return self._aware(self.start_time)

    @property
    def end_datetime(self):
        return self._aware(self.end_time)


class CrewAssignment(OrganizationScopedModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "angefragt"
        CONFIRMED = "confirmed", "zugesagt"

    job = models.ForeignKey(Job, verbose_name="Job", on_delete=models.CASCADE, related_name="crew")
    # Leer, wenn das Konto gelöscht wurde oder die AG verlassen hat – der Einsatz bleibt
    membership = models.ForeignKey(
        "organizations.Membership",
        verbose_name="Mitglied",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assignments",
    )
    role_label = models.CharField(
        "Position", max_length=40, blank=True, help_text="z. B. FOH, Bühne, Monitor"
    )
    status = models.CharField(
        "Status", max_length=10, choices=Status.choices, default=Status.REQUESTED
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    corrected_hours = models.DecimalField(
        "Tatsächliche Stunden",
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Leer lassen, um die Stunden aus den Zeiten zu berechnen.",
    )
    # Startzeit, für die schon erinnert wurde – wird der Job verschoben, kommt eine neue Erinnerung
    reminded_for = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Crew-Eintrag"
        verbose_name_plural = "Crew"
        ordering = ["membership__user__display_name"]
        constraints = [
            models.UniqueConstraint(fields=["job", "membership"], name="crew_unique_per_job")
        ]

    def __str__(self):
        return f"{self.person} – {self.job} ({self.get_status_display()})"

    @property
    def is_confirmed(self):
        return self.status == self.Status.CONFIRMED

    @property
    def person(self):
        """Name für Anzeigen; gelöschte Konten und Ausgetretene erscheinen anonym."""
        return str(self.membership.user) if self.membership_id else FORMER_MEMBER


class Todo(OrganizationScopedModel):
    production = models.ForeignKey(
        Production, verbose_name="Produktion", on_delete=models.CASCADE, related_name="todos"
    )
    text = models.CharField("Aufgabe", max_length=200)
    done = models.BooleanField("erledigt", default=False)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    done_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "To-do"
        verbose_name_plural = "To-dos"
        ordering = ["done", "position", "created_at"]

    def __str__(self):
        return self.text


class ProductionLink(OrganizationScopedModel):
    """Link im Abschnitt „Dateien“ (z. B. Bühnenplan in einer Cloud, Ablaufplan)."""

    production = models.ForeignKey(
        Production, verbose_name="Produktion", on_delete=models.CASCADE, related_name="links"
    )
    title = models.CharField("Titel", max_length=120, blank=True, help_text="z. B. Bühnenplan")
    url = models.URLField("Link", max_length=500)

    class Meta:
        verbose_name = "Link"
        verbose_name_plural = "Links"
        ordering = ["id"]

    def __str__(self):
        return self.title or self.url


class Skill(OrganizationScopedModel):
    """Fähigkeit zur Auswahl (Owner pflegt die Liste, Mitglieder wählen selbst)."""

    name = models.CharField("Name", max_length=40)
    position = models.PositiveIntegerField("Reihenfolge", default=0)
    members = models.ManyToManyField(
        "organizations.Membership", verbose_name="Mitglieder", blank=True, related_name="skills"
    )

    class Meta:
        verbose_name = "Fähigkeit"
        verbose_name_plural = "Fähigkeiten"
        ordering = ["position", "name"]

    def __str__(self):
        return self.name
