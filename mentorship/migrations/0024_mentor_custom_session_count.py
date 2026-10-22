from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mentorship', '0023_mentor_visibility_controls'),
    ]

    operations = [
        migrations.AddField(
            model_name='mentorprofile',
            name='custom_session_count',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text="Unused: the public session count is always the real number of completed sessions.",
            ),
        ),
    ]
