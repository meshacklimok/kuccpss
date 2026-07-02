# clusterpoints/models.py

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

# Import the correct models from clusters app
from clusters.models import Cluster, Subject


# =====================================================
# ABSTRACT TIMESTAMP MODEL
# =====================================================
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# =====================================================
# GRADE → POINTS MAPPING
# =====================================================
class GradePoint(TimeStampedModel):
    grade = models.CharField(max_length=2, unique=True)
    points = models.PositiveIntegerField()

    class Meta:  # type: ignore[misc]
        ordering = ['-points']

    def __str__(self):
        return f"{self.grade} ({self.points})"


# =====================================================
# USER KCSE RESULT
# =====================================================
class UserKCSEResult(TimeStampedModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    mean_grade = models.CharField(
        max_length=2,
        blank=True,
        null=True
    )

    total_points = models.PositiveIntegerField(
        default=0,
        editable=False
    )

    class Meta:  # type: ignore[misc]
        ordering = ['-created_at']
        indexes = [models.Index(fields=["user", "created_at"])]

    def recalc_total_points(self):
        """KCSE aggregate total (max 84) — see clusterpoints.services.compute_aggregate_total."""
        from .services import compute_aggregate_total
        points_dict = {sr.subject.name: sr.points for sr in self.subject_results.all()}  # type: ignore[attr-defined]
        self.total_points = compute_aggregate_total(points_dict)
        self.save(update_fields=['total_points'])

    def __str__(self):
        return f"{self.user.email if self.user else 'Guest'} - {self.total_points} pts"


# =====================================================
# INDIVIDUAL SUBJECT RESULT
# =====================================================
class SubjectResult(TimeStampedModel):

    kcse_result = models.ForeignKey(
        UserKCSEResult,
        on_delete=models.CASCADE,
        related_name="subject_results"
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE
    )

    points = models.PositiveIntegerField()

    class Meta:  # type: ignore[misc]
        unique_together = ('kcse_result', 'subject')
        ordering = ['subject__name']

    def clean(self):
        if not 1 <= self.points <= 12:
            raise ValidationError("Points must be between 1 and 12.")

    def __str__(self):
        return f"{self.subject.name} - {self.points}"


# =====================================================
# CLUSTER CALCULATION RESULT
# =====================================================
class ClusterCalculationResult(TimeStampedModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    kcse_result = models.ForeignKey(
        UserKCSEResult,
        on_delete=models.CASCADE,
        related_name="cluster_results",
        null=True,
        blank=True
    )

    cluster = models.ForeignKey(
        Cluster,
        on_delete=models.CASCADE,
        related_name="calculation_results"
    )

    cluster_points = models.FloatField(default=0, editable=False)
    core_subject_total = models.PositiveIntegerField(default=0, editable=False)
    aggregate_total = models.PositiveIntegerField(default=0, editable=False)
    weighted_calculation = models.FloatField(default=0, editable=False)

    subjects_used = models.ManyToManyField(
        Subject,
        blank=True,
        related_name="used_in_cluster_results"
    )

    class Meta:  # type: ignore[misc]
        unique_together = ('user', 'kcse_result', 'cluster')
        ordering = ['cluster__number']
        indexes = [
            models.Index(fields=["user", "cluster"]),
            models.Index(fields=["kcse_result"]),
        ]

    def __str__(self):
        return f"{self.cluster.name} - {self.cluster_points} pts"