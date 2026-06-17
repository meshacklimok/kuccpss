from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PredictionConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rising_floor_multiplier", models.FloatField(
                    default=0.5,
                    help_text="Rising courses: fraction of last year's gain added on top of the latest cutoff. 0.50 means add 50% of the last gain. Range: 0.0 (no uplift) – 2.0 (double the gain).",
                )),
                ("rising_floor_cap", models.FloatField(
                    default=3.0,
                    help_text="Rising courses: maximum points the floor can push above the latest cutoff. Prevents overshooting when one year had an unusually large jump.",
                )),
                ("stable_floor_offset", models.FloatField(
                    default=0.0,
                    help_text="Stable courses: flat points added above the latest cutoff when the blend undershoots. 0.0 = predict exactly last year's value. Try 0.3–0.5 for a small uplift.",
                )),
                ("band_multiplier", models.FloatField(
                    default=1.0,
                    help_text="Eligibility band width multiplier applied to the ± variance around the prediction. 1.0 = default width. 1.5 = 50% wider (more Borderline, fewer Unlikely). 0.7 = narrower.",
                )),
            ],
            options={
                "verbose_name": "Prediction Configuration",
                "verbose_name_plural": "Prediction Configuration",
            },
        ),
    ]
