from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.placeholder, {"section_key": "dashboard"}, name="dashboard"),
    path("kalender/", views.placeholder, {"section_key": "calendar"}, name="calendar"),
    path("produktionen/", views.placeholder, {"section_key": "productions"}, name="productions"),
    path("material/", views.placeholder, {"section_key": "inventory"}, name="inventory"),
    path("board/", views.placeholder, {"section_key": "board"}, name="board"),
    path("einstellungen/", views.placeholder, {"section_key": "settings"}, name="settings"),
    path("healthz/", views.healthz, name="healthz"),
]
