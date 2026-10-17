from functools import wraps

from django.contrib.auth.decorators import login_not_required


def landing_for_anonymous(view):
    """Startseite: Nicht Angemeldete sehen die Landingpage (Abschnitt 12), alle anderen die View."""

    @login_not_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from .views import landing

            return landing(request)
        return view(request, *args, **kwargs)

    return wrapper
