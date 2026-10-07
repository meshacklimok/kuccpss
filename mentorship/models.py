import uuid
from datetime import datetime, time as dt_time, timedelta
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg
from django.utils import timezone


from kuccpss.upload_validators import SafeDocumentValidator, SafeImageValidator

class MentorProfile(models.Model):
    YEAR_CHOICES = [
        (1, "1st Year"),
        (2, "2nd Year"),
        (3, "3rd Year"),
        (4, "4th Year"),
        (5, "5th Year"),
        (6, "6th Year / Masters"),
    ]

    STUDENT = "student"
    EXPERT = "expert"
    MENTOR_TYPE_CHOICES = [
        (STUDENT, "Student mentor"),
        (EXPERT, "Expert mentor"),
    ]

    mentor_type = models.CharField(
        max_length=10, choices=MENTOR_TYPE_CHOICES, default=STUDENT, db_index=True,
        help_text="Expert mentors are professionals who advise on any course. They are "
                  "listed above student mentors and are added by admin, not via the signup form.",
    )
    headline = models.CharField(
        max_length=120, blank=True,
        help_text="Expert mentors only — shown in place of course/year, "
                  "e.g. 'Career Counsellor · 15 yrs experience'.",
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Expert mentors only — lower numbers are listed first.",
    )
    show_new_badge = models.BooleanField(
        default=False,
        help_text="Show the 'New mentor' badge on this mentor's card and profile.",
    )
    is_pinned = models.BooleanField(
        default=False,
        help_text="Student mentors only — pin to the top of the directory, above mentors with more sessions.",
    )
    show_expert_badge = models.BooleanField(
        default=False,
        help_text="Show the 'Expert' badge next to this mentor's name on their card and profile.",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentor_profile",
    )
    # Blank for expert mentors, who aren't tied to one course; the signup form
    # still requires both for student mentors.
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mentors",
    )
    institution = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
    photo = models.ImageField(upload_to="mentor_photos/", blank=True, null=True, validators=[SafeImageValidator()])

    # Verification documents (required at signup)
    student_id_upload = models.FileField(
        upload_to="mentor_docs/student_ids/",
        null=True, blank=True, validators=[SafeDocumentValidator()],
        help_text="Photo or scan of your student ID card.",
    )
    portal_screenshot = models.FileField(
        upload_to="mentor_docs/portal_screenshots/",
        null=True, blank=True, validators=[SafeDocumentValidator()],
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
    custom_session_minutes = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(5), MaxValueValidator(240)],
        help_text="Override global session length (minutes) for this mentor only. Leave blank to use the global default.",
    )

    # Earnings wallet (in KES cents avoided — store as KES integers)
    wallet_balance = models.PositiveIntegerField(default=0)
    total_earned = models.PositiveIntegerField(default=0)
    # Payout reversed after it had already been paid out to M-Pesa (wallet too low to
    # debit). Recovered automatically from the mentor's next session earnings.
    payout_debt = models.PositiveIntegerField(default=0)

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
        indexes = [
            models.Index(fields=["is_approved", "is_active"]),
            models.Index(fields=["average_rating"]),
        ]

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
    def is_expert(self):
        return self.mentor_type == self.EXPERT

    @property
    def rating_int(self):
        return int(round(self.average_rating))

    @property
    def available_slots_count(self):
        return self.slots.filter(bookable_slots_q()).count()

    def effective_session_price(self):
        if self.custom_session_price is not None:
            return self.custom_session_price
        return MentorshipConfig.get().session_price

    def effective_mentor_payout(self):
        if self.custom_mentor_payout is not None:
            return self.custom_mentor_payout
        return MentorshipConfig.get().mentor_payout

    def effective_session_minutes(self):
        if self.custom_session_minutes:
            return self.custom_session_minutes
        return MentorshipConfig.get().session_minutes


BOOKING_LEAD_MINUTES = 30


def bookable_slots_q(prefix=""):
    """Q for open slots starting at least BOOKING_LEAD_MINUTES from now (local time).
    `prefix` lets it filter through a relation, e.g. bookable_slots_q("slots__")."""
    cutoff = timezone.localtime() + timedelta(minutes=BOOKING_LEAD_MINUTES)
    return models.Q(**{f"{prefix}is_booked": False}) & (
        models.Q(**{f"{prefix}date__gt": cutoff.date()})
        | models.Q(**{f"{prefix}date": cutoff.date(), f"{prefix}start_time__gte": cutoff.time()})
    )


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
        indexes = [
            models.Index(fields=["date", "is_booked"]),
            models.Index(fields=["mentor", "date"]),
        ]

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
        ("failed",    "Failed"),
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
        indexes = [models.Index(fields=["mentor", "status"])]
        constraints = [
            # At most one in-flight payout per mentor — the DB-level guard against a
            # double-submitted withdrawal (or auto-pay racing it) paying out twice.
            models.UniqueConstraint(
                fields=["mentor"],
                condition=models.Q(status="pending"),
                name="one_pending_withdrawal_per_mentor",
            ),
        ]

    def __str__(self):
        return f"{self.mentor.display_name} — KES {self.amount} ({self.status})"


ACTIVE_STATUSES = ("pending_payment", "pending_manual_verification", "confirmed", "completed")


class MentorshipSession(models.Model):
    STATUS_CHOICES = [
        ("pending_payment",           "Pending Payment"),
        ("pending_manual_verification", "Pending Manual Verification"),
        ("confirmed",                 "Confirmed"),
        ("completed",                 "Completed"),
        ("cancelled",                 "Cancelled"),
        ("refunded",                  "Refunded"),
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
    # A ForeignKey (not one-to-one) so a slot freed by a cancellation can be booked
    # again while the cancelled session keeps its history; the constraint in Meta
    # still allows only one live session per slot.
    slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    course_interest = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    # Expert mentors cover any course, so the student names the one they're asking
    # about (free text; course_interest is set too when it matches a Course name).
    course_topic = models.CharField(max_length=150, blank=True)
    mentee_question = models.TextField(max_length=600)

    # Mentee contact info (shared with mentor after payment)
    mentee_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Mentee's phone number — shared with mentor after payment confirmation.",
    )

    # Payment
    amount = models.PositiveIntegerField(default=100)
    mentor_payout = models.PositiveIntegerField(default=70)
    # Snapshot of the mentor's session length at booking, like amount/mentor_payout
    duration_minutes = models.PositiveSmallIntegerField(default=15)
    payment_ref = models.CharField(max_length=200, blank=True)
    phone_used = models.CharField(max_length=20, blank=True)
    manual_payment_ref = models.CharField(
        max_length=100,
        blank=True,
        help_text="M-Pesa transaction code entered by mentee for manual payment verification.",
    )

    # Track whether booking confirmation emails have been sent
    confirmation_sent = models.BooleanField(default=False)
    # IntaSend refund (chargeback) tracking. refund_requested_at doubles as the claim
    # that stops two paths refunding the same payment.
    refund_ref = models.CharField(max_length=100, blank=True)
    refund_requested_at = models.DateTimeField(null=True, blank=True)
    refund_error = models.CharField(max_length=500, blank=True)
    # Set when the 1-hour reminder emails go out, so repeated housekeeping runs don't resend
    reminder_sent = models.BooleanField(default=False)

    status = models.CharField(
        max_length=30,
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
        indexes = [
            models.Index(fields=["mentor", "status"]),
            models.Index(fields=["mentee", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["slot"],
                condition=models.Q(status__in=ACTIVE_STATUSES),
                name="one_active_session_per_slot",
            ),
        ]

    def __str__(self):
        return f"Session {str(self.token)[:8]} — {self.mentee} × {self.mentor.display_name}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("mentorship:session_detail", args=[self.token])

    @property
    def end_time(self):
        start = datetime.combine(self.slot.date, self.slot.start_time)
        return (start + timedelta(minutes=self.duration_minutes)).time()

    @property
    def mentee_display(self):
        return self.mentee.full_name or self.mentee.email.split("@")[0].title()


class MentorshipConfig(models.Model):
    """Singleton — one row (pk=1). All mentorship settings controlled from here."""
    session_price = models.PositiveIntegerField(
        default=100,
        help_text="Amount (KES) the student pays per session.",
    )
    mentor_payout = models.PositiveIntegerField(
        default=70,
        help_text="Amount (KES) the mentor earns per completed session. Must be less than session_price.",
    )
    session_minutes = models.PositiveSmallIntegerField(
        default=15,
        validators=[MinValueValidator(5), MaxValueValidator(240)],
        help_text="Default session length in minutes. Override per mentor on the mentor's profile.",
    )
    mentor_signup_enabled = models.BooleanField(
        default=True,
        help_text="Show or hide the 'Become a Mentor' button across the entire site.",
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
