"""Verschlüsselung des Refresh-Tokens (Fernet, Schlüssel aus DJANGO_SECRET_KEY abgeleitet)."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    digest = hashlib.sha256(f"google-token:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt(value: str) -> str:
    """Leerer Text, wenn nichts gespeichert ist oder der Secret Key gewechselt wurde."""
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return ""
