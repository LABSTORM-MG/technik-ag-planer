from django.db import migrations

DEFAULT_CATEGORIES = [
    ("Schulfest", "yellow"),
    ("Theater", "pink"),
    ("Konzert", "blue"),
    ("Sonstiges", "grey"),
]
SYSTEM_STATUS = [
    ("planning", "In Planung", "orange"),
    ("confirmed", "Bestätigt", "green"),
]


def create_defaults(apps, schema_editor):
    """Standard-Kategorien und System-Status für AGs, die es schon vor M3 gab."""
    Organization = apps.get_model("organizations", "Organization")
    Category = apps.get_model("productions", "Category")
    ProductionStatus = apps.get_model("productions", "ProductionStatus")
    for org in Organization.objects.all():
        if not Category.objects.filter(organization=org).exists():
            for i, (name, color) in enumerate(DEFAULT_CATEGORIES):
                Category.objects.create(organization=org, name=name, color=color, position=i)
        for i, (key, name, color) in enumerate(SYSTEM_STATUS):
            ProductionStatus.objects.get_or_create(
                organization=org,
                system_key=key,
                defaults={"name": name, "color": color, "position": i},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
        ("productions", "0001_initial"),
    ]

    operations = [migrations.RunPython(create_defaults, migrations.RunPython.noop)]
