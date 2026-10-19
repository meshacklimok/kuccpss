from django.db import migrations


def seed(apps, schema_editor):
    SiteSetting = apps.get_model('resources', 'SiteSetting')
    SiteSetting.objects.get_or_create(
        key='paste_help_video_url',
        defaults={
            'label': 'How-to-paste video URL',
            'value': '',
            'setting_type': 'url',
            'group': 'media',
            'help_note': 'YouTube link or direct .mp4/.webm link shown on the "Paste cluster points" page. Blank hides the video.',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0025_seed_maintenance_setting'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
