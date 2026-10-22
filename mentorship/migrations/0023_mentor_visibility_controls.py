# Generated migration for mentor visibility controls

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mentorship', '0022_mentor_is_pinned'),
    ]

    operations = [
        migrations.AddField(
            model_name='mentorprofile',
            name='show_session_count',
            field=models.BooleanField(
                default=True,
                help_text="Display the number of completed sessions on this mentor's card and profile.",
            ),
        ),
        migrations.AddField(
            model_name='mentorprofile',
            name='show_rating',
            field=models.BooleanField(
                default=True,
                help_text="Display the average rating on this mentor's card and profile.",
            ),
        ),
    ]
