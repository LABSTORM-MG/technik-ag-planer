"""Registrierung von Modellen für das Änderungsprotokoll.

register(Model)                          # AG über Feld `organization`
register(Model, organization="self")     # das Objekt ist selbst die AG
register(Model, organization=None)       # nicht AG-bezogen (z. B. Konten)
register(Model, exclude=["feld"])        # Felder nicht protokollieren
"""

import json
from dataclasses import dataclass, field

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.signals import post_delete, post_save, pre_save

from .context import get_current_user

# Felder mit diesen Namensteilen landen nie im Protokoll
SENSITIVE_PARTS = ("password", "token", "secret", "key")


@dataclass
class Options:
    exclude: set = field(default_factory=set)
    organization: str | None = "organization"


_registry = {}


def register(model, *, exclude=(), organization="organization"):
    _registry[model] = Options(exclude=set(exclude), organization=organization)
    uid = f"audit-{model._meta.label}"
    pre_save.connect(_remember_old_values, sender=model, dispatch_uid=f"{uid}-pre")
    post_save.connect(_log_save, sender=model, dispatch_uid=f"{uid}-post")
    post_delete.connect(_log_delete, sender=model, dispatch_uid=f"{uid}-delete")
    return model


def is_registered(model):
    return model in _registry


def _tracked_fields(model):
    options = _registry[model]
    for f in model._meta.concrete_fields:
        if f.name in options.exclude or any(part in f.name for part in SENSITIVE_PARTS):
            continue
        yield f


def _snapshot(instance):
    values = {f.name: f.value_from_object(instance) for f in _tracked_fields(type(instance))}
    return json.loads(json.dumps(values, cls=DjangoJSONEncoder))


def _remember_old_values(sender, instance, raw=False, **kwargs):
    if raw or instance._state.adding or instance.pk is None:
        instance._audit_old = None
        return
    old = sender._default_manager.filter(pk=instance.pk).first()
    instance._audit_old = _snapshot(old) if old else None


def _organization_of(instance):
    path = _registry[type(instance)].organization
    if path is None:
        return None
    if path == "self":
        return instance
    return getattr(instance, path, None)


def _write(instance, action, changes):
    from .models import AuditEntry

    actor = get_current_user()
    organization = _organization_of(instance)
    # Bei Löschungen nur den Namen merken: Die AG kann im selben Vorgang mitgelöscht werden.
    link_org = organization is not None and action != AuditEntry.Action.DELETE
    link_actor = actor is not None and actor.pk is not None and action != AuditEntry.Action.DELETE

    AuditEntry.objects.create(
        actor=actor if link_actor else None,
        actor_label=str(actor) if actor is not None else "System",
        organization=organization if link_org else None,
        organization_label=str(organization) if organization is not None else "",
        action=action,
        object_type=instance._meta.verbose_name,
        object_id=str(instance.pk),
        object_repr=str(instance)[:255],
        changes=changes,
    )


def _log_save(sender, instance, created, raw=False, **kwargs):
    from .models import AuditEntry

    if raw:
        return
    new = _snapshot(instance)
    if created:
        _write(instance, AuditEntry.Action.CREATE, {k: [None, v] for k, v in new.items()})
        return
    old = getattr(instance, "_audit_old", None) or {}
    changes = {k: [old.get(k), v] for k, v in new.items() if old.get(k) != v}
    if changes:
        _write(instance, AuditEntry.Action.UPDATE, changes)


def _log_delete(sender, instance, **kwargs):
    from .models import AuditEntry

    _write(instance, AuditEntry.Action.DELETE, {})
