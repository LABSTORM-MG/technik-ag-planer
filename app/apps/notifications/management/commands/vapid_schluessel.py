"""Erzeugt ein VAPID-Schlüsselpaar für Web Push – Ausgabe zum Eintragen in die .env.

docker compose -f deploy/docker-compose.yml exec web python manage.py vapid_schluessel
"""

from cryptography.hazmat.primitives import serialization
from django.core.management.base import BaseCommand
from py_vapid import Vapid, b64urlencode


class Command(BaseCommand):
    help = "Erzeugt VAPID-Schlüssel für Push-Mitteilungen."

    def handle(self, *args, **options):
        vapid = Vapid()
        vapid.generate_keys()
        public = vapid.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        private = vapid.private_key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        self.stdout.write("In die .env eintragen (der private Schlüssel ist geheim):\n")
        self.stdout.write(f"VAPID_PUBLIC_KEY={b64urlencode(public)}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={b64urlencode(private)}")
        self.stdout.write("VAPID_ADMIN_EMAIL=admin@example.org")
        self.stdout.write(
            "\nWerden die Schlüssel später gewechselt, müssen alle Geräte Push neu aktivieren."
        )
