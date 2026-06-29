import uuid
import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin
)
from django.conf import settings


# =====================================================
# DEFAULT EXPIRY FUNCTIONS (Named for Migrations)
# =====================================================

def default_email_token_expiry():
    return timezone.now() + timedelta(hours=24)

def default_password_reset_expiry():
    return timezone.now() + timedelta(hours=2)

def default_remember_token_expiry():
    return timezone.now() + timedelta(hours=72)


# =====================================================
# CUSTOM USER MANAGER
# =====================================================

class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True")

        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


# =====================================================
# CORE USER MODEL
# =====================================================

class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=150, blank=True)

    # Status flags
    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    is_google_user = models.BooleanField(default=False)

    # Compliance
    agreed_terms = models.BooleanField(default=False)
    terms_version = models.CharField(max_length=20, blank=True, null=True)

    # Audit timestamps
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    last_login_user_agent = models.CharField(max_length=255, blank=True, null=True)

    # Extended profile fields
    phone_number = models.CharField(max_length=20, blank=True)
    county = models.CharField(max_length=100, blank=True)
    kcse_year = models.PositiveIntegerField(null=True, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pics/', null=True, blank=True
    )

    email_notifications = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["is_active", "is_verified"]),
            models.Index(fields=["deleted_at"]),
        ]

    def __str__(self):
        return self.email

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save()


# =====================================================
# EMAIL VERIFICATION TOKEN
# =====================================================

class EmailVerificationToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_tokens")
    token = models.CharField(max_length=255, unique=True, db_index=True)
    expires_at = models.DateTimeField(default=default_email_token_expiry)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["expires_at", "is_used"])]

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()


# =====================================================
# PASSWORD RESET TOKEN
# =====================================================

class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_tokens")
    token = models.CharField(max_length=255, unique=True, db_index=True)
    expires_at = models.DateTimeField(default=default_password_reset_expiry)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["expires_at", "is_used"])]

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()


# =====================================================
# DEVICE SESSION TRACKING
# =====================================================

class DeviceSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="device_sessions")
    session_key = models.CharField(max_length=255, db_index=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)
    device_name = models.CharField(max_length=150, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["session_key"]),
        ]


# =====================================================
# REMEMBER ME TOKEN
# =====================================================

class RememberToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="remember_tokens")
    token = models.CharField(max_length=255, unique=True, db_index=True)
    expires_at = models.DateTimeField(default=default_remember_token_expiry)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["expires_at", "is_active"])]

    def is_valid(self):
        return self.is_active and self.expires_at > timezone.now()


# =====================================================
# LOGIN HISTORY / AUDIT TRAIL
# =====================================================

class LoginHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_history")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)
    success = models.BooleanField(default=True)
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-login_time"]
        indexes = [
            models.Index(fields=["user", "login_time"]),
            models.Index(fields=["ip_address"]),
        ]


# =====================================================
# APPLICATION TRACKER
# =====================================================
class Application(models.Model):
    STATUS_CHOICES = [
        ('draft',        'Draft'),
        ('submitted',    'Submitted'),
        ('under_review', 'Under Review'),
        ('waitlisted',   'Waitlisted'),
        ('accepted',     'Accepted'),
        ('rejected',     'Rejected'),
    ]
    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    course_name      = models.CharField(max_length=200)
    institution_name = models.CharField(max_length=200, blank=True)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    deadline         = models.DateField(null=True, blank=True)
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.course_name} — {self.user.email}"


# =====================================================
# SAVED COURSE
# =====================================================

class SavedCourse(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="saved_courses"
    )
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="saved_by"
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "course")
        ordering = ["-saved_at"]

    def __str__(self):
        return f"{self.user.email} → {self.course.name}"


# =====================================================
# SAVED CAREER
# =====================================================

class SavedCareer(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="saved_careers"
    )
    career_profile = models.ForeignKey(
        "career.CareerProfile", on_delete=models.CASCADE, related_name="saved_by"
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "career_profile")
        ordering = ["-saved_at"]

    def __str__(self):
        return f"{self.user.email} → {self.career_profile.title}"


# =====================================================
# COURSE SHORTLIST (comparison tool, max 5 per user)
# =====================================================

class CourseShortlist(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="shortlist"
    )
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="shortlisted_by"
    )
    rank = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="KUCCPS choice order (1 = first choice, up to 4)"
    )
    notes = models.TextField(blank=True, help_text="Personal notes for this course")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "course")
        ordering = ["rank", "-added_at"]

    def __str__(self):
        return f"{self.user.email} → {self.course.name}"


# =====================================================
# IN-APP NOTIFICATION
# =====================================================

class Notification(models.Model):
    TYPE_CHOICES = [
        ("info", "Info"),
        ("success", "Success"),
        ("warning", "Warning"),
        ("deadline", "Deadline"),
        ("system", "System"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sent_notifications",
        limit_choices_to={"is_staff": True},
    )
    message = models.TextField()
    notif_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="info")
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.message[:50]}"


# =====================================================
# CAREER SESSION SNAPSHOT
# Persists career engine results so the dashboard can
# show "Recommended For You" even after session expires.
# =====================================================

class CareerSessionSnapshot(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='career_snapshots'
    )
    pathway = models.CharField(max_length=50)
    cluster_points_json = models.JSONField(default=dict, blank=True)
    mean_grade = models.CharField(max_length=5, blank=True)
    aggregate_score = models.FloatField(null=True, blank=True)
    total_matches = models.PositiveIntegerField(default=0)
    tier_counts_json = models.JSONField(default=dict, blank=True)
    top_matches_json = models.JSONField(default=list, blank=True)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-computed_at']
        verbose_name = 'Career Session Snapshot'
        verbose_name_plural = 'Career Session Snapshots'
        indexes = [
            models.Index(fields=["user", "pathway"]),
            models.Index(fields=["user", "computed_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.pathway} ({self.computed_at:%Y-%m-%d})"


# =====================================================
# REFERRAL SYSTEM
# =====================================================

import random, string as _string

def _make_referral_code():
    return ''.join(random.choices(_string.ascii_uppercase + _string.digits, k=8))

class Referral(models.Model):
    referrer       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_sent')
    code           = models.CharField(max_length=12, unique=True, db_index=True)
    referred_user  = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='referred_by'
    )
    referred_email = models.EmailField(blank=True)
    converted      = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)
    converted_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['code']), models.Index(fields=['referrer'])]

    def __str__(self):
        return f"{self.referrer.email} → {self.code}"

    @staticmethod
    def get_or_create_for_user(user):
        obj, _ = Referral.objects.get_or_create(
            referrer=user, referred_user=None, converted=False,
            defaults={'code': _make_referral_code()}
        )
        return obj


# =====================================================
# AFFILIATE SYSTEM
# =====================================================

class AffiliateProfile(models.Model):
    """Hand-picked accounts that earn commission when their referrals pay."""
    user            = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='affiliate_profile'
    )
    is_active       = models.BooleanField(default=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=20.00,
                                          help_text="Percentage of each payment awarded as commission")
    wallet_balance  = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          help_text="Pending payout in KES")
    total_earned    = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          help_text="Lifetime commissions earned in KES")
    notes           = models.TextField(blank=True, help_text="Admin notes (e.g. WhatsApp group admin, 8K members)")
    approved_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_affiliates'
    )
    approved_at     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Affiliate Profile"
        verbose_name_plural = "Affiliate Profiles"
        ordering = ['-created_at']

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.user.email} ({status}) — KES {self.wallet_balance} pending"


class AffiliateCommission(models.Model):
    """One record per payment made by a referred user of an active affiliate."""
    STATUS_CHOICES = [
        ('pending',  'Pending Payout'),
        ('paid_out', 'Paid Out'),
    ]

    affiliate     = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='commissions')
    payment       = models.OneToOneField('payments.Payment', on_delete=models.CASCADE,
                                          related_name='affiliate_commission')
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='commissions_generated'
    )
    referral      = models.ForeignKey(Referral, on_delete=models.SET_NULL, null=True, related_name='commissions')
    amount        = models.DecimalField(max_digits=10, decimal_places=2, help_text="Commission in KES")
    rate_snapshot = models.DecimalField(max_digits=5, decimal_places=2,
                                         help_text="Rate at time of award (in case rate changes later)")
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paid_out_at   = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Affiliate Commission"
        verbose_name_plural = "Affiliate Commissions"
        ordering = ['-created_at']
        indexes = [models.Index(fields=["affiliate", "status"])]

    def __str__(self):
        return f"{self.affiliate.user.email} — KES {self.amount} ({self.status})"


class AffiliateWithdrawalRequest(models.Model):
    """Tracks each payout request made by an affiliate from their dashboard."""
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('processed', 'Processed'),
        ('failed',    'Failed'),
    ]

    affiliate    = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='withdrawals')
    amount       = models.DecimalField(max_digits=10, decimal_places=2)
    mpesa_number = models.CharField(max_length=20)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note   = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Affiliate Withdrawal"
        verbose_name_plural = "Affiliate Withdrawals"
        ordering = ['-created_at']
        indexes = [models.Index(fields=["affiliate", "status"])]

    def __str__(self):
        return f"{self.affiliate.user.email} — KES {self.amount} ({self.status})"


# =====================================================
# EMAIL LEAD (visitor email capture)
# =====================================================

class EmailLead(models.Model):
    SOURCE_CHOICES = [
        ('home',       'Homepage'),
        ('calculator', 'Calculator'),
        ('courses',    'Eligible Courses'),
        ('results',    'Career Results'),
        ('share',      'Shared Link'),
        ('other',      'Other'),
    ]
    email            = models.EmailField(db_index=True)
    source           = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='home')
    ref_code         = models.CharField(max_length=12, blank=True)
    ip_address       = models.GenericIPAddressField(blank=True, null=True)
    converted_to_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='email_lead'
    )
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering  = ['-created_at']
        indexes   = [models.Index(fields=['email'])]

    def __str__(self):
        return f"{self.email} ({self.source})"


# =====================================================
# WEB PUSH SUBSCRIPTIONS
# Stores browser push subscriptions for Web Push API.
# One user can have multiple subscriptions (phone + laptop).
# =====================================================

class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='push_subscriptions',
    )
    endpoint = models.URLField(max_length=600, unique=True)
    p256dh   = models.TextField()
    auth     = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Push Subscription'
        verbose_name_plural = 'Push Subscriptions'

    def __str__(self):
        return f"{self.user.email if self.user else 'anon'} — {self.endpoint[:60]}"


# =====================================================
# EMAIL BROADCAST
# Records every bulk email sent to all subscribers.
# =====================================================

class EmailBroadcast(models.Model):
    STATUS_CHOICES = [
        ('draft',   'Draft'),
        ('sent',    'Sent'),
        ('failed',  'Failed'),
    ]

    subject          = models.CharField(max_length=255)
    heading          = models.CharField(max_length=255)
    body             = models.TextField(help_text="One paragraph per line. Each line becomes a separate paragraph.")
    cta_label        = models.CharField(max_length=100, blank=True)
    cta_url          = models.URLField(blank=True)
    banner_color     = models.CharField(
        max_length=20,
        choices=[('green','Green'),('blue','Blue'),('amber','Amber'),('red','Red'),('purple','Purple')],
        default='blue',
    )
    send_to_leads    = models.BooleanField(default=False, help_text="Also send to captured email leads (non-registered visitors)")
    recipient_count  = models.PositiveIntegerField(default=0)
    status           = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    sent_by          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='broadcasts_sent'
    )
    sent_at          = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Email Broadcast'
        verbose_name_plural = 'Email Broadcasts'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status.upper()}] {self.subject} ({self.recipient_count} recipients)"
