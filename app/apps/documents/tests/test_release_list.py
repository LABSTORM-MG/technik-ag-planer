"""Freistellungsliste: wer wann vom Unterricht freigestellt werden muss."""

from datetime import time, timedelta

from django.urls import reverse

from apps.documents.services import release_omissions, release_rows, release_tables
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


def test_table_has_periods_as_columns_and_crosses(
    org, raster, monday, make_member, make_production, make_job, make_assignment
):
    production = make_production(org)
    job = make_job(production, "Aufbau", day=monday, start=time(9), end=time(11))
    make_assignment(job, make_member(org, Role.STUDENT, display_name="Emma", grade="Q1"), CONFIRMED)
    make_assignment(job, make_member(org, Role.STUDENT, display_name="Ben", grade="7"), CONFIRMED)

    [table] = release_tables(production)

    assert table.date == monday
    assert table.columns[:2] == ["1.", "2."]
    assert [(name, grade) for name, grade, _cells in table.rows] == [("Ben", "7"), ("Emma", "Q1")]
    marked = [i + 1 for i, cell in enumerate(table.rows[0][2]) if cell]
    assert marked == [2, 3, 4]


def test_table_per_day_and_only_confirmed(
    org, raster, monday, make_member, make_production, make_job, make_assignment
):
    production = make_production(org, length=2)
    first = make_job(production, "Aufbau", day=monday, start=time(9), end=time(10))
    second_day = monday + timedelta(days=1)
    second = make_job(production, "Abbau", day=second_day, start=time(9), end=time(10))
    student = make_member(org, Role.STUDENT, display_name="Emma", grade="Q1")
    make_assignment(first, student, CONFIRMED)
    make_assignment(second, student, CONFIRMED)
    make_assignment(first, make_member(org, Role.STUDENT, display_name="Angefragt"))

    tables = release_tables(production)

    assert [t.date for t in tables] == [monday, second_day]
    assert all([row[0] for row in t.rows] == ["Emma"] for t in tables)


def test_without_raster_columns_are_merged_job_times(
    org, monday, make_member, make_production, make_job, make_assignment
):
    production = make_production(org)
    first = make_job(production, "Aufbau", day=monday, start=time(22, 43), end=time(22, 50))
    second = make_job(production, "Abbau", day=monday, start=time(22, 50), end=time(22, 55))
    weekend = make_job(production, "Sa", day=monday + timedelta(days=5))
    student = make_member(org, Role.STUDENT, display_name="Lennart", grade="10")
    make_assignment(first, student, CONFIRMED)
    make_assignment(second, student, CONFIRMED)
    make_assignment(weekend, student, CONFIRMED)

    [table] = release_tables(production)

    assert table.columns == ["22:43–22:55"]
    assert table.rows[0][0] == "Lennart" and table.rows[0][2] == [True]


def test_omissions_name_who_is_missing_and_why(
    org, raster, monday, make_member, make_production, make_job, make_assignment
):
    production = make_production(org)
    school = make_job(production, "Aufbau", day=monday, start=time(9), end=time(10))
    evening = make_job(production, "Show", day=monday, start=time(22), end=time(23))
    make_assignment(school, make_member(org, display_name="Da", grade="7"), CONFIRMED)
    make_assignment(evening, make_member(org, display_name="Abend", grade="7"), CONFIRMED)
    make_assignment(school, make_member(org, display_name="Offen", grade="7"))
    make_assignment(school, make_member(org, Role.TEACHER, display_name="Frau L"), CONFIRMED)

    assert release_omissions(production) == [
        "Abend: Job außerhalb der Schulstunden",
        "Frau L: Lehrkraft",
        "Offen: noch nicht zugesagt",
    ]


def test_release_list_page_has_no_org_or_app_name_in_document(
    org, owner, login, raster, monday, make_member, make_production, make_job, make_assignment
):
    production = make_production(org)
    job = make_job(production, "Aufbau", day=monday, start=time(9), end=time(10))
    make_assignment(job, make_member(org, Role.STUDENT, display_name="Emma", grade="Q1"), CONFIRMED)

    content = (
        login(owner.user, org)
        .get(reverse("documents:release_list", args=[production.pk]))
        .content.decode()
    )
    document = content.split('<div class="paper">')[1]

    assert "Emma" in document and "doc__cross" in document
    assert org.name not in document
    assert "Technik-AG Planer" not in document
