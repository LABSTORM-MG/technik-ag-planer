"""Inhalte der Dokumente – ohne Darstellung."""

from dataclasses import dataclass, field
from datetime import date, time

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
    """Ein Zeitblock an einem Tag mit allen Schülerinnen und Schülern, die er betrifft."""

    date: date
    start: time
    end: time
    periods: list = field(default_factory=list)
    rows: list = field(default_factory=list)

    @property
    def periods_label(self):
        return school_periods.describe(self.periods)

    @property
    def time_label(self):
        return f"{self.start:%H:%M}–{self.end:%H:%M} Uhr"


def _runs(periods):
    """Teilt Stunden in zusammenhängende Blöcke; eine Lücke beginnt einen neuen."""
    runs = []
    for period in periods:
        if runs and period.number == runs[-1][-1].number + 1:
            runs[-1].append(period)
        else:
            runs.append([period])
    return runs


def _released_assignments(production):
    return (
        CrewAssignment.objects.for_org(production.organization)
        .filter(job__production=production, status=CrewAssignment.Status.CONFIRMED)
        .filter(membership__isnull=False)
        .exclude(membership__role=Role.TEACHER)
        .exclude(membership__user__grade=Grade.EXTERN)
        .select_related("job", "membership__user")
    )


def _blocks_by_job_times(production):
    """Ohne Stundenraster: zusammengefasste Jobzeiten je Person an Schultagen."""
    spans = {}
    for a in _released_assignments(production):
        if a.job.date.weekday() < 5:
            spans.setdefault((a.job.date, a.membership_id), (a, []))[1].append(
                (a.job.start_time, a.job.end_time)
            )
    blocks = {}
    for (day, _member), (assignment, times) in spans.items():
        user = assignment.membership.user
        row = ReleaseRow(day, str(user), user.get_grade_display(), user.grade)
        merged = []
        for start, end in sorted(times):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        for start, end in merged:
            blocks.setdefault((day, start, end), ReleaseBlock(day, start, end)).rows.append(row)
    for block in blocks.values():
        block.rows.sort(key=_row_order)
    return [blocks[key] for key in sorted(blocks)]


def _row_order(row):
    return (GRADE_ORDER.get(row.grade_key, len(GRADE_ORDER)), row.name.lower())


def release_blocks(production):
    """Freistellungsliste nach Blöcken, damit Lehrkräfte blockweise eintragen können."""
    if not school_periods.periods_for(production.organization):
        return _blocks_by_job_times(production)
    blocks = {}
    for row in release_rows(production):
        for run in _runs(row.periods):
            key = (row.date, run[0].number, run[-1].number)
            block = blocks.setdefault(
                key, ReleaseBlock(row.date, run[0].start_time, run[-1].end_time, run)
            )
            block.rows.append(row)
    return [blocks[key] for key in sorted(blocks)]


def release_omissions(production):
    """Wer in einem Job steht, aber nicht auf der Liste, und warum (nur für die Vorschau)."""
    listed = {(row.name, block.date) for block in release_blocks(production) for row in block.rows}
    has_raster = bool(school_periods.periods_for(production.organization))
    reasons = {}
    assignments = (
        CrewAssignment.objects.for_org(production.organization)
        .filter(job__production=production, membership__isnull=False)
        .select_related("job", "membership__user")
    )
    for a in assignments:
        user = a.membership.user
        if a.status != CrewAssignment.Status.CONFIRMED:
            reason = "noch nicht zugesagt"
        elif a.membership.role == Role.TEACHER:
            reason = "Lehrkraft"
        elif user.grade == Grade.EXTERN:
            reason = "extern"
        elif a.job.date.weekday() >= 5:
            reason = "Job am Wochenende"
        elif has_raster and (str(user), a.job.date) not in listed:
            reason = "Job außerhalb der Schulstunden"
        else:
            continue
        reasons.setdefault(str(user), set()).add(reason)
    names = {row[0] for row in listed}
    return [
        f"{name}: {', '.join(sorted(why))}"
        for name, why in sorted(reasons.items())
        if name not in names
    ]


def packing_items(production):
    """Geplantes Material, nach Material-Kategorie sortiert (für {% regroup %})."""
    return production.planned_material.select_related("material", "material__category").order_by(
        "material__category__position", "material__category__name", "material__name"
    )
