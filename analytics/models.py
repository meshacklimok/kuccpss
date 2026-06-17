from django.db import models
from django.conf import settings


class SearchLog(models.Model):
    query        = models.CharField(max_length=300, db_index=True)
    result_count = models.PositiveSmallIntegerField(default=0)
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+')
    session_key  = models.CharField(max_length=40, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['query']), models.Index(fields=['created_at'])]

    def __str__(self):
        return f'"{self.query}" ({self.result_count} results)'


class ViewLog(models.Model):
    TYPE_CHOICES = [
        ('course',         'Course'),
        ('institution',    'Institution'),
        ('career_profile', 'Career Profile'),
        ('resource',       'Resource'),
        ('article',        'Article'),
    ]
    content_type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    object_id    = models.PositiveIntegerField()
    object_name  = models.CharField(max_length=250, blank=True)
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+')
    session_key  = models.CharField(max_length=40, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.content_type}: {self.object_name}'


class DownloadLog(models.Model):
    TYPE_CHOICES = [
        ('resource_pdf',    'Resource PDF'),
        ('course_pdf',      'Course PDF'),
        ('institution_pdf', 'Institution PDF'),
        ('career_pdf',      'Career Engine PDF'),
        ('cluster_pdf',     'Cluster Points PDF'),
    ]
    content_type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    object_id    = models.PositiveIntegerField(null=True, blank=True)
    object_name  = models.CharField(max_length=250, blank=True)
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+')
    session_key  = models.CharField(max_length=40, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['content_type']), models.Index(fields=['created_at'])]

    def __str__(self):
        return f'{self.content_type}: {self.object_name}'


class CareerEngineLog(models.Model):
    PATHWAY_CHOICES = [
        ('degree',      'Degree'),
        ('diploma',     'Diploma'),
        ('kmtc',        'KMTC'),
        ('certificate', 'Certificate'),
        ('artisan',     'Artisan'),
        ('ttc',         'TTC'),
        ('shortcourse', 'Short Course'),
    ]
    pathway      = models.CharField(max_length=20, choices=PATHWAY_CHOICES, db_index=True)
    result_count = models.PositiveSmallIntegerField(default=0)
    mean_grade   = models.CharField(max_length=5, blank=True)
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+')
    session_key  = models.CharField(max_length=40, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['pathway', 'created_at'])]

    def __str__(self):
        return f'{self.pathway} — {self.result_count} matches'
