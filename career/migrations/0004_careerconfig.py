from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("career", "0003_delete_clustersubject_alter_course_cluster_subjects_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="CareerConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("best_match_max_diff", models.FloatField(
                    default=3.0,
                    help_text="Max points ABOVE cutoff for 'Best Match'. E.g. 3.0 means diff 0–3 = Best Match.",
                )),
                ("stretch_min_diff", models.FloatField(
                    default=-3.0,
                    help_text="Min points BELOW cutoff still counted as 'Stretch Opportunity' (enter as negative).",
                )),
                ("safe_max_diff", models.FloatField(
                    default=8.0,
                    help_text="Max points above cutoff for 'Safe Option'. Beyond this becomes 'Easy Admission'.",
                )),
            ],
            options={
                "verbose_name": "Career Recommendation Config",
                "verbose_name_plural": "Career Recommendation Config",
            },
        ),
    ]
