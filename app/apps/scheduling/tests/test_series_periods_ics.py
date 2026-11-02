from datetime import date, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.scheduling import ics, services
from apps.scheduling.models import Event, EventSeries, SchoolPeriod
from apps.scheduling.periods import DEFAULT_PERIODS, affected_periods, describe, times_for

W, B, M = (
    EventSeries.Frequency.WEEKLY,
    EventSeries.Frequency.BIWEEKLY,
    EventSeries.Frequency.MONTHLY,
)


@pytest.fixture
def periods(org):
    for number, start, end in DEFAULT_PERIODS:
        SchoolPeriod.objects.create(organization=org, number=number, start_time=start, end_time=end)


def test_weekly_and_biweekly_dates():
    start = date(2026, 10, 15)
    assert list(services.occurrence_dates(start, W, date(2026, 11, 5))) == [
        date(2026, 10, 15),
        date(2026, 10, 22),
        date(2026, 10, 29),
        date(2026, 11, 5),
    ]
    assert list(services.occurrence_dates(start, B, date(2026, 11, 5))) == [
        date(2026, 10, 15),
        date(2026, 10, 29),
    ]


def test_monthly_skips_missing_days():
    dates = list(services.occurrence_dates(date(2027, 1, 31), M, date(2027, 5, 31)))
    assert dates == [date(2027, 1, 31), date(2027, 3, 31), date(2027, 5, 31)]


def _series(org, frequency=W, weeks=4):
    start = timezone.localdate() + timedelta(days=1)
    first = services.create_event(
        org,
        {
            "title": "AG-Treffen",
            "date": start,
            "start_time": time(14),
            "end_time": time(15, 30),
            "location": "Technikraum",
            "notes": "",
        },
        frequency=frequency,
        until=start + timedelta(weeks=weeks - 1),
    )
    return list(Event.objects.filter(series=first.series).order_by("date"))


def test_single_change_detaches_without_touching_series(org):
    events = _series(org)
    moved = events[1]
    services.update_event(
        moved,
        {
            "title": "AG-Treffen (verschoben)",
            "date": moved.date + timedelta(days=1),
            "start_time": time(15),
            "end_time": time(16),
        },
    )
    moved.refresh_from_db()
    assert moved.is_detached and moved.title == "AG-Treffen (verschoben)"
    assert {e.title for e in Event.objects.exclude(pk=moved.pk)} == {"AG-Treffen"}


def test_cancel_single_occurrence(org):
    events = _series(org)
    services.set_cancelled(events[2], True)
    assert [e.cancelled for e in Event.objects.order_by("date")] == [False, False, True, False]


def test_change_following_skips_detached(org):
    events = _series(org)
    services.update_event(
        events[2],
        {"title": "Einzeln", "date": events[2].date, "start_time": time(9), "end_time": time(10)},
    )
    services.update_event(
        events[1],
        {
            "title": "Neue Zeit",
            "date": events[1].date,
            "start_time": time(15),
            "end_time": time(16),
        },
        scope="following",
    )
    titles = [e.title for e in Event.objects.order_by("date")]
    assert titles == ["AG-Treffen", "Neue Zeit", "Einzeln", "Neue Zeit"]


def test_delete_following(org):
    events = _series(org)
    services.delete_event(events[2], scope="following")
    assert Event.objects.count() == 2


def test_period_times_and_affected(org, periods):
    assert times_for(org, 5) == (time(11, 40), time(12, 25))
    assert times_for(org, 1, 4) == (time(8), time(11, 20))
    affected = affected_periods(org, time(9, 0), time(12, 0))
    assert describe(affected) == "2.–5. Stunde"


def test_job_form_accepts_school_periods(org, periods, planner_client, concert):
    planner_client.post(
        reverse("productions:job_create", args=[concert.pk]),
        {
            "name": "Probe",
            "date": concert.start_date.isoformat(),
            "start_time": "",
            "start_period": "5",
            "end_time": "",
            "end_period": "6",
            "meeting_point": "",
        },
    )
    job = concert.jobs.get(name="Probe")
    assert (job.start_time, job.end_time) == (time(11, 40), time(13, 10))


def _period_data(*rows, initial=0, **extra):
    data = {
        "periods-TOTAL_FORMS": str(len(rows)),
        "periods-INITIAL_FORMS": str(initial),
        "periods-MIN_NUM_FORMS": "0",
        "periods-MAX_NUM_FORMS": "1000",
        **extra,
    }
    for i, (start, end) in enumerate(rows):
        data[f"periods-{i}-start_time"] = start
        data[f"periods-{i}-end_time"] = end
    return data


def test_owner_saves_period_grid_in_time_order(org, owner, login):
    client = login(owner.user, org)
    response = client.get(reverse("scheduling:periods"))
    assert "Vorschlag" in response.content.decode()

    client.post(reverse("scheduling:periods"), _period_data(("08:45", "09:30"), ("08:00", "08:45")))

    saved = SchoolPeriod.objects.for_org(org)
    assert [(p.number, f"{p.start_time:%H:%M}") for p in saved] == [(1, "08:00"), (2, "08:45")]


def test_period_grid_edit_renumbers_and_removes(org, owner, login):
    client = login(owner.user, org)
    url = reverse("scheduling:periods")
    client.post(url, _period_data(("08:00", "08:45"), ("08:45", "09:30"), ("09:50", "10:35")))

    data = _period_data(
        ("08:00", "08:45"),
        ("08:45", "09:30"),
        ("09:50", "10:35"),
        initial=3,
        **{"periods-1-DELETE": "on"},
    )
    assert client.post(url, data).status_code == 302

    saved = SchoolPeriod.objects.for_org(org)
    assert [(p.number, f"{p.start_time:%H:%M}") for p in saved] == [(1, "08:00"), (2, "09:50")]


def test_period_grid_rejects_overlaps(org, owner, login):
    data = _period_data(("08:00", "09:00"), ("08:45", "09:30"))
    response = login(owner.user, org).post(reverse("scheduling:periods"), data)
    assert "überschneiden" in response.content.decode()
    assert not SchoolPeriod.objects.exists()


def test_period_grid_rejects_end_before_start(org, owner, login):
    data = _period_data(("09:00", "08:00"))
    response = login(owner.user, org).post(reverse("scheduling:periods"), data)
    assert "Das Ende muss nach dem Beginn liegen." in response.content.decode()
    assert not SchoolPeriod.objects.exists()


def test_period_grid_keeps_other_orgs(org, other_org, owner, login):
    SchoolPeriod.objects.create(
        organization=other_org, number=1, start_time=time(8), end_time=time(9)
    )
    login(owner.user, org).post(reverse("scheduling:periods"), _period_data(("10:00", "11:00")))

    assert SchoolPeriod.objects.for_org(other_org).count() == 1
    assert SchoolPeriod.objects.for_org(org).count() == 1


def test_period_grid_only_for_owner(org, planner_client, student_client):
    assert planner_client.get(reverse("scheduling:periods")).status_code == 403
    assert student_client.get(reverse("scheduling:periods")).status_code == 403


def test_ics_structure_and_timezone():
    start = timezone.make_aware(timezone.datetime(2026, 10, 18, 14, 0))
    content = ics.build_calendar(
        [
            ics.IcsEvent(
                uid="job-1@x",
                summary="Schulkonzert – Aufbau, Bühne",
                start=start,
                end=start + timedelta(hours=2),
                location="Aula; hinten",
            ),
            ics.IcsEvent(
                uid="production-1@x",
                summary="Schulkonzert",
                start=date(2026, 10, 18),
                end=date(2026, 10, 20),
            ),
        ]
    )
    assert content.startswith("BEGIN:VCALENDAR\r\n") and content.endswith("END:VCALENDAR\r\n")
    assert content.count("BEGIN:VEVENT") == 2
    assert "DTSTART:20261018T120000Z" in content  # 14:00 MESZ = 12:00 UTC
    assert "DTSTART;VALUE=DATE:20261018" in content
    assert "DTEND;VALUE=DATE:20261020" in content
    assert "SUMMARY:Schulkonzert – Aufbau\\, Bühne" in content
    assert "LOCATION:Aula\\; hinten" in content
    assert all(len(line.encode()) <= 75 for line in content.split("\r\n"))


def test_ics_downloads(org, member_client, concert):
    response = member_client.get(reverse("scheduling:ics_production", args=[concert.pk]))
    assert response["Content-Type"].startswith("text/calendar")
    assert "SUMMARY:Schulkonzert" in response.content.decode()

    job = concert.jobs.first()
    job_ics = member_client.get(reverse("scheduling:ics_job", args=[job.pk])).content.decode()
    assert "Treffpunkt: Bühneneingang" in job_ics
