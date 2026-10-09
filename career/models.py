from django.db import models
from django.conf import settings

from kuccpss.upload_validators import SafeImageValidator

# Legacy career course models (KCSEGrade, University, Course, TVET/KMTC/TTC
# courses, StudentCourseMatch, AIRecommendation, CareerInsight) were dropped in
# migration 0026 — all course data lives in courses.Course / CourseOffering.


def get_default_course_category():
    """Referenced by migration 0001 only; the model it served no longer exists."""
    return None


# =====================================================
# Career Profile (for career guidance section)
# =====================================================
class CareerProfile(models.Model):
    DEMAND_CHOICES = [
        ("very_high", "Very High"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    title = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    description = models.TextField()
    duties = models.TextField(blank=True, help_text="Key duties and responsibilities")
    skills_required = models.TextField(blank=True, help_text="Skills needed for this career")
    educational_pathway = models.TextField(blank=True, help_text="Steps to enter this career")
    job_opportunities = models.TextField(blank=True, help_text="Where you can work")
    average_salary = models.CharField(max_length=100, blank=True, help_text="e.g. KSh 50,000 – 150,000/month")
    demand_level = models.CharField(max_length=20, choices=DEMAND_CHOICES, default="medium")
    future_outlook = models.TextField(blank=True, help_text="Future growth prospects")
    icon = models.CharField(max_length=50, blank=True, help_text="FontAwesome icon class")
    image = models.ImageField(upload_to="career_profile_images/", blank=True, null=True, validators=[SafeImageValidator()])
    career_tags = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated tags used for quiz matching, e.g. science,health,biology"
    )
    related_courses = models.ManyToManyField(
        "courses.Course", blank=True, related_name="career_profiles"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        indexes = [
            models.Index(fields=["demand_level"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.title)
            slug = base
            counter = 1
            while CareerProfile.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_tags_list(self):
        return [t.strip() for t in self.career_tags.split(",") if t.strip()]

    def get_demand_color(self):
        colors = {
            "very_high": "success",
            "high": "primary",
            "medium": "warning",
            "low": "secondary",
        }
        return colors.get(self.demand_level, "secondary")


# =====================================================
# Career Assessment Quiz
# =====================================================
class QuizQuestion(models.Model):
    CATEGORY_CHOICES = [
        ("interest", "Interests"),
        ("strength", "Strengths"),
        ("personality", "Personality"),
        ("values", "Values"),
    ]

    text = models.CharField(max_length=300)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="interest")
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text


class QuizOption(models.Model):
    question = models.ForeignKey(
        QuizQuestion, on_delete=models.CASCADE, related_name="options"
    )
    text = models.CharField(max_length=200)
    career_tags = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated career tags this option maps to, e.g. science,engineering"
    )
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.question.text[:40]} → {self.text}"

    def get_tags_list(self):
        return [t.strip() for t in self.career_tags.split(",") if t.strip()]


class QuizSubmission(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="quiz_submissions", null=True, blank=True
    )
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Quiz by {self.user or self.session_key} on {self.created_at.date()}"


class QuizAnswer(models.Model):
    submission = models.ForeignKey(
        QuizSubmission, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    option = models.ForeignKey(QuizOption, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("submission", "question")

    def __str__(self):
        return f"{self.question.text[:40]} → {self.option.text}"

# =====================================================
# Career Recommendation Config (singleton)
# =====================================================
class CareerConfig(models.Model):
    """
    Singleton — one row (pk=1). Configures recommendation tier thresholds.
    Distances are in cluster points (Degree) or mean-grade points (others).
    """
    best_match_max_diff = models.FloatField(
        default=3.0,
        help_text=(
            "Max points ABOVE cutoff for 'Best Match'. "
            "E.g. 3.0 means diff 0–3 = Best Match."
        ),
    )
    stretch_min_diff = models.FloatField(
        default=-3.0,
        help_text=(
            "Min points BELOW cutoff still counted as 'Stretch Opportunity' (enter as negative). "
            "E.g. -3.0 means student can be up to 3 pts below cutoff and still see it as Stretch."
        ),
    )
    safe_max_diff = models.FloatField(
        default=8.0,
        help_text=(
            "Max points above cutoff for 'Safe Option'. "
            "Beyond this becomes 'Easy Admission'. E.g. 8.0 means diff 3–8 = Safe."
        ),
    )
    competitive_threshold = models.FloatField(
        default=40.0,
        help_text=(
            "Courses whose cutoff is at or above this value are flagged 'Competitive'. "
            "Applies to Degree pathway (cluster points out of 48). Default: 40.0."
        ),
    )

    # ── Mentorship ────────────────────────────────────
    mentor_signup_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Show or hide the 'Become a Mentor' button and signup page. "
            "Disable to pause new mentor applications without removing existing mentors."
        ),
    )

    # ── Tawk.to Live Chat ─────────────────────────────
    tawk_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Show or hide the Tawk.to live chat widget on the dashboard. "
            "Disable this to remove the widget without touching code."
        ),
    )

    # ── AI On/Off ─────────────────────────────────────
    ai_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Master switch — disables ALL AI features site-wide (chat, insight, quiz summary). "
            "Use this to cut off OpenAI calls instantly without touching code."
        ),
    )
    ai_prompt_template = models.TextField(
        blank=True,
        help_text=(
            "Prompt sent to GPT-4o-mini for the quiz results summary. "
            "Use {tag_str} for interest tags and {careers_str} for matched careers. "
            "Leave blank to use the default prompt."
        ),
    )
    ai_model_name = models.CharField(
        max_length=50,
        default='gpt-4o-mini',
        help_text=(
            "OpenAI model used for all CareerNext AI features (chat, insight, quiz summary). "
            "Change this to switch models without a code deploy, e.g. 'gpt-4o' or 'gpt-4o-mini'."
        ),
    )
    ai_temperature = models.FloatField(
        default=0.6,
        help_text=(
            "Sampling temperature (0.0–2.0) applied to all CareerNext AI calls. "
            "Lower = more focused/deterministic, higher = more creative/varied."
        ),
    )

    # ── Rate Limiting ──────────────────────────────────
    rate_limiting_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Enable or disable rate limiting entirely. "
            "When off, users can make unlimited AI calls regardless of the limits below."
        ),
    )
    ai_daily_limit = models.PositiveIntegerField(
        default=3,
        help_text=(
            "Daily AI call limit for ANONYMOUS (non-logged-in) users only. "
            "Logged-in users are governed by ai_free_message_limit instead."
        ),
    )
    ai_chat_max_messages = models.PositiveIntegerField(
        default=20,
        help_text=(
            "Maximum number of messages a user can send in a single chat conversation. "
            "Set to 0 for unlimited. Ignored when rate limiting is disabled."
        ),
    )
    # ── Lifetime credit limits (logged-in users) ───────
    ai_free_message_limit = models.PositiveIntegerField(
        default=20,
        help_text=(
            "Total lifetime free AI chat messages a registered user gets before hitting the paywall. "
            "E.g. 20 means the first 20 messages are free forever."
        ),
    )
    ai_paid_message_limit = models.PositiveIntegerField(
        default=200,
        help_text=(
            "Number of AI chat messages unlocked each time a user makes a payment. "
            "E.g. 200 means each top-up gives 200 additional messages."
        ),
    )
    ai_free_reset_days = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Days before the free message counter resets automatically for users who haven't paid. "
            "E.g. 1 = resets every day, 7 = every week. "
            "0 = never reset (lifetime allocation — user must pay once exhausted)."
        ),
    )

    class Meta:
        verbose_name = "Career Recommendation Config"
        verbose_name_plural = "Career Recommendation Config"

    def __str__(self):
        return "Career Recommendation Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls) -> "CareerConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

# =====================================================
# SHARED RESULT (public shareable career result links)
# =====================================================
# =====================================================
# AI Knowledge Base (admin-managed Q&A for chatbot)
# =====================================================
class AIKnowledgeEntry(models.Model):
    CATEGORY_CHOICES = [
        ('grade_career',    'Grade → Career'),
        ('interest_career', 'Interest → Career'),
        ('course_info',     'Course Explanation'),
        ('career_outcome',  'Career Outcomes & Salary'),
        ('admission',       'University & Admission'),
        ('comparison',      'Comparisons'),
        ('decision',        'Decision Help'),
        ('future_trends',   'Future & Trends'),
        ('pathway',         'Pathways (Degree/Diploma/TVET)'),
        ('kuccps',          'KUCCPS Process'),
        ('general',         'General'),
    ]

    question   = models.CharField(max_length=500)
    answer     = models.TextField(help_text="The verified, factual answer the AI will use")
    keywords   = models.CharField(
        max_length=500, blank=True,
        help_text="Comma-separated search words (e.g. c+,degree,university,qualify)"
    )
    category   = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='general')
    is_active  = models.BooleanField(default=True)
    order      = models.PositiveIntegerField(default=0, help_text="Lower = shown first in admin")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'order', 'id']
        verbose_name        = 'AI Knowledge Entry'
        verbose_name_plural = 'AI Knowledge Base'
        indexes = [models.Index(fields=["is_active", "category"])]

    def __str__(self):
        return f"[{self.get_category_display()}] {self.question[:80]}"  # type: ignore[attr-defined]

    def get_keywords_list(self):
        return [k.strip().lower() for k in self.keywords.split(',') if k.strip()]


# =====================================================
# Job Market Intelligence
# =====================================================
class JobMarketData(models.Model):
    DEMAND_CHOICES = [('High', 'High'), ('Medium', 'Medium'), ('Low', 'Low')]

    career_name  = models.CharField(max_length=150, unique=True)
    keywords     = models.CharField(
        max_length=600,
        help_text="Comma-separated lowercase terms matched against course career_outcomes (e.g. doctor,physician,surgeon)"
    )
    salary_min   = models.PositiveIntegerField(help_text="Monthly gross KES — lower end")
    salary_max   = models.PositiveIntegerField(help_text="Monthly gross KES — upper end")
    demand       = models.CharField(max_length=10, choices=DEMAND_CHOICES, default='Medium')
    top_sectors  = models.CharField(max_length=300, help_text="Comma-separated hiring sectors")
    source_year  = models.PositiveSmallIntegerField(default=2024)
    source_name  = models.CharField(max_length=200, default="BrighterMonday Kenya Salary Report 2024")
    source_url   = models.URLField(blank=True, default="https://www.brightermonday.co.ke/research")

    class Meta:
        ordering = ['career_name']
        verbose_name        = 'Job Market Data'
        verbose_name_plural = 'Job Market Data'

    def __str__(self):
        return f"{self.career_name} (KSh {self.salary_min:,}–{self.salary_max:,})"

    def salary_display(self):
        def _fmt(n):
            return f"{n // 1000}k" if n % 1000 == 0 else f"{n:,}"
        return f"KSh {_fmt(self.salary_min)} – {_fmt(self.salary_max)} / mo"

    def keywords_list(self):
        return [k.strip().lower() for k in self.keywords.split(',') if k.strip()]

    def sectors_list(self):
        return [s.strip() for s in self.top_sectors.split(',') if s.strip()]


# =====================================================
# AI Call Rate-Limit Log
# =====================================================
class AICallLog(models.Model):
    """One row per (user OR session) per calendar day — tracks daily AI call count."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='ai_call_logs',
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    date = models.DateField(db_index=True)
    call_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'date'],
                condition=models.Q(user__isnull=False),
                name='unique_user_date_ai_log',
            ),
            models.UniqueConstraint(
                fields=['session_key', 'date'],
                condition=models.Q(user__isnull=True),
                name='unique_session_date_ai_log',
            ),
        ]
        indexes = [models.Index(fields=["user", "date"])]
        verbose_name = 'AI Call Log'
        verbose_name_plural = 'AI Call Logs'

    def __str__(self):
        who = str(self.user) if self.user_id else f'session:{self.session_key[:8]}'  # type: ignore[attr-defined]
        return f"{who} — {self.date} — {self.call_count} calls"


# =====================================================
# AI Chat Credit — lifetime message bank per user
# =====================================================
class AIChatCredit(models.Model):
    """
    Tracks how many lifetime free messages a registered user has consumed
    and how many paid messages they still have remaining.

    free_messages_used   — increments on every free-tier message sent.
    paid_messages_remaining — decrements on every paid-tier message sent;
                              topped up when a payment for 'ai_chat_access' completes.
    total_paid_ever      — cumulative paid messages ever purchased (audit trail).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_chat_credit',
    )
    free_messages_used = models.PositiveIntegerField(default=0)
    paid_messages_remaining = models.PositiveIntegerField(default=0)
    total_paid_ever = models.PositiveIntegerField(default=0)
    last_topped_up_at = models.DateTimeField(null=True, blank=True)
    free_period_started_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Start of the current free-message period. Updated each time the counter is auto-reset.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI Chat Credit'
        verbose_name_plural = 'AI Chat Credits'

    def __str__(self):
        return (
            f"{self.user.email} — "
            f"free used: {self.free_messages_used} | "
            f"paid remaining: {self.paid_messages_remaining}"
        )

    @classmethod
    def for_user(cls, user):
        """Get-or-create the credit record for a user."""
        obj, _ = cls.objects.get_or_create(user=user)
        return obj

    def top_up(self, messages: int):
        """Add paid messages (called by payment webhook)."""
        from django.utils import timezone
        self.paid_messages_remaining += messages
        self.total_paid_ever += messages
        self.last_topped_up_at = timezone.now()
        self.save(update_fields=['paid_messages_remaining', 'total_paid_ever', 'last_topped_up_at', 'updated_at'])


import uuid as _uuid
from datetime import timedelta as _td

def _default_share_expiry():
    from django.utils import timezone
    return timezone.now() + _td(days=30)

class SharedResult(models.Model):
    token           = models.UUIDField(default=_uuid.uuid4, unique=True, db_index=True, editable=False)
    user            = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='shared_results'
    )
    pathway         = models.CharField(max_length=50)
    cluster_points_json = models.JSONField(default=dict)
    cluster_pts_single  = models.FloatField(default=0)
    total_matches   = models.PositiveIntegerField(default=0)
    top_courses_json = models.JSONField(default=list)
    view_count      = models.PositiveIntegerField(default=0)
    created_at      = models.DateTimeField(auto_now_add=True)
    expires_at      = models.DateTimeField(default=_default_share_expiry)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"Share/{self.token} — {self.pathway} ({self.total_matches} matches)"

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('career:shared_result', args=[str(self.token)])


# =====================================================
# Submission Lock Config (admin-configurable per feature)
# =====================================================
class SubmissionLockConfig(models.Model):
    FEATURE_CHOICES = [
        ('degree_career', 'Career Engine (Degree Path)'),
        ('cluster_calculator', 'Cluster Points Calculator'),
        ('non_degree_career', 'Career Engine (Diploma / Certificate / KMTC / TTC / Artisan)'),
    ]
    feature = models.CharField(max_length=50, choices=FEATURE_CHOICES, unique=True)
    lock_minutes = models.PositiveIntegerField(
        default=2,
        help_text="Minutes the user has to review and edit before their submission is locked.",
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text="Disable to allow unlimited resubmission (no locking).",
    )
    allow_official_resubmit = models.BooleanField(
        default=False,
        help_text=(
            "When ON: users who submitted via the calculator can resubmit once more "
            "using Upload / Paste / Manual (for when real KUCCPS cluster points are released). "
            "The calculator itself stays blocked."
        ),
    )
    lock_on_payment = models.BooleanField(
        default=True,
        help_text=(
            "When ON: grades are locked immediately when the linked payment completes "
            "(view_cluster_points → cluster_calculator; premium_career_report → degree_career "
            "and non_degree_career). "
            "Turn OFF to rely only on the time-based grace period."
        ),
    )

    class Meta:
        verbose_name = "Submission Lock Config"
        verbose_name_plural = "Submission Lock Configs"

    def __str__(self):
        state = "enabled" if self.is_enabled else "disabled"
        return f"{self.get_feature_display()} — {self.lock_minutes} min grace ({state})"  # type: ignore[attr-defined]

    @classmethod
    def get_for_feature(cls, feature: str):
        try:
            return cls.objects.get(feature=feature)
        except cls.DoesNotExist:
            return None


# =====================================================
# Career Submission (one per user per feature, locks after grace period)
# =====================================================
class CareerSubmission(models.Model):
    FEATURE_DEGREE = 'degree_career'
    FEATURE_CALCULATOR = 'cluster_calculator'
    # One lock shared by every non-degree pathway — KCSE grades don't change with the pathway
    FEATURE_NON_DEGREE = 'non_degree_career'

    STATUS_PENDING = 'pending'
    STATUS_LOCKED = 'locked'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending — editable'),
        (STATUS_LOCKED, 'Locked'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='career_submissions',
    )
    METHOD_CALCULATE = 'calculate'
    METHOD_UPLOAD    = 'upload'
    METHOD_PASTE     = 'paste'
    METHOD_MANUAL    = 'manual'
    METHOD_CHOICES = [
        (METHOD_CALCULATE, 'Calculator (estimated)'),
        (METHOD_UPLOAD,    'Upload KCSE slip'),
        (METHOD_PASTE,     'Paste cluster points'),
        (METHOD_MANUAL,    'Manual cluster points entry'),
    ]

    feature = models.CharField(max_length=50, choices=SubmissionLockConfig.FEATURE_CHOICES)
    grades_json = models.JSONField(
        help_text="Subject grades {name: points} for calculate/upload; cluster points {num: pts} for paste/manual."
    )
    method = models.CharField(
        max_length=20, choices=METHOD_CHOICES, default=METHOD_CALCULATE,
        help_text="Which entry method the student used.",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    lock_at = models.DateTimeField(help_text="Submission auto-locks after this time.")
    unlocked_by_payment = models.ForeignKey(
        'payments.Payment',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='locked_submissions',
        help_text="The payment that locked and unlocked viewing for this grade session.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'feature')
        verbose_name = "Career Submission"
        verbose_name_plural = "Career Submissions"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["lock_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.get_feature_display()} ({self.status})"  # type: ignore[attr-defined]

    def seconds_remaining(self):
        from django.utils import timezone
        delta = (self.lock_at - timezone.now()).total_seconds()
        return max(0, int(delta))

    def grade_summary(self):
        """[(subject, letter), ...] for the review banner; empty for cluster-point entries."""
        if self.feature == self.FEATURE_NON_DEGREE and self.method == self.METHOD_MANUAL:
            mean = (self.grades_json or {}).get('mean_grade')
            return [('Mean grade', mean)] if mean else []
        if self.method not in (self.METHOD_CALCULATE, self.METHOD_UPLOAD):
            return []
        from clusterpoints.forms import DEFAULT_GRADE_CHOICES
        letters = dict(DEFAULT_GRADE_CHOICES)
        out = []
        for name, pts in (self.grades_json or {}).items():
            try:
                out.append((name, letters.get(int(pts), str(pts))))
            except (TypeError, ValueError):
                continue
        return sorted(out)
