import base64
import io
import time

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, update_session_auth_hash
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.organizations.permissions import Role

from . import throttle
from .forms import (
    ConfirmPasswordForm,
    EmailPasswordResetForm,
    GermanPasswordChangeForm,
    GermanSetPasswordForm,
    LoginForm,
    ProfileForm,
    TokenForm,
)

PENDING_USER_KEY = "pending_2fa_user_id"
PENDING_NEXT_KEY = "pending_2fa_next"
PENDING_SINCE_KEY = "pending_2fa_since"
PENDING_MAX_SECONDS = 5 * 60
BLOCKED_MESSAGE = "Zu viele Fehlversuche. Bitte versuche es in 15 Minuten erneut."


def _safe_next(request, value):
    if value and url_has_allowed_host_and_scheme(
        value, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return value
    return reverse("productions:dashboard")


def confirmed_device(user):
    return TOTPDevice.objects.filter(user=user, confirmed=True).first()


def needs_grade(user):
    """Jahrgangsstufe brauchen alle außer Lehrkräften (Abschnitt 2)."""
    roles = set(user.memberships.values_list("role", flat=True))
    return bool(roles - {Role.TEACHER})


def _clear_pending(request):
    for key in (PENDING_USER_KEY, PENDING_NEXT_KEY, PENDING_SINCE_KEY):
        request.session.pop(key, None)


@login_not_required
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request, request.GET.get("next")))

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        if throttle.is_blocked("login", email, request):
            form.add_error(None, BLOCKED_MESSAGE)
        else:
            user = authenticate(request, email=email, password=form.cleaned_data["password"])
            if user is None:
                throttle.register_failure("login", email, request)
                form.add_error(None, "E-Mail-Adresse oder Passwort ist falsch.")
            else:
                throttle.reset("login", email, request)
                next_url = _safe_next(request, request.POST.get("next"))
                if confirmed_device(user):
                    request.session[PENDING_USER_KEY] = user.pk
                    request.session[PENDING_NEXT_KEY] = next_url
                    request.session[PENDING_SINCE_KEY] = int(time.time())
                    return redirect("accounts:login_2fa")
                auth_login(request, user)
                return redirect(next_url)

    return render(
        request, "accounts/login.html", {"form": form, "next": request.GET.get("next", "")}
    )


@login_not_required
def login_2fa_view(request):
    user_id = request.session.get(PENDING_USER_KEY)
    since = request.session.get(PENDING_SINCE_KEY, 0)
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None or time.time() - since > PENDING_MAX_SECONDS:
        _clear_pending(request)
        if user is not None:
            messages.info(request, "Bitte melde dich erneut an.")
        return redirect("accounts:login")

    form = TokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if throttle.is_blocked("2fa", user.email, request):
            form.add_error(None, BLOCKED_MESSAGE)
        else:
            device = confirmed_device(user)
            if device is not None and device.verify_token(form.cleaned_data["token"]):
                next_url = request.session.get(PENDING_NEXT_KEY) or reverse("productions:dashboard")
                _clear_pending(request)
                user.backend = "django.contrib.auth.backends.ModelBackend"
                auth_login(request, user)
                otp_login(request, device)
                throttle.reset("2fa", user.email, request)
                return redirect(next_url)
            throttle.register_failure("2fa", user.email, request)
            form.add_error("token", "Der Code ist falsch oder abgelaufen.")

    return render(request, "accounts/login_2fa.html", {"form": form})


@require_POST
def logout_view(request):
    auth_logout(request)
    messages.info(request, "Du bist abgemeldet.")
    return redirect("accounts:login")


def profile_view(request):
    grade_needed = needs_grade(request.user)
    form = ProfileForm(request.POST or None, instance=request.user, needs_grade=grade_needed)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Gespeichert.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form, "active_section": "settings"})


def password_change_view(request):
    form = GermanPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Dein Passwort wurde geändert.")
        return redirect("organizations:settings")
    return render(
        request, "accounts/password_change.html", {"form": form, "active_section": "settings"}
    )


def _qr_svg_data_uri(device):
    import qrcode
    import qrcode.image.svg

    image = qrcode.make(device.config_url, image_factory=qrcode.image.svg.SvgPathImage)
    buffer = io.BytesIO()
    image.save(buffer)
    return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode()


def _2fa_required_by_org(user):
    return user.memberships.filter(organization__require_2fa=True).exists()


def two_factor_view(request):
    """Meine Zwei-Faktor-Anmeldung: Status, Einrichtung per Authenticator-App, Deaktivieren."""
    user = request.user
    device = confirmed_device(user)
    context = {
        "active_section": "settings",
        "device": device,
        "required": _2fa_required_by_org(user),
        "forced": request.GET.get("pflicht") == "1",
    }
    if device is not None:
        context["disable_form"] = ConfirmPasswordForm(user=user)
        return render(request, "accounts/two_factor.html", context)

    pending, _ = TOTPDevice.objects.get_or_create(
        user=user, confirmed=False, defaults={"name": "Authenticator-App"}
    )
    form = TokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if pending.verify_token(form.cleaned_data["token"]):
            pending.confirmed = True
            pending.save()
            otp_login(request, pending)
            messages.success(request, "Die Zwei-Faktor-Anmeldung ist eingerichtet.")
            return redirect("accounts:two_factor")
        form.add_error(
            "token", "Der Code passt nicht. Prüfe die Uhrzeit am Handy und versuche es erneut."
        )

    secret = base64.b32encode(pending.bin_key).decode().rstrip("=")
    context.update(
        {
            "form": form,
            "qr": _qr_svg_data_uri(pending),
            "secret": " ".join(secret[i : i + 4] for i in range(0, len(secret), 4)),
        }
    )
    return render(request, "accounts/two_factor.html", context)


@require_POST
def two_factor_disable_view(request):
    if _2fa_required_by_org(request.user):
        raise PermissionDenied
    form = ConfirmPasswordForm(request.POST, user=request.user)
    if form.is_valid():
        TOTPDevice.objects.filter(user=request.user).delete()
        messages.success(request, "Die Zwei-Faktor-Anmeldung ist ausgeschaltet.")
    else:
        messages.error(request, "Das Passwort ist falsch. Die Zwei-Faktor-Anmeldung bleibt aktiv.")
    return redirect("accounts:two_factor")


# „Passwort vergessen“ – Djangos Views mit eigenen Templates und Texten
password_reset_view = login_not_required(
    auth_views.PasswordResetView.as_view(
        form_class=EmailPasswordResetForm,
        template_name="accounts/password_reset.html",
        email_template_name="emails/password_reset.txt",
        html_email_template_name="emails/password_reset.html",
        subject_template_name="emails/password_reset_subject.txt",
        success_url=reverse_lazy("accounts:password_reset_done"),
    )
)
password_reset_done_view = login_not_required(
    auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html")
)
password_reset_confirm_view = login_not_required(
    auth_views.PasswordResetConfirmView.as_view(
        form_class=GermanSetPasswordForm,
        template_name="accounts/password_reset_confirm.html",
        success_url=reverse_lazy("accounts:password_reset_complete"),
    )
)
password_reset_complete_view = login_not_required(
    auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"
    )
)
