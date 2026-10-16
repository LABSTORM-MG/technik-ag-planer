"""Einfacher Schutz gegen das Durchprobieren von Passwörtern und Codes."""

import hashlib

from django.conf import settings
from django.core.cache import cache


def _key(scope, identifier, ip):
    raw = f"{scope}:{identifier.lower()}:{ip}"
    return "throttle:" + hashlib.sha256(raw.encode()).hexdigest()


def client_ip(request):
    # Nur hinter Caddy vertrauenswürdig: Caddy ersetzt X-Forwarded-For durch die echte Adresse.
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def is_blocked(scope, identifier, request):
    return cache.get(_key(scope, identifier, client_ip(request)), 0) >= settings.LOGIN_MAX_ATTEMPTS


def register_failure(scope, identifier, request):
    key = _key(scope, identifier, client_ip(request))
    cache.add(key, 0, timeout=settings.LOGIN_BLOCK_SECONDS)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=settings.LOGIN_BLOCK_SECONDS)


def reset(scope, identifier, request):
    cache.delete(_key(scope, identifier, client_ip(request)))
