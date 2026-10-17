from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .permissions import Perm


def org_required(view):
    """Die View braucht eine aktive AG; ohne Mitgliedschaft geht es zur Seite „Keine AG“."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.organization is None:
            return redirect("organizations:no_organization")
        return view(request, *args, **kwargs)

    wrapper.checks_organization = True  # für tests/test_security.py
    return wrapper


def permission_required_in_org(perm: Perm):
    """Prüft das Recht laut Rechte-Tabelle (Abschnitt 2) in der aktiven AG."""

    def decorator(view):
        @wraps(view)
        @org_required
        def wrapper(request, *args, **kwargs):
            if not request.membership.has_perm(perm):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def owner_required(view):
    @wraps(view)
    @org_required
    def wrapper(request, *args, **kwargs):
        if not request.membership.is_owner:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
