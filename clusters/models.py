from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError

from .constants import KUCCPS_CLUSTER_NUMBERS, NUM_KUCCPS_CLUSTERS


# ============================================================
# ABSTRACT BASE MODEL (Reusable Timestamp Model)
# ============================================================

from kuccpss.upload_validators import SafeImageValidator

class TimeStampedModel(models.Model):
    """
    Abstract base model that provides:
    - created_at
    - updated_at
    """

    created_at = models.DateTimeField(
        default=timezone.now,
        editable=False
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        abstract = True


# ============================================================
# SUBJECT MODEL
# ============================================================

GROUP_CHOICES = [
    ('I',   'Group I – Compulsory'),
    ('II',  'Group II – Sciences'),
    ('III', 'Group III – Humanities'),
    ('IV',  'Group IV – Technical & Applied'),
    ('V',   'Group V – Languages, Business & Music'),
]


class Subject(TimeStampedModel):
    """
    Represents a KCSE subject.
    Example: English, Kiswahili, Mathematics, History, CRE, etc.
    """

    name = models.CharField(
        max_length=100,
        unique=True
    )

    code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Optional subject code (for future integration)"
    )

    group = models.CharField(
        max_length=4,
        choices=GROUP_CHOICES,
        blank=True,
        default='',
        help_text="KUCCPS subject group (I–V)"
    )

    class Meta:  # type: ignore[misc]
        ordering = ['group', 'name']
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"
        indexes = [
            models.Index(fields=['group']),
        ]

    def __str__(self):
        return self.name


# ============================================================
# CLUSTER MODEL
# ============================================================

class ClusterQuerySet(models.QuerySet):
    def kuccps(self):
        """The 18 KUCCPS clusters (rows 101–118) — use this wherever clusters are listed or scored."""
        return self.filter(number__in=KUCCPS_CLUSTER_NUMBERS)


class Cluster(TimeStampedModel):
    objects = ClusterQuerySet.as_manager()

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Example: Education, Engineering, Health Sciences"
    )

    slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True
    )

    description = models.TextField(blank=True)

    color_code = models.CharField(max_length=7, blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    image = models.ImageField(upload_to='cluster_images/', blank=True, null=True, validators=[SafeImageValidator()])

    number = models.PositiveIntegerField(
        unique=True,
        blank=True,
        null=True,
        help_text="Cluster number (used for ordering or official identification)"
    )

    class Meta:  # type: ignore[misc]
        ordering = ['number', 'name']
        verbose_name = "Cluster"
        verbose_name_plural = "Clusters"

    # Auto-generate slug & number
    @property
    def kuccps_number(self):
        """
        Return the KUCCPS cluster number (1-18) for this cluster.
        Clusters 101-118: kuccps_number = number - 100 (see clusters/constants.py).
        Legacy fallback: parse a name like 'Medicine (13A)' → 13.
        """
        if self.number and self.number > 100:
            return self.number - 100
        import re
        m = re.search(r'\((\d+)[A-Za-z]*\)', self.name)
        return int(m.group(1)) if m else self.number

    def save(self, *args, **kwargs):
        # Auto-generate slug
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Cluster.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        # Auto-assign the first free KUCCPS slot (101–118) if missing
        if self.number is None:
            self.number = self._free_number()
        if self.number not in KUCCPS_CLUSTER_NUMBERS:
            raise ValidationError(
                f'There are exactly {NUM_KUCCPS_CLUSTERS} KUCCPS clusters; '
                f'number must be {KUCCPS_CLUSTER_NUMBERS[0]}–{KUCCPS_CLUSTER_NUMBERS[-1]}.'
            )

        super().save(*args, **kwargs)

    def _free_number(self):
        taken = set(Cluster.objects.exclude(pk=self.pk).values_list('number', flat=True))
        return next((n for n in KUCCPS_CLUSTER_NUMBERS if n not in taken), None)

    def clean(self):
        super().clean()
        number = self.number if self.number is not None else self._free_number()
        if number not in KUCCPS_CLUSTER_NUMBERS:
            raise ValidationError({'number': (
                f'There are exactly {NUM_KUCCPS_CLUSTERS} KUCCPS clusters; '
                f'number must be {KUCCPS_CLUSTER_NUMBERS[0]}–{KUCCPS_CLUSTER_NUMBERS[-1]} '
                f'(KUCCPS cluster number + 100).'
            )})

    def get_absolute_url(self):
        return reverse("clusters:cluster_detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.name

# ============================================================
# SUBJECT GROUP MODEL
# ============================================================

class SubjectGroup(TimeStampedModel):
    """
    Represents a subject selection group inside a cluster.

    Example:

        Humanities Group:
            History
            CRE
            Geography

        Language Group:
            English
            Kiswahili
    """

    cluster = models.ForeignKey(
        Cluster,
        on_delete=models.CASCADE,
        related_name="subject_groups"
    )

    name = models.CharField(
        max_length=100
    )

    subjects = models.ManyToManyField(
        Subject,
        related_name="subject_groups"
    )

    required = models.BooleanField(
        default=True,
        help_text="If True, best subject from this group must be included"
    )

    priority = models.PositiveIntegerField(
        default=1,
        help_text="Lower number = higher priority"
    )

    class Meta:  # type: ignore[misc]
        ordering = ['priority', 'name']
        verbose_name = "Subject Group"
        verbose_name_plural = "Subject Groups"
        indexes = [
            models.Index(fields=['priority']),
        ]

    def __str__(self):
        return f"{self.cluster.name} - {self.name}"