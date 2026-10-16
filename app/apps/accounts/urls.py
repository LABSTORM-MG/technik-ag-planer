from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("anmelden/", views.login_view, name="login"),
    path("anmelden/code/", views.login_2fa_view, name="login_2fa"),
    path("abmelden/", views.logout_view, name="logout"),
    path("passwort-vergessen/", views.password_reset_view, name="password_reset"),
    path(
        "passwort-vergessen/gesendet/",
        views.password_reset_done_view,
        name="password_reset_done",
    ),
    path(
        "passwort-neu/<uidb64>/<token>/",
        views.password_reset_confirm_view,
        name="password_reset_confirm",
    ),
    path(
        "passwort-neu/fertig/",
        views.password_reset_complete_view,
        name="password_reset_complete",
    ),
    path("einstellungen/konto/profil/", views.profile_view, name="profile"),
    path("einstellungen/konto/passwort/", views.password_change_view, name="password_change"),
    path("einstellungen/konto/zwei-faktor/", views.two_factor_view, name="two_factor"),
    path(
        "einstellungen/konto/zwei-faktor/ausschalten/",
        views.two_factor_disable_view,
        name="two_factor_disable",
    ),
]
