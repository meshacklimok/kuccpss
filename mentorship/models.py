import uuid
from datetime import datetime, time as dt_time
from django.conf import settings
from django.db import models
from django.db.models import Avg
from django.utils import timezone


class MentorProfile(models.Model):
    YEAR_CHOICES = [
        (1, "1st Year"),
        (2, "2nd Year"),
        (3, "3rd Year"),
        (4, "4th Year"),
        (5, "5th Year"),
        (6, "6th Year / Masters"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentor_profile",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        related_name="mentors",
    )
    institution = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.SET_NULL,
        null=True,
        related_name="mentors",
    )
    year_of_study = models.PositiveSmallIntegerField(choices=YEAR_CHOICES, default=1)
    bio = models.TextField(
        max_length=600,
        help_text="Tell students what you study, your experience, and what you can help with.",
    )
    whatsapp = models.CharField(
        max_length=20,
        help_text="Your WhatsApp number — shared only with paying students. E.g. +254712345678",
    )
    photo = models.ImageField(upload_to="mentor_photos/", blank=True, null=True)

    # Verification documents (required at signup)
    student_id_upload = models.FileField(
        upload_to="mentor_docs/student_ids/",
        null=True, blank=True,
        help_text="Photo or scan of your student ID card.",
    )
    portal_screenshot = models.FileField(
        upload_to="mentor_docs/portal_screenshots/",
        null=True, blank=True,
        help_text="Screenshot from your university portal showing Name, Reg No, Course, and Year/Semester.",
    )

    # Optional — institutional email boosts credibility
    university_email = models.EmailField(
        blank=True,
        help_text="Your institutional email, e.g. jm001@students.jkuat.ac.ke. Optional but increases approval chances.",
    )

    # Per-mentor pricing override (leave blank to use global MentorshipConfig)
    custom_session_price = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Override global session price for this mentor only. Leave blank to use the global default.",
    )
    custom_mentor_payout = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Override global mentor payout for this mentor only. Leave blank to use the global default.",
    )

    # Earnings wallet (in KES cents avoided — store as KES integers)
    wallet_balance = models.PositiveIntegerField(default=0)
    total_earned = models.PositiveIntegerField(default=0)

    # Computed stats — refreshed after each session
    total_sessions = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)

    # Approval workflow
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_rejected = models.BooleanField(
        default=False,
        help_text="Set by admin on rejection — permanently prevents reapplication.",
    )
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-average_rating", "-total_sessions", "-created_at"]

    def __str__(self):
        return f"{self.user.full_name or self.user.email} — {self.course}"

    def refresh_stats(self):
        rated = self.sessions.filter(status="completed", rating__isnull=False)
        self.average_rating = rated.aggregate(avg=Avg("rating"))["avg"] or 0
        self.total_sessions = self.sessions.filter(status="completed").count()
        self.save(update_fields=["average_rating", "total_sessions"])

    @property
    def display_name(self):
        return self.user.full_name or self.user.email.split("@")[0].title()

    @property
    def rating_int(self):
        return int(round(self.average_rating))

    @property
    def available_slots_count(self):
        return self.slots.filter(is_booked=False, date__gte=timezone.now().date()).count()

    def effective_session_price(self):
        if self.custom_session_price is not None:
            return self.custom_session_price
        return MentorshipConfig.get().session_price

    def effective_mentor_payout(self):
        if self.custom_mentor_payout is not None:
            return self.custom_mentor_payout
        return MentorshipConfig.get().mentor_payout


class TimeSlot(models.Model):
    mentor = models.ForeignKey(
        MentorProfile,
        on_delete=models.CASCADE,
        related_name="slots",
    )
    date = models.DateField()
    start_time = models.TimeField()
    is_booked = models.BooleanField(default=False)

    class Meta:
        ordering = ["date", "start_time"]
        unique_together = ["mentor", "date", "start_time"]

    def __str__(self):
        return f"{self.mentor.display_name} — {self.date} {self.start_time.strftime('%H:%M')}"

    @property
    def is_future(self):
        slot_dt = timezone.make_aware(datetime.combine(self.date, self.start_time))
        return slot_dt > timezone.now()

    @property
    def datetime_display(self):
        return f"{self.date.strftime('%a %d %b')} at {self.start_time.strftime('%I:%M %p')}"


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ("pending",   "Pending Review"),
        ("processed", "Processed"),
        ("rejected",  "Rejected"),
    ]

    mentor = models.ForeignKey(
        MentorProfile,
        on_delete=models.CASCADE,
        related_name="withdrawals",
    )
    amount = models.PositiveIntegerField(help_text="KES amount to withdraw")
    mpesa_number = models.CharField(max_length=20, help_text="e.g. +254712345678")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.mentor.display_name} — KES {self.amount} ({self.status})"


class MentorshipSession(models.Model):
    STATUS_CHOICES = [
        ("pending_payment", "Pending Payment"),
        ("confirmed",       "Confirmed"),
        ("completed",       "Completed"),
        ("cancelled",       "Cancelled"),
        ("refunded",        "Refunded"),
    ]

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    mentor = models.ForeignKey(
        MentorProfile,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    mentee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentorship_sessions",
    )
    slot = models.OneToOneField(
        TimeSlot,
        on_delete=models.CASCADE,
        related_name="session",
    )
    course_interest = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    mentee_question = models.TextField(max_length=600)

    # Payment
    amount = models.PositiveIntegerField(default=100)
    mentor_payout = models.PositiveIntegerField(default=70)
    payment_ref = models.CharField(max_length=200, blank=True)
    phone_used = models.CharField(max_length=20, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending_payment",
        db_index=True,
    )

    # Post-session feedback
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    review = models.TextField(blank=True, max_length=500)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Session {str(self.token)[:8]} — {self.mentee} × {self.mentor.display_name}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("mentorship:session_detail", args=[self.token])

    @property
    def mentee_display(self):
        return self.mentee.full_name or self.mentee.email.split("@")[0].title()


class MentorshipConfig(models.Model):
    """Singleton — one row (pk=1). Set session price and mentor payout from admin."""
    session_price = models.PositiveIntegerField(
        default=100,
        help_text="Amount (KES) the student pays per session.",
    )
    mentor_payout = models.PositiveIntegerField(
        default=70,
        help_text="Amount (KES) the mentor earns per completed session. Must be less than session_price.",
    )

    class Meta:
        verbose_name = "Mentorship Pricing Config"
        verbose_name_plural = "Mentorship Pricing Config"

    def __str__(self):
        return f"Session: KES {self.session_price} | Mentor payout: KES {self.mentor_payout}"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"session_price": 100, "mentor_payout": 70})
        return obj
