from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.db.models import Count
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.organizations.models import Membership

from .models import User


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fields = ["organization", "role", "joined_at"]
    readonly_fields = ["organization", "role", "joined_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class CreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ["email", "display_name"]


class ChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Kontenübersicht für den Betreiber: sperren, löschen, 2FA zurücksetzen."""

    form = ChangeForm
    add_form = CreationForm
    ordering = ["email"]
    list_display = [
        "email",
        "display_name",
        "grade",
        "orgs",
        "has_2fa_display",
        "is_active",
        "is_staff",
        "last_login",
    ]
    list_filter = ["is_active", "is_staff", "grade"]
    search_fields = ["email", "display_name"]
    inlines = [MembershipInline]
    actions = ["lock", "unlock", "reset_2fa"]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Angaben", {"fields": ["display_name", "grade"]}),
        ("Status", {"fields": ["is_active", "is_staff", "is_superuser"]}),
        ("Daten", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (
            None,
            {"classes": ["wide"], "fields": ["email", "display_name", "password1", "password2"]},
        ),
    ]
    readonly_fields = ["last_login", "date_joined"]
    filter_horizontal = []

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_orgs=Count("memberships"))

    @admin.display(description="AGs", ordering="_orgs")
    def orgs(self, obj):
        return obj._orgs

    @admin.display(description="2FA", boolean=True)
    def has_2fa_display(self, obj):
        return obj.has_2fa

    @admin.action(description="Konten sperren")
    def lock(self, request, queryset):
        for user in queryset.exclude(pk=request.user.pk):
            user.is_active = False
            user.save(update_fields=["is_active"])
        self.message_user(request, "Ausgewählte Konten gesperrt.")

    @admin.action(description="Sperre aufheben")
    def unlock(self, request, queryset):
        for user in queryset:
            user.is_active = True
            user.save(update_fields=["is_active"])
        self.message_user(request, "Sperre aufgehoben.")

    @admin.action(description="Zwei-Faktor-Anmeldung zurücksetzen")
    def reset_2fa(self, request, queryset):
        deleted, _ = TOTPDevice.objects.filter(user__in=queryset).delete()
        self.message_user(
            request,
            f"{deleted} Authenticator-Gerät(e) entfernt. Die Person kann 2FA neu einrichten.",
            messages.SUCCESS,
        )
