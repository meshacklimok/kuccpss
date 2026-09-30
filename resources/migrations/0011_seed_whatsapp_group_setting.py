from django.db import migrations


def seed_settings(apps, schema_editor):
    SiteSetting = apps.get_model('resources', 'SiteSetting')
    SiteSetting.objects.get_or_create(
        key='whatsapp_group_url',
        defaults={
            'label':        'WhatsApp Group Link',
            'value':        '',
            'setting_type': 'url',
            'group':        'social',
            'help_note':    'Invite link, e.g. https://chat.whatsapp.com/XXXX. Leave blank to hide the WhatsApp icon in the footer.',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0010_seed_withdrawal_settings"),
    ]

    operations = [
        migrations.RunPython(seed_settings, reverse_code=migrations.RunPython.noop),
    ]
