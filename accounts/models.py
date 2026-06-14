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
# APPLICATION TRACKING
# =====================================================

class ApplicationTracking(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("waitlisted", "Waitlisted"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="applications"
    )
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="applications",
        null=True, blank=True
    )
    institution_name = models.CharField(max_length=200, blank=True)
    course_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    deadline = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.course_name or self.course} ({self.status})"

    def get_course_display(self):
        if self.course:
            return self.course.name
        return self.course_name or "Unknown course"


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