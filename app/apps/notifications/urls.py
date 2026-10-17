from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("einstellungen/benachrichtigungen/", views.settings_page, name="settings"),
    path("benachrichtigungen/geraet/", views.subscribe, name="subscribe"),
    path("benachrichtigungen/geraet/abmelden/", views.unsubscribe, name="unsubscribe"),
    path("benachrichtigungen/test/", views.test, name="test"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
]
