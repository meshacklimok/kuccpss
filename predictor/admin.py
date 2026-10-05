from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import PredictionConfig


@admin.register(PredictionConfig)
class PredictionConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Floor Settings — when blend predicts below last year", {
            "description": (
                "These control how much the prediction is pushed upward when the weighted average "
                "undershoots the latest known cutoff."
            ),
            "fields": ("rising_floor_multiplier", "rising_floor_cap", "stable_floor_offset"),
        }),
        ("Eligibility Band Width", {
            "description": (
                "The band width determines how wide the ± range is around the predicted cutoff. "
                "Wider = more courses show as Borderline. Narrower = stricter Likely/Unlikely split."
            ),
            "fields": ("band_multiplier",),
        }),
        ("Cohort Shift — set once the new KCSE results are out", {
            "description": (
                "Moves every predicted cutoff up or down by the same amount, for a year-wide change "
                "that past cutoffs can't show (e.g. a stronger or weaker KCSE cohort)."
            ),
            "fields": ("cohort_shift",),
        }),
    )

    def has_add_permission(self, request):
        return not PredictionConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        config = PredictionConfig.get()
        return HttpResponseRedirect(
            reverse("admin:predictor_predictionconfig_change", args=[config.pk])
        )
