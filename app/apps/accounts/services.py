"""Konto löschen (Abschnitte 2 und 11)."""

from django.core.exceptions import ValidationError
from django.db import transaction


def owned_organizations(user):
    from apps.organizations.models import Membership
    from apps.organizations.permissions import Role

    return [
        m.organization
        for m in Membership.objects.filter(user=user, role=Role.OWNER).select_related(
            "organization"
        )
    ]


@transaction.atomic
def delete_account(user):
    """Löscht das Konto endgültig.

    Mitgliedschaften, „Nicht verfügbar“, Lesestand und 2FA-Geräte verschwinden mit dem Konto.
    Einsätze, Termin-Teilnahmen und Board-Nachrichten bleiben anonym als „Ehemaliges Mitglied“
    erhalten (SET_NULL an den Fremdschlüsseln).
    """
    from apps.organizations.models import Invitation

    owned = owned_organizations(user)
    if owned:
        names = ", ".join(o.name for o in owned)
        raise ValidationError(
            f"Du bist Owner von: {names}. Bitte übertrage zuerst die Ownership "
            "(Einstellungen → Organisation verwalten)."
        )
    Invitation.objects.filter(email__iexact=user.email).delete()
    user.delete()
