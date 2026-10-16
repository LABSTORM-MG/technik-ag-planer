"""Datenexport einer AG für den Betreiber (Django-Admin): ZIP mit einer JSON-Datei je Datenart.

Spätere Meilensteine tragen ihre AG-Daten hier ein: export.register(Model).
"""

import io
import json
import zipfile

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

_registry = {}

USER_FIELDS = ["id", "email", "display_name", "grade", "date_joined", "is_active"]


def register(model, *, exclude=()):
    _registry[model] = set(exclude)
    return model


def _rows(queryset, exclude):
    fields = [f for f in queryset.model._meta.concrete_fields if f.name not in exclude]
    return [{f.name: f.value_from_object(obj) for f in fields} for obj in queryset]


def export_organization(organization) -> bytes:
    from .models import Membership

    files = {
        "ag.json": {
            "id": organization.pk,
            "name": organization.name,
            "is_active": organization.is_active,
            "require_2fa": organization.require_2fa,
            "created_at": organization.created_at,
            "exportiert_am": timezone.now(),
        },
        "konten.json": [
            {field: getattr(m.user, field) for field in USER_FIELDS}
            for m in Membership.objects.for_org(organization).select_related("user")
        ],
    }
    for model, exclude in _registry.items():
        name = f"{model._meta.app_label}_{model._meta.model_name}.json"
        files[name] = _rows(model.objects.for_org(organization).order_by("pk"), exclude)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(
                name, json.dumps(content, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)
            )
    return buffer.getvalue()
