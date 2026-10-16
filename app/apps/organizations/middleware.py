from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import SimpleLazyObject

from .models import Membership
from .permissions import OrgPerms

SESSION_KEY = "active_organization_id"


def active_memberships(user):
    return (
        Membership.objects.filter(user=user, organization__is_active=True)
        .select_related("organization")
        .order_by("organization__name")
    )


def set_active_organization(request, organization):
    request.session[SESSION_KEY] = organization.pk


class OrganizationMiddleware:
    """Mandantentrennung: setzt request.organization und request.membership.

    Die aktive AG steht in der Session. Ist sie ungültig (keine Mitgliedschaft mehr,
    AG deaktiviert), wird die erste verbleibende AG gewählt – oder keine.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membership = None
        request.organization = None
        request.memberships = []

        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            memberships = list(active_memberships(user))
            request.memberships = memberships
            wanted = request.session.get(SESSION_KEY)
            current = next((m for m in memberships if m.organization_id == wanted), None)
            if current is None and memberships:
                current = memberships[0]
                request.session[SESSION_KEY] = current.organization_id
            if current is not None:
                request.membership = current
                request.organization = current.organization

        request.org_perms = SimpleLazyObject(lambda: OrgPerms(request.membership))
        return self.get_response(request)


class Require2FAMiddleware:
    """Schreibt die AG Zwei-Faktor vor, müssen Mitglieder ohne 2FA sie zuerst einrichten."""

    ALLOWED_URL_NAMES = ("accounts:two_factor", "accounts:logout")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        org = getattr(request, "organization", None)
        if org is not None and org.require_2fa and not request.user.has_2fa:
            allowed = {reverse(name) for name in self.ALLOWED_URL_NAMES}
            if request.path not in allowed and not request.path.startswith("/static/"):
                return redirect(f"{reverse('accounts:two_factor')}?pflicht=1")
        return self.get_response(request)
