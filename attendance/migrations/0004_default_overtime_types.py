from django.db import migrations

DEFAULT_TYPES = [
    # (code, libellé, majoration %) — valeurs indicatives, à valider avec la convention collective
    ('HS15', 'De la 41e à la 48e heure', 15),
    ('HS40', 'Au-delà de la 48e heure', 40),
    ('HSN', 'Heures de nuit', 60),
    ('HSD', 'Dimanche et jours fériés', 60),
]


def create_default_types(apps, schema_editor):
    overtime_type = apps.get_model('attendance', 'OvertimeType')
    if overtime_type.objects.exists():
        return
    for order, (code, name, rate) in enumerate(DEFAULT_TYPES, start=1):
        overtime_type.objects.create(code=code, name=name, increase_rate=rate, order=order)


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0003_overtimetype_overtimeentry'),
    ]

    operations = [
        migrations.RunPython(create_default_types, migrations.RunPython.noop),
    ]
