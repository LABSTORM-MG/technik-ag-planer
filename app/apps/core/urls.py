from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("material/", views.placeholder, {"section_key": "inventory"}, name="inventory"),
    path("healthz/", views.healthz, name="healthz"),
]
