"""Inhalte der Dokumente – ohne Darstellung."""

from dataclasses import dataclass, field
from datetime import date

from apps.accounts.models import Grade
from apps.organizations.permissions import Role
from apps.productions.models import CrewAssignment
from apps.scheduling import periods as school_periods

GRADE_ORDER = {value: i for i, (value, _label) in enumerate(Grade.choices)}


@dataclass
class ReleaseRow:
    """Eine Zeile der Freistellungsliste: eine Person an einem Tag."""

    date: date
    name: str
    grade: str
    grade_key: str
    periods: list = field(default_factory=list)

    @property
    def periods_label(self):
        return school_periods.describe(self.periods)


def release_rows(production):
    """Wer an welchem Tag für welche Schulstunden freigestellt werden muss (Abschnitt 9).

    Nur zugesagte Crew, keine Lehrkräfte und keine Externen; Wochenenden und Jobs außerhalb
    des Stundenrasters fallen weg. Mehrere Jobs am selben Tag werden zusammengefasst.
    """
    raster = school_periods.periods_for(production.organization)
    assignments = (
        CrewAssignment.objects.for_org(production.organization)
        .filter(job__production=production, status=CrewAssignment.Status.CONFIRMED)
        .filter(membership__isnull=False)
        .exclude(membership__role=Role.TEACHER)
        .exclude(membership__user__grade=Grade.EXTERN)
        .select_related("job", "membership__user")
    )
    rows = {}
    for a in assignments:
        job = a.job
        if job.date.weekday() >= 5:
            continue
        affected = [
            p for p in raster if p.start_time < job.end_time and p.end_time > job.start_time
        ]
        if not affected:
            continue
        user = a.membership.user
        row = rows.setdefault(
            (job.date, a.membership_id),
            ReleaseRow(job.date, str(user), user.get_grade_display(), user.grade),
        )
        row.periods = sorted({*row.periods, *affected}, key=lambda p: p.number)
    return sorted(
        rows.values(),
        key=lambda r: (r.date, GRADE_ORDER.get(r.grade_key, len(GRADE_ORDER)), r.name.lower()),
    )


@dataclass
class ReleaseBlock:
    """Ein Stundenblock an einem Tag mit allen Schülerinnen und Schülern, die er betrifft."""

    date: date
    periods: list
    rows: list = field(default_factory=list)

    @property
    def periods_label(self):
        return school_periods.describe(self.periods)

    @property
    def time_label(self):
        return f"{self.periods[0].start_time:%H:%M}–{self.periods[-1].end_time:%H:%M} Uhr"


def _runs(periods):
    """Teilt Stunden in zusammenhängende Blöcke; eine Lücke beginnt einen neuen."""
    runs = []
    for period in periods:
        if runs and period.number == runs[-1][-1].number + 1:
            runs[-1].append(period)
        else:
            runs.append([period])
    return runs


def release_blocks(production):
    """Freistellungsliste nach Blöcken, damit Lehrkräfte blockweise eintragen können."""
    blocks = {}
    for row in release_rows(production):
        for run in _runs(row.periods):
            key = (row.date, run[0].number, run[-1].number)
            blocks.setdefault(key, ReleaseBlock(row.date, run)).rows.append(row)
    return [blocks[key] for key in sorted(blocks)]


def packing_items(production):
    """Geplantes Material, nach Material-Kategorie sortiert (für {% regroup %})."""
    return production.planned_material.select_related("material", "material__category").order_by(
        "material__category__position", "material__category__name", "material__name"
    )
