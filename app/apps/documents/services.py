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
class ReleaseTable:
    """Ein Tag der Freistellungsliste: Personen in den Zeilen, Stunden in den Spalten."""

    date: date
    columns: list
    rows: list = field(default_factory=list)  # (Name, Jahrgang, [angekreuzt je Spalte])


def _merged_job_times(production):
    """Ohne Stundenraster: zusammengefasste Jobzeiten je Person an Schultagen."""
    people = {}
    assignments = (
        CrewAssignment.objects.for_org(production.organization)
        .filter(job__production=production, status=CrewAssignment.Status.CONFIRMED)
        .filter(membership__isnull=False)
        .exclude(membership__role=Role.TEACHER)
        .exclude(membership__user__grade=Grade.EXTERN)
        .select_related("job", "membership__user")
    )
    for a in assignments:
        if a.job.date.weekday() < 5:
            user = a.membership.user
            key = (a.job.date, GRADE_ORDER.get(user.grade, len(GRADE_ORDER)), str(user).lower())
            people.setdefault(key, (user, []))[1].append((a.job.start_time, a.job.end_time))
    result = []
    for key, (user, times) in sorted(people.items(), key=lambda item: item[0]):
        merged = []
        for start, end in sorted(times):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        result.append((key[0], user, [tuple(span) for span in merged]))
    return result


def _tables_by_job_times(production):
    days = {}
    for day, user, spans in _merged_job_times(production):
        days.setdefault(day, []).append((user, spans))
    tables = []
    for day, people in sorted(days.items()):
        columns = sorted({span for _user, spans in people for span in spans})
        table = ReleaseTable(day, [f"{s:%H:%M}–{e:%H:%M}" for s, e in columns])
        for user, spans in people:
            table.rows.append((str(user), user.get_grade_display(), [c in spans for c in columns]))
        tables.append(table)
    return tables


def release_tables(production):
    """Je Schultag eine Tabelle, damit Lehrkräfte Stunde für Stunde eintragen können."""
    raster = school_periods.periods_for(production.organization)
    if not raster:
        return _tables_by_job_times(production)
    tables = {}
    for row in release_rows(production):
        table = tables.setdefault(
            row.date, ReleaseTable(row.date, [f"{p.number}." for p in raster])
        )
        numbers = {p.number for p in row.periods}
        table.rows.append((row.name, row.grade, [p.number in numbers for p in raster]))
    return [tables[day] for day in sorted(tables)]


def release_omissions(production):
    """Wer in einem Job steht, aber nicht auf der Liste, und warum (nur für die Vorschau)."""
    listed = {(row[0], table.date) for table in release_tables(production) for row in table.rows}
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
