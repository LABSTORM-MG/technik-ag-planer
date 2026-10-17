from django.urls import path

from . import views

app_name = "documents"

PDF = {"as_pdf": True}

urlpatterns = [
    path(
        "produktionen/<int:pk>/call-sheet/",
        views.production_call_sheet,
        name="production_call_sheet",
    ),
    path(
        "produktionen/<int:pk>/call-sheet.pdf",
        views.production_call_sheet,
        PDF,
        name="production_call_sheet_pdf",
    ),
    path("jobs/<int:pk>/call-sheet/", views.job_call_sheet, name="job_call_sheet"),
    path("jobs/<int:pk>/call-sheet.pdf", views.job_call_sheet, PDF, name="job_call_sheet_pdf"),
    path("produktionen/<int:pk>/freistellungsliste/", views.release_list, name="release_list"),
    path(
        "produktionen/<int:pk>/freistellungsliste.pdf",
        views.release_list,
        PDF,
        name="release_list_pdf",
    ),
    path("einsaetze/<int:pk>/uebersicht/", views.hours, name="hours"),
    path("einsaetze/<int:pk>/uebersicht.pdf", views.hours, PDF, name="hours_pdf"),
    path("produktionen/<int:pk>/packliste.pdf", views.packing_list, PDF, name="packing_list_pdf"),
    path(
        "produktionen/<int:pk>/packliste/vorschau/",
        views.packing_list,
        name="packing_list",
    ),
]
