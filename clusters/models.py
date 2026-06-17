from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.utils import timezone


# ============================================================
# ABSTRACT BASE MODEL (Reusable Timestamp Model)
# ============================================================

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

    class Meta:
        ordering = ['group', 'name']
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['group']),
        ]

    def __str__(self):
        return self.name


# ============================================================
# CLUSTER MODEL
# ============================================================

class Cluster(TimeStampedModel):
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
    image = models.ImageField(upload_to='cluster_images/', blank=True, null=True)

    number = models.PositiveIntegerField(
        unique=True,
        blank=True,
        null=True,
        help_text="Cluster number (used for ordering or official identification)"
    )

    class Meta:
        ordering = ['number', 'name']
        verbose_name = "Cluster"
        verbose_name_plural = "Clusters"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
            models.Index(fields=['number']),
        ]

    # Auto-generate slug & number
    @property
    def kuccps_number(self):
        """
        Return the KUCCPS group number (1-20) for this cluster.
        Master clusters (number 101-120): kuccps_group = number - 100.
        Sub-clusters: parse from name pattern like 'Medicine (13A)' → 13.
        """
        if self.number and 101 <= self.number <= 120:
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

        # Auto-assign number if missing
        if self.number is None:
            last_number = Cluster.objects.aggregate(models.Max('number'))['number__max'] or 0
            self.number = last_number + 1

        super().save(*args, **kwargs)

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

    class Meta:
        ordering = ['priority', 'name']
        verbose_name = "Subject Group"
        verbose_name_plural = "Subject Groups"
        indexes = [
            models.Index(fields=['priority']),
        ]

    def __str__(self):
        return f"{self.cluster.name} - {self.name}"