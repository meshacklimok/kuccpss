from django.db import migrations


def seed(apps, schema_editor):
    SiteSetting = apps.get_model('resources', 'SiteSetting')
    SiteSetting.objects.get_or_create(
        key='maintenance_mode',
        defaults={
            'label': 'Maintenance mode',
            'value': 'off',
            'group': 'system',
            'help_note': 'on = site offline for everyone except staff; off = live',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0024_kmtc_tvet_intakes_all_cycles'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
