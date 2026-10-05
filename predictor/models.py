from django.db import models


class PredictionConfig(models.Model):
    """
    Singleton configuration for the cutoff prediction engine.
    Only one row ever exists (pk=1). Edit via Django admin.
    """

    rising_floor_multiplier = models.FloatField(
        default=0.0,
        help_text=(
            "Rising courses: fraction of last year's gain added on top of the latest cutoff. "
            "0.0 (default, best in 2024/2025 backtest) holds at the latest cutoff; 0.50 adds 50% of the last gain. Range: 0.0 (no uplift) – 2.0 (double the gain)."
        ),
    )
    rising_floor_cap = models.FloatField(
        default=3.0,
        help_text=(
            "Rising courses: maximum points the floor can push above the latest cutoff. "
            "Prevents overshooting when one year had an unusually large jump."
        ),
    )
    stable_floor_offset = models.FloatField(
        default=0.0,
        help_text=(
            "Stable courses: flat points added above the latest cutoff when the blend undershoots. "
            "0.0 = predict exactly last year's value. Try 0.3–0.5 for a small uplift."
        ),
    )
    band_multiplier = models.FloatField(
        default=1.5,
        help_text=(
            "Eligibility band width multiplier applied to the ± variance around the prediction. "
            "1.0 = raw recent volatility. 1.5 (default) = 50% wider (more Borderline, fewer Unlikely). "
            "0.7 = narrower (tighter Likely/Unlikely split)."
        ),
    )

    cohort_shift = models.FloatField(
        default=0.0,
        help_text=(
            "Points added to every prediction (and floor) for the coming year, for a cohort-wide move "
            "history can't see. Set it when the new KCSE results are out: positive if more candidates "
            "scored C+ and above than last year (cutoffs rise), negative if fewer. Past moves: "
            "2023 −0.5, 2024 −0.8, 2025 +1.0. Range about −2 to +2; 0.0 = no adjustment."
        ),
    )

    class Meta:
        verbose_name = "Prediction Configuration"
        verbose_name_plural = "Prediction Configuration"

    def __str__(self):
        return "Prediction Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls) -> "PredictionConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
