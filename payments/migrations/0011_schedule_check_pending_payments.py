from django.db import migrations


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model('django_q', 'Schedule')
    Schedule.objects.get_or_create(
        func='payments.tasks.check_pending_payments',
        defaults={
            'name': 'Mark stale pending payments as failed',
            'schedule_type': 'H',  # hourly
            'repeats': -1,
        },
    )


def remove_schedule(apps, schema_editor):
    Schedule = apps.get_model('django_q', 'Schedule')
    Schedule.objects.filter(func='payments.tasks.check_pending_payments').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0010_payment_mentorship_session_alter_payment_feature_and_more'),
        ('django_q', '0019_alter_task_options_alter_ormq_key_alter_ormq_lock_and_more'),
    ]

    operations = [
        migrations.RunPython(create_schedule, reverse_code=remove_schedule),
    ]
