from django.db import models
from django.utils.text import slugify


# ──────────────────────────────────────────────────────
# Site-wide key-value settings (contact info, hero text, social links …)
# ──────────────────────────────────────────────────────
class SiteSetting(models.Model):
    TYPE_CHOICES = [
        ('text',     'Short Text'),
        ('textarea', 'Long Text'),
        ('url',      'URL'),
        ('email',    'Email'),
        ('phone',    'Phone / WhatsApp'),
        ('number',   'Number'),
    ]

    key          = models.CharField(max_length=100, unique=True,
                                    help_text="Unique key used in views/templates")
    label        = models.CharField(max_length=200, help_text="Human-readable label")
    value        = models.TextField(blank=True)
    setting_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='text')
    group        = models.CharField(max_length=50, default='general',
                                    help_text="Group name for admin display (e.g. contact, social, hero)")
    help_note    = models.CharField(max_length=300, blank=True,
                                    help_text="Extra hint for the admin editing this value")

    class Meta:
        ordering = ['group', 'key']
        verbose_name        = 'Site Setting'
        verbose_name_plural = 'Site Settings'
        indexes = [models.Index(fields=["group"])]

    def __str__(self):
        return f"{self.label} ({self.key})"

    @classmethod
    def get(cls, key, default=''):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default


# ──────────────────────────────────────────────────────
# FAQ items
# ──────────────────────────────────────────────────────
class FAQItem(models.Model):
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('cluster', 'Cluster Points'),
        ('courses', 'Courses & Pathways'),
        ('kuccps',  'KUCCPS Process'),
        ('account', 'My Account'),
    ]

    question   = models.CharField(max_length=400)
    answer     = models.TextField()
    category   = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    order      = models.PositiveIntegerField(default=0,
                                             help_text="Lower numbers appear first within each category")
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'order', 'id']
        verbose_name        = 'FAQ Item'
        verbose_name_plural = 'FAQ Items'
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"[{self.get_category_display()}] {self.question[:70]}"


# ──────────────────────────────────────────────────────
# Student success stories (public home page)
# ──────────────────────────────────────────────────────
class SuccessStory(models.Model):
    PATHWAY_CHOICES = [
        ('degree',  'Degree'),
        ('kmtc',    'KMTC'),
        ('tvet',    'TVET / Polytechnic'),
        ('ttc',     'TTC'),
        ('diploma', 'Diploma'),
        ('artisan', 'Artisan Certificate'),
    ]

    name          = models.CharField(max_length=100)
    initials      = models.CharField(max_length=4, blank=True,
                                     help_text="2-letter avatar initials — auto-filled from name if blank")
    county        = models.CharField(max_length=80, blank=True, help_text="Home county, e.g. Kiambu County")
    work_location = models.CharField(max_length=100, blank=True,
                                     help_text="City/region where they work now, e.g. Nairobi")
    kcse_grade    = models.CharField(max_length=4, blank=True, help_text="Mean grade, e.g. A-, C+, B")
    quote         = models.TextField(help_text="Their testimonial in their own words")
    course_name   = models.CharField(max_length=200)
    institution   = models.CharField(max_length=200)
    pathway       = models.CharField(max_length=20, choices=PATHWAY_CHOICES, default='degree')
    year          = models.PositiveIntegerField(blank=True, null=True, help_text="Graduation year")
    avatar_bg     = models.CharField(max_length=20, default='#eef2ff',
                                     help_text="Avatar background colour (hex)")
    avatar_color  = models.CharField(max_length=20, default='#4f46e5',
                                     help_text="Avatar text colour (hex)")
    order         = models.PositiveIntegerField(default=0)
    is_active     = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name        = 'Success Story'
        verbose_name_plural = 'Success Stories'
        indexes = [models.Index(fields=["is_active", "pathway"])]

    def save(self, *args, **kwargs):
        if not self.initials:
            parts = self.name.split()
            self.initials = ''.join(p[0].upper() for p in parts[:2])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} — {self.course_name}"


class ResourceCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="FontAwesome icon class")
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Resource Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Resource(models.Model):
    TYPE_CHOICES = [
        ("pdf", "PDF Guide"),
        ("video", "Video"),
        ("link", "External Link"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.ForeignKey(
        ResourceCategory, on_delete=models.CASCADE, related_name="resources"
    )
    resource_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="pdf")
    description = models.TextField(blank=True)
    pdf_file = models.FileField(upload_to="resources/pdfs/", blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to="resources/thumbnails/", blank=True, null=True)
    is_free = models.BooleanField(default=True)
    download_count = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resource_type", "is_free"]),
            models.Index(fields=["category"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug = base
            counter = 1
            while Resource.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def increment_download(self):
        Resource.objects.filter(pk=self.pk).update(download_count=models.F("download_count") + 1)


class Article(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    author = models.CharField(max_length=100, blank=True)
    excerpt = models.CharField(max_length=300, blank=True)
    content = models.TextField()
    thumbnail = models.ImageField(upload_to="articles/thumbnails/", blank=True, null=True)
    tags = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated tags, e.g. career,university,tips"
    )
    is_published = models.BooleanField(default=True)
    featured = models.BooleanField(default=False, help_text="Pin as the featured headline article")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_published", "featured"]),
            models.Index(fields=["is_published"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug = base
            counter = 1
            while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_tags_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def reading_time(self):
        words = len(self.content.split())
        minutes = max(1, round(words / 200))
        return minutes


# ──────────────────────────────────────────────────────
# Site-wide announcements (admin-published banners)
# ──────────────────────────────────────────────────────
class Announcement(models.Model):
    TYPE_CHOICES = [
        ('info',    'Info (blue)'),
        ('success', 'Success (green)'),
        ('warning', 'Warning (yellow)'),
        ('danger',  'Alert (red)'),
    ]

    title      = models.CharField(max_length=200)
    body       = models.TextField(help_text="Short announcement text shown to users")
    link_url   = models.URLField(blank=True, help_text="Optional call-to-action URL")
    link_label = models.CharField(max_length=60, blank=True, help_text="Button label for the link")
    kind       = models.CharField(max_length=10, choices=TYPE_CHOICES, default='info')
    is_active  = models.BooleanField(default=True)
    starts_at  = models.DateTimeField(null=True, blank=True, help_text="Leave blank to show immediately")
    ends_at    = models.DateTimeField(null=True, blank=True, help_text="Leave blank to show indefinitely")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Announcement'
        verbose_name_plural = 'Announcements'
        indexes = [models.Index(fields=['is_active'])]

    def __str__(self):
        return self.title


# ──────────────────────────────────────────────────────
# User-submitted site feedback
# ──────────────────────────────────────────────────────
class SiteFeedback(models.Model):
    TYPE_CHOICES = [
        ('bug',        'Bug Report'),
        ('suggestion', 'Feature Suggestion'),
        ('general',    'General Feedback'),
        ('content',    'Content Error'),
    ]
    STATUS_CHOICES = [
        ('new',        'New'),
        ('reviewing',  'Reviewing'),
        ('resolved',   'Resolved'),
        ('dismissed',  'Dismissed'),
    ]

    feedback_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='general')
    message       = models.TextField(max_length=2000)
    email         = models.EmailField(blank=True, help_text="Optional — for follow-up")
    page_url      = models.CharField(max_length=300, blank=True, help_text="Page where feedback was submitted")
    status        = models.CharField(max_length=12, choices=STATUS_CHOICES, default='new')
    admin_note    = models.TextField(blank=True, help_text="Internal note")
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Site Feedback'
        verbose_name_plural = 'Site Feedback'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['feedback_type', 'status']),
        ]

    def __str__(self):
        return f"[{self.get_feedback_type_display()}] {self.message[:60]}"
