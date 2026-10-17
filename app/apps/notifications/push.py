"""Versand an ein Gerät über Web Push (VAPID). Tests ersetzen `send` durch eine Attrappe."""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

OK, GONE, FAILED = "ok", "gone", "failed"


def is_enabled():
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def send(subscription, payload):
    """Schickt `payload` (dict) an ein Gerät. OK, GONE (Gerät abgemeldet) oder FAILED."""
    from pywebpush import WebPushException, webpush

    contact = settings.VAPID_ADMIN_EMAIL or settings.DEFAULT_FROM_EMAIL
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{contact}"},
            ttl=12 * 60 * 60,
            timeout=10,
        )
    except WebPushException as error:
        status = getattr(error.response, "status_code", None)
        if status in (404, 410):
            return GONE
        logger.warning("Push an %s fehlgeschlagen: %s", subscription.pk, error)
        return FAILED
    except Exception as error:  # noqa: BLE001 – Netzwerkfehler o. Ä. sollen nichts aufhalten
        logger.warning("Push an %s fehlgeschlagen: %s", subscription.pk, error)
        return FAILED
    return OK
