from django.db import models
from django.conf import settings


class PageViewLog(models.Model):
    """Auto-recorded by PageTrackingMiddleware for every non-static page hit."""
    DEVICE_CHOICES = [
        ('mobile',  'Mobile'),
        ('tablet',  'Tablet'),
        ('desktop', 'Desktop'),
        ('bot',     'Bot / Crawler'),
        ('unknown', 'Unknown'),
    ]
    path             = models.CharField(max_length=500, db_index=True)
    method           = models.CharField(max_length=10, default='GET')
    status_code      = models.PositiveSmallIntegerField(default=200, db_index=True)
    response_time_ms = models.PositiveIntegerField(default=0)
    referrer         = models.CharField(max_length=500, blank=True)
    device           = models.CharField(max_length=10, choices=DEVICE_CHOICES, default='unknown', db_index=True)
    user             = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                         on_delete=models.SET_NULL, related_name='+')
    session_key      = models.CharField(max_length=40, blank=True)
    ip               = models.GenericIPAddressField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['path', 'created_at']),
            models.Index(fields=['status_code', 'created_at']),
            models.Index(fields=['device', 'created_at']),
        ]

    def __str__(self):
        return f'{self.method} {self.path} → {self.status_code}'


class UserActionLog(models.Model):
    """Explicit user-initiated actions: login, shortlist, quiz, share, etc."""
    ACTION_CHOICES = [
        ('login',            'Login'),
        ('login_failed',     'Login Failed'),
        ('logout',           'Logout'),
        ('shortlist_add',    'Shortlist Add'),
        ('shortlist_remove', 'Shortlist Remove'),
        ('compare_add',      'Compare Add'),
        ('compare_remove',   'Compare Remove'),
        ('profile_update',   'Profile Update'),
        ('share',            'Share'),
        ('ai_chat',          'AI Chat Message'),
        ('quiz_start',       'Quiz Start'),
        ('quiz_complete',    'Quiz Complete'),
        ('calculator_run',   'Calculator Run'),
        ('referral_click',   'Referral Click'),
        ('email_verified',   'Email Verified'),
        ('password_reset',   'Password Reset'),
    ]
    action      = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    properties  = models.JSONField(default=dict, blank=True)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+')
    session_key = models.CharField(max_length=40, blank=True)
    ip          = models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        who = self.user.email if self.user else 'anon'
        return f'{self.action} — {who} — {self.created_at:%Y-%m-%d %H:%M}'


class SessionLog(models.Model):
    """
    One row per browser session. Created on first page hit, updated on every
    subsequent hit and every JS heartbeat (every 60 s).
    duration = last_seen_at − created_at  →  average session time on site.
    """
    session_key  = models.CharField(max_length=40, unique=True, db_index=True)
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+')
    ip           = models.GenericIPAddressField(null=True, blank=True)
    device       = models.CharField(max_length=10, blank=True)
    country      = models.CharField(max_length=100, blank=True, db_index=True)
    region       = models.CharField(max_length=100, blank=True, db_index=True)
    page_count   = models.PositiveIntegerField(default=1)
    last_seen_at = models.DateTimeField(db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['created_at'])]

    def __str__(self):
        return f'Session {self.session_key[:8]}… — {self.page_count} pages'

    @property
    def duration_seconds(self):
        return max(0, int((self.last_seen_at - self.created_at).total_seconds()))


class SearchLog(models.Model):
    query        = models.CharField(max_length=300, db_index=True)
    result_count = models.PositiveSmallIntegerField(default=0)
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+')
    session_key  = models.CharField(max_length=40, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['query']),
            models.Index(fields=['created_at']),
            models.Index(fields=['session_key']),
        ]

    def __str__(self):
        return f'"{self.query}" ({self.result_count} results)'


class ViewLog(models.Model):
    TYPE_CHOICES = [
        ('course',          'Course'),
        ('institution',     'Institution'),
        ('career_profile',  'Career Profile'),
        ('resource',        'Resource'),
        ('article',         'Article'),
        ('mentor_profile',  'Mentor Profile'),
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


class EventLog(models.Model):
    """Generic server-side event store for anything not covered by specialised logs."""
    name        = models.CharField(max_length=80, db_index=True)
    properties  = models.JSONField(default=dict, blank=True)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+')
    session_key = models.CharField(max_length=40, blank=True)
    ip          = models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['name', 'created_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.name} — {self.created_at:%Y-%m-%d %H:%M}'


class PWAInstallLog(models.Model):
    PLATFORM_CHOICES = [
        ('android', 'Android / Chrome'),
        ('ios',     'iOS Safari'),
        ('desktop', 'Desktop'),
        ('unknown', 'Unknown'),
    ]
    platform    = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default='unknown', db_index=True)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+')
    session_key = models.CharField(max_length=40, blank=True)
    ip          = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.CharField(max_length=300, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['platform', 'created_at'])]

    def __str__(self):
        return f'PWA install — {self.platform} — {self.created_at:%Y-%m-%d}'


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
