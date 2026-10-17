from django.urls import path

from . import views

app_name = "board"

urlpatterns = [
    path("board/", views.index, name="index"),
    path("board/produktion/<int:pk>/", views.production_chat, name="production"),
    path("board/neu/", views.new_messages, name="new"),
    path("board/senden/", views.send, name="send"),
    path("board/nachricht/<int:pk>/bearbeiten/", views.edit, name="edit"),
    path("board/nachricht/<int:pk>/loeschen/", views.delete, name="delete"),
]
