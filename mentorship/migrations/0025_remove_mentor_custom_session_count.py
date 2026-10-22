from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mentorship', '0024_mentor_custom_session_count'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mentorprofile',
            name='custom_session_count',
        ),
    ]
