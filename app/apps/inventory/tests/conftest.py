import pytest

from apps.inventory.models import Kit, KitItem, Material, MaterialCategory


@pytest.fixture
def make_material():
    def factory(organization, name="Funkmikrofon", quantity=6, **extra):
        extra.setdefault("category", MaterialCategory.objects.for_org(organization).first())
        return Material.objects.create(
            organization=organization, name=name, quantity=quantity, **extra
        )

    return factory


@pytest.fixture
def make_kit():
    def factory(organization, name="Große Audioanlage", items=()):
        kit = Kit.objects.create(organization=organization, name=name)
        for material, quantity in items:
            KitItem.objects.create(
                organization=organization, kit=kit, material=material, quantity=quantity
            )
        return kit

    return factory


@pytest.fixture
def mics(org, make_material):
    return make_material(org)
