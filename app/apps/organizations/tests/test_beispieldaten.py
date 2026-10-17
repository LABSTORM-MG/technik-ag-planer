from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.inventory import services
from apps.inventory.models import Kit, Material
from apps.productions.models import Production


def test_beispieldaten_with_short_logins_and_material(db, settings):
    settings.DEBUG = True
    call_command("beispieldaten")
    call_command("beispieldaten")  # idempotent

    client = Client()
    for name in ["owner", "lehrer", "schueler"]:
        response = client.post(
            reverse("accounts:login"), {"email": f"{name}@example.org", "password": name}
        )
        assert response.status_code == 302, name
        client.logout()

    assert Material.objects.count() == 12
    assert Kit.objects.count() == 2
    concert = Production.objects.get(name="Schulkonzert")
    assert services.production_shortages(concert)  # Beispiel für eine Überbuchung

    from apps.inquiries.models import Inquiry, InquiryLink

    assert InquiryLink.objects.get(organization=concert.organization).is_active
    assert Inquiry.objects.open().count() == 2 and Inquiry.objects.done().count() == 1


def test_beispieldaten_team(db, settings):
    from apps.organizations.models import Membership
    from apps.productions import hours
    from apps.productions.models import Skill

    settings.DEBUG = True
    call_command("beispieldaten")
    emma = Membership.objects.get(
        user__email="schueler@example.org", organization__name="Technik-AG Nord"
    )
    assert Skill.objects.filter(members=emma).count() == 2
    period = hours.periods()[0]
    assert hours.total(hours.entries(emma, period.start, period.end)) > 0
