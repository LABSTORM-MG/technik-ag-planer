from datetime import timedelta

import pytest
from django.utils import timezone

from apps.inventory.tests.conftest import make_material  # noqa: F401 – auch hier gebraucht
from apps.scheduling.models import SchoolPeriod
from apps.scheduling.periods import DEFAULT_PERIODS


@pytest.fixture
def raster(org):
    """Stundenraster mit den Vorschlagswerten (1. Stunde 8:00–8:45 …)."""
    for number, start, end in DEFAULT_PERIODS:
        SchoolPeriod.objects.create(organization=org, number=number, start_time=start, end_time=end)


@pytest.fixture
def monday():
    today = timezone.localdate()
    return today + timedelta(days=7 - today.weekday())
