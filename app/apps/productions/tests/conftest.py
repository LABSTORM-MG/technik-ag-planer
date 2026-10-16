from datetime import time, timedelta

import pytest
from django.utils import timezone

from apps.organizations.permissions import Role
from apps.productions.models import CrewAssignment, Job, Production, ProductionStatus


@pytest.fixture
def make_production():
    def factory(organization, name="Schulkonzert", days_ahead=3, length=1, **extra):
        start = timezone.localdate() + timedelta(days=days_ahead)
        extra.setdefault("status", ProductionStatus.planning_for(organization))
        return Production.objects.create(
            organization=organization,
            name=name,
            start_date=start,
            end_date=start + timedelta(days=length - 1),
            **extra,
        )

    return factory


@pytest.fixture
def make_job():
    def factory(production, name="Aufbau", day=None, start=time(14), end=time(16), **extra):
        return Job.objects.create(
            organization=production.organization,
            production=production,
            name=name,
            date=day or production.start_date,
            start_time=start,
            end_time=end,
            **extra,
        )

    return factory


@pytest.fixture
def make_assignment():
    def factory(job, membership, status=CrewAssignment.Status.REQUESTED, **extra):
        return CrewAssignment.objects.create(
            organization=job.organization,
            job=job,
            membership=membership,
            status=status,
            **extra,
        )

    return factory


@pytest.fixture
def planner(org, make_member):
    return make_member(org, Role.ADMIN, display_name="Ali Admin")


@pytest.fixture
def planner_client(planner, login, org):
    return login(planner.user, org)


@pytest.fixture
def student(org, make_member):
    return make_member(org, Role.STUDENT, display_name="Emma")


@pytest.fixture
def student_client(student, login, org):
    return login(student.user, org)


@pytest.fixture
def concert(org, make_production, make_job):
    production = make_production(org, location_name="Aula", address="Schulstraße 1, Köln")
    make_job(production, "Aufbau", meeting_point="Bühneneingang")
    make_job(production, "Show", start=time(18), end=time(21))
    return production
