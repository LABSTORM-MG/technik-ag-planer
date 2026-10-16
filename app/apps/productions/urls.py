from django.urls import path

from . import views

app_name = "productions"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("produktionen/", views.production_list, name="list"),
    path("produktionen/neu/", views.production_create, name="create"),
    path("produktionen/<int:pk>/", views.production_detail, name="detail"),
    path("produktionen/<int:pk>/bearbeiten/", views.production_edit, name="edit"),
    path("produktionen/<int:pk>/status/", views.production_status, name="status"),
    path("produktionen/<int:pk>/kopieren/", views.production_copy, name="copy"),
    path("produktionen/<int:pk>/loeschen/", views.production_delete, name="delete"),
    path("produktionen/<int:pk>/wiederherstellen/", views.production_restore, name="restore"),
    path("produktionen/<int:pk>/aufsicht/", views.production_supervise, name="supervise"),
    path("produktionen/<int:pk>/jobs/neu/", views.job_create, name="job_create"),
    path("produktionen/<int:pk>/todos/neu/", views.todo_create, name="todo_create"),
    path("jobs/<int:pk>/bearbeiten/", views.job_edit, name="job_edit"),
    path("jobs/<int:pk>/loeschen/", views.job_delete, name="job_delete"),
    path("jobs/<int:pk>/crew/", views.job_crew, name="job_crew"),
    path("crew/<int:pk>/entfernen/", views.crew_remove, name="crew_remove"),
    path("crew/<int:pk>/antworten/", views.crew_respond, name="crew_respond"),
    path("todos/<int:pk>/abhaken/", views.todo_toggle, name="todo_toggle"),
    path("todos/<int:pk>/loeschen/", views.todo_delete, name="todo_delete"),
    path("einstellungen/kuerzlich-geloescht/", views.trash, name="trash"),
    path("einstellungen/kategorien/", views.categories, name="categories"),
    path("einstellungen/kategorien/<int:pk>/", views.category_edit, name="category_edit"),
    path(
        "einstellungen/kategorien/<int:pk>/loeschen/",
        views.category_delete,
        name="category_delete",
    ),
    path(
        "einstellungen/kategorien/<int:pk>/verschieben/",
        views.category_move,
        name="category_move",
    ),
    path("einstellungen/status-werte/", views.statuses, name="statuses"),
    path("einstellungen/status-werte/<int:pk>/", views.status_edit, name="status_edit"),
    path(
        "einstellungen/status-werte/<int:pk>/loeschen/", views.status_delete, name="status_delete"
    ),
    path("einstellungen/status-werte/<int:pk>/verschieben/", views.status_move, name="status_move"),
]
