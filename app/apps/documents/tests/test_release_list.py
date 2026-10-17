"""Freistellungsliste: wer wann vom Unterricht freigestellt werden muss."""

from datetime import time, timedelta

from apps.documents.services import release_rows
from apps.organizations.permissions import Role
from apps.productions.models import CrewAssignment
from apps.scheduling.models import SchoolPeriod
from apps.scheduling.periods import describe

CONFIRMED = CrewAssignment.Status.CONFIRMED


def test_describe_groups_consecutive_periods():
    def periods(*numbers):
        return [SchoolPeriod(number=n) for n in numbers]

    assert describe(periods(4)) == "4. Stunde"
    assert describe(periods(3, 4, 5)) == "3.–5. Stunde"
    assert describe(periods(5, 1, 2)) == "1.–2., 5. Stunde"
    assert describe([]) == ""


def test_jobs_on_the_same_day_are_merged(
    org, raster, monday, make_member, make_production, make_job, make_assignment
):
    production = make_production(org)
    morning = make_job(production, "Aufbau", day=monday, start=time(8), end=time(10))
    noon = make_job(production, "Probe", day=monday, start=time(12, 30), end=time(13))
    emma = make_member(org, Role.STUDENT, display_name="Emma", grade="Q1")
    make_assignment(morning, emma, CONFIRMED)
    make_assignment(noon, emma, CONFIRMED)

    [row] = release_rows(production)

    assert row.date == monday
    assert (row.name, row.grade) == ("Emma", "Q1")
    assert row.periods_label == "1.–3., 6. Stunde"


def test_only_confirmed_students_on_school_time(
    org, raster, monday, make_member, make_production, make_job, make_assignment
):
    production = make_production(org)
    job = make_job(production, "Aufbau", day=monday, start=time(9), end=time(11))
    evening = make_job(production, "Show", day=monday, start=time(18), end=time(21))
    saturday = make_job(production, "Abbau", day=monday + timedelta(days=5))
    admin = make_member(org, Role.ADMIN, display_name="Ali", grade="5")
    make_assignment(job, admin, CONFIRMED)
    make_assignment(job, make_member(org, Role.STUDENT, display_name="Angefragt"))
    make_assignment(job, make_member(org, Role.TEACHER, display_name="Frau Lehrer"), CONFIRMED)
    make_assignment(job, make_member(org, display_name="Abgänger", grade="EXT"), CONFIRMED)
    late = make_member(org, display_name="Ben", grade="7")
    make_assignment(evening, late, CONFIRMED)
    make_assignment(saturday, late, CONFIRMED)
    make_assignment(job, make_member(org, display_name="Zoe", grade="Q2"), CONFIRMED)

    rows = release_rows(production)

    assert [(r.name, r.grade, r.periods_label) for r in rows] == [
        ("Ali", "5", "2.–4. Stunde"),
        ("Zoe", "Q2", "2.–4. Stunde"),
    ]


def test_without_raster_nobody_is_listed(
    org, monday, make_member, make_production, make_job, make_assignment
):
    production = make_production(org)
    job = make_job(production, day=monday, start=time(9), end=time(11))
    make_assignment(job, make_member(org), CONFIRMED)
    assert release_rows(production) == []
