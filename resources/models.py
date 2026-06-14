from django.db import models
from django.utils.text import slugify


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

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
