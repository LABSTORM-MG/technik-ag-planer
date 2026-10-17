"""Fähigkeiten: Verwaltung durch den Owner, eigene Auswahl, Filter und Vorschläge beim Einteilen."""

from datetime import time, timedelta

import pytest
from django.urls import reverse

from apps.organizations.permissions import Role
from apps.productions.models import CrewAssignment, Skill
from apps.productions.services import suggest_crew

CONFIRMED = CrewAssignment.Status.CONFIRMED


@pytest.fixture
def make_skill():
    def factory(organization, name="Licht", members=()):
        skill = Skill.objects.create(organization=organization, name=name)
        skill.members.set(members)
        return skill

    return factory


def test_owner_manages_skills(org, owner, login):
    client = login(owner.user, org)
    client.post(reverse("productions:skills"), {"name": "Licht"})
    client.post(reverse("productions:skills"), {"name": "Ton"})
    licht, ton = Skill.objects.for_org(org)
    assert (licht.name, licht.position, ton.position) == ("Licht", 0, 1)

    client.post(reverse("productions:skill_move", args=[ton.pk]), {"richtung": "-1"})
    assert [s.name for s in Skill.objects.for_org(org)] == ["Ton", "Licht"]

    client.post(reverse("productions:skill_edit", args=[licht.pk]), {"name": "Licht & Video"})
    client.post(reverse("productions:skill_delete", args=[ton.pk]))
    assert [s.name for s in Skill.objects.for_org(org)] == ["Licht & Video"]


@pytest.mark.parametrize("role", [Role.ADMIN, Role.TEACHER, Role.STUDENT])
def test_only_owner_manages_skills(org, make_member, make_skill, login, role):
    skill = make_skill(org)
    client = login(make_member(org, role).user, org)
    assert client.get(reverse("productions:skills")).status_code == 403
    assert client.post(reverse("productions:skill_delete", args=[skill.pk])).status_code == 403


def test_foreign_skill_returns_404(org, other_org, owner, make_skill, login):
    foreign = make_skill(other_org)
    client = login(owner.user, org)
    for name in ["skill_edit", "skill_delete", "skill_move"]:
        method = client.get if name == "skill_edit" else client.post
        assert method(reverse(f"productions:{name}", args=[foreign.pk])).status_code == 404


def test_my_skills(org, other_org, student, student_client, make_skill):
    licht, ton = make_skill(org, "Licht"), make_skill(org, "Ton")
    foreign = make_skill(other_org, "Fremd")
    url = reverse("productions:my_skills")
    assert "Licht" in student_client.get(url).content.decode()

    student_client.post(url, {"skills": [licht.pk, ton.pk]})
    assert set(student.skills.all()) == {licht, ton}

    student_client.post(url, {"skills": [foreign.pk]})
    assert set(student.skills.all()) == {licht, ton}  # fremde Fähigkeit abgelehnt


def test_member_list_shows_skills(org, student, member_client, make_skill):
    make_skill(org, "Kamera", members=[student])
    assert "Kamera" in member_client.get(reverse("organizations:members")).content.decode()


def test_crew_form_filters_and_suggests(
    org, planner_client, make_member, make_production, make_job, make_assignment, make_skill
):
    production = make_production(org)
    job = make_job(production, start=time(14), end=time(16))
    busy = make_member(org, display_name="Busy")
    busy_job = make_job(make_production(org, "Anderes"), day=job.date, start=time(15))
    make_assignment(busy_job, busy, CONFIRMED)
    taken = make_member(org, display_name="Schon dabei")
    make_assignment(job, taken)
    veteran = make_member(org, display_name="Veteran")
    past = make_production(org, "Früher", days_ahead=-1)
    make_assignment(make_job(past), veteran, CONFIRMED)
    rookie = make_member(org, display_name="Rookie")
    no_skill = make_member(org, display_name="Ohne Licht")
    licht = make_skill(org, "Licht", members=[busy, taken, veteran, rookie])

    assert [m.user.display_name for m in suggest_crew(job, licht)] == ["Rookie", "Veteran"]

    url = reverse("productions:job_crew", args=[job.pk])
    content = planner_client.get(f"{url}?faehigkeit={licht.pk}").content.decode()
    assert "Vorschläge" in content and "Rookie" in content
    assert no_skill.user.display_name not in content

    preselected = planner_client.get(f"{url}?faehigkeit={licht.pk}&mitglied={rookie.pk}")
    assert f'value="{rookie.pk}" selected' in preselected.content.decode()


def test_suggestions_skip_unavailable(org, make_member, make_production, make_job, make_skill):
    from apps.scheduling.models import Unavailability

    job = make_job(make_production(org))
    away = make_member(org, display_name="Weg")
    Unavailability.objects.create(
        organization=org, membership=away, start_date=job.date, end_date=job.date + timedelta(1)
    )
    assert suggest_crew(job, make_skill(org, members=[away])) == []
