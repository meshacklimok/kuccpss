from datetime import date

from django.db import models
from django.urls import reverse
from django.utils.text import slugify

class InstitutionType(models.Model):
    """
    Top-level types of institutions: Public University, Private University, KMTC, TVET, TTC, Specialized Schools
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="FontAwesome icon for UI cards")
    color_code = models.CharField(max_length=7, blank=True, null=True, help_text="Hex color for UI display")

    class Meta:
        verbose_name = "Institution Type"
        verbose_name_plural = "Institution Types"
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

    _BG_MAP = {
        '#1d4ed8': '#eff6ff',
        '#7c3aed': '#f5f3ff',
        '#dc2626': '#fef2f2',
        '#d97706': '#fffbeb',
        '#059669': '#ecfdf5',
    }

    def display_icon(self):
        return self.icon or "fa-solid fa-university"

    def display_color(self):
        return self.color_code or "#2c3e50"

    @property
    def bg_color(self):
        return self._BG_MAP.get(self.color_code, '#f8fafc')


class Institution(models.Model):
    """
    Individual institution linked to an InstitutionType.
    Includes PDFs for brochures, admission requirements, or programs.
    Note: slug auto-generates from name with collision handling.
    """
    name = models.CharField(max_length=200)
    abbreviation = models.CharField(max_length=20, blank=True, help_text="Short code, e.g. UoN, KU, JKUAT")
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    institution_type = models.ForeignKey(InstitutionType, on_delete=models.CASCADE, related_name='institutions')
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True, help_text="City, County, etc.")
    website = models.URLField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    logo = models.ImageField(upload_to="institution_logos/", blank=True, null=True)
    pdf_file = models.FileField(upload_to="institution_pdfs/", blank=True, null=True, help_text="Upload PDF brochure or requirements")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['institution_type', 'name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:110]
            slug = base
            n = 1
            qs = Institution.objects.exclude(pk=self.pk) if self.pk else Institution.objects.all()
            while qs.filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.institution_type.name})"

    # --- Helper methods for templates ---
    def display_logo(self):
        if self.logo:
            return self.logo.url
        return "/static/images/default_institution.png"  # Optional default logo

    def display_pdf(self):
        if self.pdf_file:
            return self.pdf_file.url
        return None

    def get_absolute_url(self):
        return reverse(
            "institutions:institution_detail",
            kwargs={"type_slug": self.institution_type.slug, "institution_slug": self.slug},
        )


class InstitutionPromotion(models.Model):
    TIER_FEATURED = 'featured'
    TIER_SCHOLARSHIP = 'scholarship'
    TIER_COURSE_SPOTLIGHT = 'course_spotlight'
    TIER_CHOICES = [
        (TIER_FEATURED, 'Featured Partner'),
        (TIER_SCHOLARSHIP, 'Scholarship Alert'),
        (TIER_COURSE_SPOTLIGHT, 'Sponsored Course Listing'),
    ]

    PATHWAY_ALL = 'all'
    PATHWAY_CHOICES = [
        ('all',     'All Pathways'),
        ('Degree',  'Degree (University)'),
        ('Diploma', 'Diploma'),
        ('KMTC',    'KMTC'),
        ('TVET',    'TVET'),
        ('TTC',     'TTC'),
    ]

    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name='promotions'
    )
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default=TIER_FEATURED)
    tagline = models.CharField(max_length=200, blank=True, help_text="Short marketing message shown on the platform")
    banner_image = models.ImageField(upload_to='institution_banners/', blank=True, null=True)

    # For course_spotlight tier — highlight a specific course in career results
    featured_course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sponsorships',
        help_text="The specific course to spotlight in career results (course_spotlight tier only)",
    )
    pathway = models.CharField(
        max_length=20, choices=PATHWAY_CHOICES, default=PATHWAY_ALL,
        help_text="Which career pathway to show this sponsored listing in (course_spotlight tier)",
    )

    # Scholarship-specific
    scholarship_title = models.CharField(max_length=200, blank=True)
    scholarship_description = models.TextField(blank=True)
    scholarship_amount = models.CharField(max_length=100, blank=True, help_text="e.g. Full tuition, KES 50,000")
    scholarship_deadline = models.DateField(blank=True, null=True)
    scholarship_link = models.URLField(blank=True, null=True, help_text="External apply/learn-more link")

    # Campaign window
    start_date = models.DateField()
    end_date = models.DateField()

    # Internal deal tracking
    contact_name = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True, help_text="Internal notes about this partnership deal")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Institution Promotion'
        verbose_name_plural = 'Institution Promotions'
        ordering = ['end_date']

    def __str__(self):
        return f"{self.institution.name} — {self.get_tier_display()} ({self.start_date} → {self.end_date})"

    @property
    def is_live(self):
        today = date.today()
        return self.start_date <= today <= self.end_date

    @property
    def days_remaining(self):
        return max(0, (self.end_date - date.today()).days)

    @property
    def scholarship_deadline_soon(self):
        if not self.scholarship_deadline:
            return False
        return (self.scholarship_deadline - date.today()).days <= 14