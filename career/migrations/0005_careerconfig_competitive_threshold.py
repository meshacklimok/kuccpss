from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("career", "0004_careerconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="careerconfig",
            name="competitive_threshold",
            field=models.FloatField(
                default=40.0,
                help_text="Courses whose cutoff is at or above this value are flagged 'Competitive'. Applies to Degree pathway (cluster points out of 48). Default: 40.0.",
            ),
        ),
    ]
