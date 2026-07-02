from django.db import migrations


def seed_settings(apps, schema_editor):
    SiteSetting = apps.get_model('resources', 'SiteSetting')
    SiteSetting.objects.get_or_create(
        key='affiliate_min_withdrawal',
        defaults={
            'label':        'Affiliate Minimum Withdrawal (KES)',
            'value':        '500',
            'setting_type': 'number',
            'group':        'payouts',
            'help_note':    'Minimum wallet balance an affiliate must have before they can request a payout.',
        },
    )
    SiteSetting.objects.get_or_create(
        key='mentor_min_withdrawal',
        defaults={
            'label':        'Mentor Minimum Withdrawal (KES)',
            'value':        '100',
            'setting_type': 'number',
            'group':        'payouts',
            'help_note':    'Minimum wallet balance a mentor must have before they can request a payout.',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0009_seed_deadline_banner"),
    ]

    operations = [
        migrations.RunPython(seed_settings, reverse_code=migrations.RunPython.noop),
    ]
