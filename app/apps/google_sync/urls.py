from django.urls import path

from . import views

app_name = "google_sync"

urlpatterns = [
    path("einstellungen/google/", views.settings_page, name="settings"),
    path("einstellungen/google/verbinden/", views.connect, name="connect"),
    path("einstellungen/google/rueckmeldung/", views.callback, name="callback"),
    path("einstellungen/google/trennen/", views.disconnect, name="disconnect"),
    path("einstellungen/google/abgleichen/", views.sync_now, name="sync_now"),
    path("produktionen/<int:pk>/dateien/neu/", views.production_upload, name="production_upload"),
    path("material/<int:pk>/dateien/neu/", views.material_upload, name="material_upload"),
    path("dateien/<int:pk>/", views.attachment_open, name="open"),
    path("dateien/<int:pk>/loeschen/", views.attachment_delete, name="delete"),
]
