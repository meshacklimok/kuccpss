# clusterpoints/models.py

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from math import sqrt

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

    class Meta:
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

    class Meta:
        ordering = ['-created_at']

    def recalc_total_points(self):
        """
        Correct KCSE total:
        1. Mathematics (compulsory)
        2. Best language (English/Kiswahili)
        3. Next 5 best subjects
        Total max = 84
        """
        points_dict = {sr.subject.name: sr.points for sr in self.subject_results.all()}

        aggregate_subjects = []

        # 1️⃣ Mathematics (compulsory)
        if "Mathematics" in points_dict:
            aggregate_subjects.append(points_dict.pop("Mathematics"))

        # 2️⃣ Best language (non-best language returns to pool for step 3)
        lang_points = {lang: points_dict.pop(lang) for lang in ["English", "Kiswahili"] if lang in points_dict}
        if lang_points:
            best_lang = max(lang_points, key=lambda k: lang_points[k])
            aggregate_subjects.append(lang_points[best_lang])
            for lang, pts in lang_points.items():
                if lang != best_lang:
                    points_dict[lang] = pts

        # 3️⃣ Next 5 best remaining subjects
        remaining_points = sorted(points_dict.values(), reverse=True)
        aggregate_subjects += remaining_points[:5]

        self.total_points = sum(aggregate_subjects)
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

    class Meta:
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

    class Meta:
        unique_together = ('user', 'kcse_result', 'cluster')
        ordering = ['cluster__number']

    def calculate_cluster_points(self):
        """
        Correct KCSE cluster calculation:
        - Core: 4 best subjects in cluster
        - Aggregate: total points from recalc_total_points()
        - Weighted formula
        """
        if not self.kcse_result:
            return 0.0

        points_dict = {sr.subject.name: sr.points for sr in self.kcse_result.subject_results.all()}

        # Required subjects
        required_subjects = Subject.objects.filter(
            subject_groups__cluster=self.cluster,
            subject_groups__required=True
        ).distinct()

        # Optional subjects
        optional_subjects = Subject.objects.filter(
            subject_groups__cluster=self.cluster,
            subject_groups__required=False
        ).distinct()

        # -----------------------
        # CORE SUBJECT TOTAL
        # -----------------------
        core_points_list = [points_dict.get(s.name, 0) for s in required_subjects]

        remaining_slots = 4 - len(core_points_list)
        optional_points = [points_dict.get(s.name, 0) for s in optional_subjects]
        core_points_list += sorted(optional_points, reverse=True)[:remaining_slots]

        if len(core_points_list) < 4:
            raw_core_total = sum(core_points_list)
            self.cluster_points = 0.0
        else:
            raw_core_total = min(sum(sorted(core_points_list, reverse=True)[:4]), 48)

        self.core_subject_total = raw_core_total

        # -----------------------
        # AGGREGATE TOTAL
        # -----------------------
        self.kcse_result.recalc_total_points()  # ensures total_points is correct
        self.aggregate_total = self.kcse_result.total_points

        # -----------------------
        # WEIGHTED CALCULATION
        # -----------------------
        if raw_core_total == 0 or self.aggregate_total == 0:
            weighted = 0.0
        else:
            weighted = 48 * sqrt((raw_core_total / 48) * (self.aggregate_total / 84))
        weighted = round(weighted, 2)

        self.cluster_points = weighted
        self.weighted_calculation = weighted

        # Track subjects used
        self.subjects_used.set(list(required_subjects) + list(optional_subjects))

        self.save()
        return weighted

    def __str__(self):
        return f"{self.cluster.name} - {self.cluster_points} pts"