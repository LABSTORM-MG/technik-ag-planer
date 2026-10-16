"""Merkt sich, wer gerade eine Änderung auslöst (pro Request bzw. Task)."""

from contextlib import contextmanager
from contextvars import ContextVar

_current_user = ContextVar("audit_current_user", default=None)


def get_current_user():
    return _current_user.get()


@contextmanager
def acting_as(user):
    token = _current_user.set(user)
    try:
        yield
    finally:
        _current_user.reset(token)


class AuditMiddleware:
    """Setzt den angemeldeten Nutzer als Auslöser für alle Änderungen dieses Requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        with acting_as(user if user is not None and user.is_authenticated else None):
            return self.get_response(request)
