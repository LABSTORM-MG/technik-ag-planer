from django.urls import path

from . import views

app_name = "inquiries"

urlpatterns = [
    path("anfrage/<str:token>/", views.public_form, name="public"),
    path("anfrage/<str:token>/danke/", views.public_thanks, name="public_thanks"),
    path("anfragen/<int:pk>/", views.inquiry_detail, name="detail"),
    path("anfragen/<int:pk>/erledigt/", views.inquiry_done, name="done"),
    path("anfragen/erledigt/", views.done_list, name="done_list"),
    path("einstellungen/technik-anfragen/", views.link_settings, name="settings"),
]
