from django.db import migrations


def seed_settings(apps, schema_editor):
    SiteSetting = apps.get_model('resources', 'SiteSetting')
    SiteSetting.objects.get_or_create(
        key='contact_phone',
        defaults={
            'label':        'Contact Phone Number',
            'value':        '+254768326532',
            'setting_type': 'phone',
            'group':        'contact',
            'help_note':    'Shown on the Privacy Policy contact section, e.g. +254712345678.',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0014_seed_calendar"),
    ]

    operations = [
        migrations.RunPython(seed_settings, reverse_code=migrations.RunPython.noop),
    ]
