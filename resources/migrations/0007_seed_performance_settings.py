from django.db import migrations


def seed_settings(apps, schema_editor):
    SiteSetting = apps.get_model('resources', 'SiteSetting')
    SiteSetting.objects.get_or_create(
        key='courses_per_page',
        defaults={
            'label':        'Courses Per Page',
            'value':        '24',
            'setting_type': 'number',
            'group':        'performance',
            'help_note':    'Number of courses shown per page in course listings and search results.',
        },
    )
    SiteSetting.objects.get_or_create(
        key='mentors_per_page',
        defaults={
            'label':        'Mentors Per Page',
            'value':        '18',
            'setting_type': 'number',
            'group':        'performance',
            'help_note':    'Number of mentors shown per page in the mentor directory.',
        },
    )
    SiteSetting.objects.get_or_create(
        key='trends_cache_ttl',
        defaults={
            'label':        'Homepage Trends Cache TTL (seconds)',
            'value':        '3600',
            'setting_type': 'number',
            'group':        'performance',
            'help_note':    'How long the homepage course-trends section is cached, in seconds. Default 3600 = 1 hour.',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0006_announcement_sitefeedback"),
    ]

    operations = [
        migrations.RunPython(seed_settings, reverse_code=migrations.RunPython.noop),
    ]
