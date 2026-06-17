import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_savedcareer_career_profile_savedcareer_user_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="CareerSessionSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pathway", models.CharField(max_length=50)),
                ("cluster_points_json", models.JSONField(blank=True, default=dict)),
                ("mean_grade", models.CharField(blank=True, max_length=5)),
                ("aggregate_score", models.FloatField(blank=True, null=True)),
                ("total_matches", models.PositiveIntegerField(default=0)),
                ("tier_counts_json", models.JSONField(blank=True, default=dict)),
                ("top_matches_json", models.JSONField(blank=True, default=list)),
                ("computed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="career_snapshots",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Career Session Snapshot",
                "verbose_name_plural": "Career Session Snapshots",
                "ordering": ["-computed_at"],
            },
        ),
    ]
