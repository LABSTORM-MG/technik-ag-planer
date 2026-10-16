from unittest import mock

import pytest
from django.db.utils import OperationalError
from django.urls import reverse

from apps.core.tasks import ping


@pytest.mark.django_db
def test_healthz_ok(client):
    response = client.get(reverse("core:healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "datenbank": True}


def test_healthz_reports_database_error(client):
    with mock.patch("apps.core.views.connection.cursor", side_effect=OperationalError):
        response = client.get(reverse("core:healthz"))

    assert response.status_code == 503
    assert response.json()["datenbank"] is False


def test_ping_task_runs():
    assert ping.delay().get() == "pong"
