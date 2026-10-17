from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("einstellungen/hilfe/", views.help_page, name="help"),
    path("einstellungen/ueber/", views.about, name="about"),
    path("impressum/", views.legal, {"kind": "impressum"}, name="imprint"),
    path("datenschutz/", views.legal, {"kind": "datenschutz"}, name="privacy"),
    path("nutzungsbedingungen/", views.legal, {"kind": "nutzungsbedingungen"}, name="terms"),
]
