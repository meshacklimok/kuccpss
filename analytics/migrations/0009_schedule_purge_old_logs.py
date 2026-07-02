from django.db import migrations


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model('django_q', 'Schedule')
    Schedule.objects.get_or_create(
        func='analytics.tasks.purge_old_logs',
        defaults={
            'name': 'Purge old analytics logs',
            'schedule_type': 'W',  # weekly
            'repeats': -1,
        },
    )


def remove_schedule(apps, schema_editor):
    Schedule = apps.get_model('django_q', 'Schedule')
    Schedule.objects.filter(func='analytics.tasks.purge_old_logs').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0008_rename_analytics_p_path_ca_idx_analytics_p_path_8a12c2_idx_and_more'),
        ('django_q', '0019_alter_task_options_alter_ormq_key_alter_ormq_lock_and_more'),
    ]

    operations = [
        migrations.RunPython(create_schedule, reverse_code=remove_schedule),
    ]
