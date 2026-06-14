from django.db import models
from django.utils.text import slugify
from clusters.models import Cluster
from institutions.models import Institution

class CourseType(models.Model):
    """
    Top-level course type: Degree, Diploma, KMTC, TTC, Short Courses, Artisan Certificate, etc.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="Optional icon for UI cards")
    color_code = models.CharField(max_length=7, blank=True, null=True, help_text="Optional hex color for UI")

    class Meta:
        verbose_name = "Course Type"
        verbose_name_plural = "Course Types"
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def display_color(self):
        return self.color_code or "#3498db"

    def display_icon(self):
        return self.icon or "fa-solid fa-book"

class CourseCategory(models.Model):
    """
    Subcategory for Degree/Diploma: Tech, Health, etc.
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    course_type = models.ForeignKey(CourseType, on_delete=models.CASCADE, related_name='categories')
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ('name', 'course_type')
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.course_type.name} → {self.name}"

class Course(models.Model):
    """
    Individual course.
    University courses may link to a cluster.
    """
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    course_type = models.ForeignKey(CourseType, on_delete=models.CASCADE)
    category = models.ForeignKey(CourseCategory, on_delete=models.SET_NULL, null=True, blank=True)
    institutions = models.ManyToManyField(Institution, through='CourseOffering', blank=True)
    cluster = models.ForeignKey(Cluster, on_delete=models.SET_NULL, null=True, blank=True, help_text="Only for university courses")
    core_subjects = models.ManyToManyField('clusters.Subject', blank=True, related_name='courses')
    description = models.TextField(blank=True)
    cutoff_points = models.JSONField(blank=True, null=True, help_text='Example: {"2024": 65, "2023": 62}')
    minimum_mean_grade = models.CharField(max_length=5, blank=True, help_text='e.g. C, C-, D+')
    subject_requirements = models.JSONField(
        blank=True, null=True,
        help_text='[{"slot":1,"subjects_str":"ENG/KIS","min_grade":"C"}, ...]'
    )
    pdf_file = models.FileField(upload_to="course_pdfs/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['course_type', 'category', 'name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:110]
            slug = base
            n = 1
            qs = Course.objects.exclude(pk=self.pk) if self.pk else Course.objects.all()
            while qs.filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def is_university_course(self):
        return self.cluster is not None


class CourseOffering(models.Model):
    """
    Links a Course to an Institution with institution-specific cutoff points.
    This is the correct representation of KUCCPS data where the same course
    has different cutoff points at different universities.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='offerings')
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='offerings')
    programme_code = models.CharField(max_length=20, blank=True, help_text='KUCCPS code e.g. 5000K32')
    cutoff_points = models.JSONField(
        blank=True, null=True,
        help_text='Per-institution cutoffs. Example: {"2024": 78.5, "2023": 76.2}'
    )

    class Meta:
        unique_together = ('course', 'institution')
        ordering = ['institution__name']
        verbose_name = "Course Offering"
        verbose_name_plural = "Course Offerings"

    def __str__(self):
        return f"{self.course.name} @ {self.institution.name}"

    def latest_cutoff(self):
        if not self.cutoff_points:
            return None
        years = sorted(self.cutoff_points.keys(), reverse=True)
        return self.cutoff_points.get(years[0]) if years else None