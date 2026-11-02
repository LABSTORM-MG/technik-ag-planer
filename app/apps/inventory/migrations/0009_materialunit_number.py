from django.db import migrations, models


def number_devices(apps, schema_editor):
    """Bestehende Geräte je Material in der Reihenfolge des Anlegens durchzählen."""
    MaterialUnit = apps.get_model("inventory", "MaterialUnit")
    counters = {}
    for unit in MaterialUnit.objects.order_by("material_id", "pk"):
        counters[unit.material_id] = counters.get(unit.material_id, 0) + 1
        unit.number = counters[unit.material_id]
        unit.save(update_fields=["number"])


class Migration(migrations.Migration):
    dependencies = [("inventory", "0008_reservierung_entfaellt")]

    operations = [
        migrations.AlterModelOptions(
            name="materialunit", options={"ordering": ["material_id", "number"]}
        ),
        migrations.AddField(
            model_name="materialunit",
            name="number",
            field=models.PositiveIntegerField(default=0, editable=False, verbose_name="Nummer"),
            preserve_default=False,
        ),
        migrations.RunPython(number_devices, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="materialunit",
            constraint=models.UniqueConstraint(
                fields=("material", "number"), name="material_unit_number_unique"
            ),
        ),
    ]
