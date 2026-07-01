from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import (
    TVETCategory, TVETCourse, KMTCampus, KMTCourse, TTCCollege, TTCCourse,
    CareerInsight,
    CareerProfile, QuizQuestion, QuizOption, QuizSubmission, QuizAnswer,
    CareerConfig, AIKnowledgeEntry, JobMarketData, AICallLog,
    SubmissionLockConfig, CareerSubmission, AIChatCredit,
)


# =====================================================
# TVET Categories & Courses
# =====================================================
@admin.register(TVETCategory)
class TVETCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(TVETCourse)
class TVETCourseAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "min_mean_grade")
    search_fields = ("name",)
    list_filter = ("category",)
    filter_horizontal = ("required_subjects",)


# =====================================================
# KMTC Campuses & Courses
# =====================================================
@admin.register(KMTCampus)
class KMTCampusAdmin(admin.ModelAdmin):
    list_display = ("name", "county")
    search_fields = ("name", "county")


@admin.register(KMTCourse)
class KMTCourseAdmin(admin.ModelAdmin):
    list_display = ("name", "min_mean_grade")
    search_fields = ("name",)
    filter_horizontal = ("required_subjects", "campuses")


# =====================================================
# TTC Colleges & Courses
# =====================================================
@admin.register(TTCCollege)
class TTCCollegeAdmin(admin.ModelAdmin):
    list_display = ("name", "county")
    search_fields = ("name", "county")


@admin.register(TTCCourse)
class TTCCourseAdmin(admin.ModelAdmin):
    list_display = ("name", "min_mean_grade")
    search_fields = ("name",)
    filter_horizontal = ("required_subjects", "colleges")


# =====================================================
# Career Insights
# =====================================================
@admin.register(CareerInsight)
class CareerInsightAdmin(admin.ModelAdmin):
    list_display = ("get_course_name", "demand_level", "average_salary")
    search_fields = ("course__name", "tvet_course__name", "kmc_course__name", "ttc_course__name", "career_fields")
    list_filter = ("demand_level",)

    @admin.display(description="Course")
    def get_course_name(self, obj):
        course_obj = obj.course or obj.tvet_course or obj.kmc_course or obj.ttc_course
        return course_obj.name if course_obj else "N/A"


# =====================================================
# Career Profiles
# =====================================================
class QuizOptionInline(admin.TabularInline):
    model = QuizOption
    extra = 2
    fields = ("text", "career_tags", "order")


@admin.register(CareerProfile)
class CareerProfileAdmin(admin.ModelAdmin):
    list_display  = ("title", "demand_level", "average_salary")
    search_fields = ("title", "career_tags")
    list_filter   = ("demand_level",)
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("related_courses",)


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display  = ("text", "category", "order")
    list_filter   = ("category",)
    ordering      = ("order",)
    inlines       = [QuizOptionInline]


@admin.register(QuizOption)
class QuizOptionAdmin(admin.ModelAdmin):
    list_display  = ("text", "question", "career_tags", "order")
    search_fields = ("text", "career_tags")
    ordering      = ("question", "order")


@admin.register(QuizSubmission)
class QuizSubmissionAdmin(admin.ModelAdmin):
    list_display    = ("user", "session_key", "created_at")
    list_filter     = ("created_at",)
    readonly_fields = ("created_at",)


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ("submission", "question", "option")
    list_filter  = ("question__category",)


# =====================================================
# Career Recommendation Config (singleton)
# =====================================================
@admin.register(CareerConfig)
class CareerConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Recommendation Tier Thresholds", {
            "description": (
                "Controls which tier each course falls into based on the difference between "
                "the student's score and the course cutoff. "
                "All values are in cluster points (Degree pathway) or mean-grade points (others)."
            ),
            "fields": ("best_match_max_diff", "stretch_min_diff", "safe_max_diff"),
        }),
        ("Competitive Flag", {
            "description": "Courses with a cutoff at or above this threshold are marked 'Competitive'.",
            "fields": ("competitive_threshold",),
        }),
        ("Tawk.to Live Chat", {
            "description": "Show or hide the Tawk.to live chat widget on the dashboard.",
            "fields": ("tawk_enabled",),
        }),
        ("Mentorship", {
            "description": (
                "Controls whether new mentor applications are open. "
                "Disabling hides the 'Become a Mentor' button and blocks direct URL access to the signup page."
            ),
            "fields": ("mentor_signup_enabled",),
        }),
        ("AI Master Switch", {
            "description": (
                "Disables ALL AI features site-wide (chat, insight, quiz summary) instantly. "
                "Use this to cut off OpenAI calls without touching code. "
                "Requires OPENAI_API_KEY in .env to function."
            ),
            "fields": ("ai_enabled",),
        }),
        ("AI Model Settings", {
            "description": (
                "Controls the OpenAI model and sampling temperature used by ALL CareerNext AI features "
                "(chat, insight, quiz summary). Change ai_model_name to switch models (e.g. 'gpt-4o') without a deploy. "
                "ai_temperature ranges 0.0 (focused) to 2.0 (creative)."
            ),
            "fields": ("ai_model_name", "ai_temperature"),
        }),
        ("AI Quiz Summary Prompt", {
            "description": (
                "Customise the prompt for the quiz results summary. "
                "Available placeholders: {tag_str} = student interest tags, {careers_str} = top matched careers. "
                "Leave blank to use the built-in default prompt."
            ),
            "fields": ("ai_prompt_template",),
        }),
        ("AI Rate Limiting — Anonymous Users", {
            "description": (
                "Daily limit for non-logged-in (anonymous) users only. "
                "Turn off 'rate limiting enabled' to remove all caps globally."
            ),
            "fields": ("rate_limiting_enabled", "ai_daily_limit", "ai_chat_max_messages"),
        }),
        ("AI Chat Credits — Registered Users", {
            "description": (
                "Controls the free-message allocation for registered users and the optional auto-reset period.\n\n"
                "ai_free_message_limit — how many free messages per period (e.g. 20).\n"
                "ai_paid_message_limit — messages added per payment (set price in Payments → Payment Features → ai_chat_access).\n"
                "ai_free_reset_days — 0 = lifetime (never resets, must pay). "
                "1 = resets every day. 7 = every week. "
                "Users who have paid credits are NOT affected by this reset."
            ),
            "fields": ("ai_free_message_limit", "ai_paid_message_limit", "ai_free_reset_days"),
        }),
    )

    def has_add_permission(self, request):  # noqa: ARG002
        return not CareerConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return False

    def changelist_view(self, request, extra_context=None):  # noqa: ARG002
        config = CareerConfig.get()
        return HttpResponseRedirect(
            reverse("admin:career_careerconfig_change", args=[config.pk])
        )


# =====================================================
# AI Knowledge Base
# =====================================================
@admin.register(AIKnowledgeEntry)
class AIKnowledgeEntryAdmin(admin.ModelAdmin):
    list_display  = ("question_short", "category", "is_active", "order", "updated_at")
    list_filter   = ("category", "is_active")
    search_fields = ("question", "answer", "keywords")
    list_editable = ("is_active", "order")
    ordering      = ("category", "order", "id")
    fieldsets = (
        (None, {
            "fields": ("question", "answer"),
        }),
        ("Classification & Search", {
            "fields": ("category", "keywords", "order", "is_active"),
            "description": (
                "Keywords are comma-separated words the chatbot uses to find this entry "
                "(e.g. 'c+,degree,qualify,university'). The more relevant keywords you add, "
                "the better the AI will match student questions to this answer."
            ),
        }),
    )

    @admin.display(description="Question")
    def question_short(self, obj):
        return obj.question[:90]


# =====================================================
# Job Market Intelligence
# =====================================================
@admin.register(JobMarketData)
class JobMarketDataAdmin(admin.ModelAdmin):
    list_display  = ('career_name', 'demand', 'salary_display', 'top_sectors', 'source_year')
    list_filter   = ('demand', 'source_year')
    search_fields = ('career_name', 'keywords', 'top_sectors')
    list_editable = ('demand',)
    ordering      = ('career_name',)
    fieldsets = (
        (None, {
            'fields': ('career_name', 'keywords', 'demand'),
            'description': 'Keywords are matched against course career_outcomes — use comma-separated lowercase job titles.',
        }),
        ('Salary (monthly gross KES)', {
            'fields': ('salary_min', 'salary_max'),
        }),
        ('Market Info', {
            'fields': ('top_sectors',),
        }),
        ('Source', {
            'fields': ('source_year', 'source_name', 'source_url'),
        }),
    )

    @admin.display(description='Salary Range')
    def salary_display(self, obj):
        return obj.salary_display()


# =====================================================
# AI Call Rate-Limit Log (read-only monitoring)
# =====================================================
@admin.register(AICallLog)
class AICallLogAdmin(admin.ModelAdmin):
    list_display  = ('user', 'session_short', 'date', 'call_count')
    list_filter   = ('date',)
    search_fields = ('user__email', 'session_key')
    ordering      = ('-date', '-call_count')
    readonly_fields = ('user', 'session_key', 'date', 'call_count')

    @admin.display(description='Session')
    def session_short(self, obj):
        return obj.session_key[:12] + '…' if obj.session_key else '—'

    def has_add_permission(self, request):  # type: ignore[override]
        return False

    def has_change_permission(self, request, obj=None):  # type: ignore[override]
        return False


# =====================================================
# AI Chat Credit — lifetime message bank
# =====================================================
@admin.register(AIChatCredit)
class AIChatCreditAdmin(admin.ModelAdmin):
    list_display = (
        'user_email', 'free_messages_used', 'paid_messages_remaining',
        'total_paid_ever', 'last_topped_up_at', 'updated_at',
    )
    search_fields = ('user__email',)
    readonly_fields = ('total_paid_ever', 'last_topped_up_at', 'updated_at')
    actions = ['action_topup_credits', 'action_reset_free_usage']

    @admin.display(description='User', ordering='user__email')
    def user_email(self, obj):
        return obj.user.email

    @admin.action(description="Top up selected users by ai_paid_message_limit messages")
    def action_topup_credits(self, request, queryset):
        cfg = CareerConfig.get()
        top_up = getattr(cfg, 'ai_paid_message_limit', 200)
        for credit in queryset:
            credit.top_up(top_up)
        self.message_user(request, f"Topped up {queryset.count()} user(s) by {top_up} messages.")

    @admin.action(description="Reset free message counter to 0")
    def action_reset_free_usage(self, request, queryset):
        updated = queryset.update(free_messages_used=0)
        self.message_user(request, f"Reset free usage counter for {updated} user(s).")

    def has_add_permission(self, request):  # type: ignore[override]  # noqa: ARG002
        return False


# =====================================================
# Submission Lock Config
# =====================================================
@admin.register(SubmissionLockConfig)
class SubmissionLockConfigAdmin(admin.ModelAdmin):
    list_display = ('feature', 'lock_minutes', 'is_enabled', 'allow_official_resubmit')
    list_editable = ('lock_minutes', 'is_enabled', 'allow_official_resubmit')
    ordering = ('feature',)


# =====================================================
# Career Submissions (grade lock per user)
# =====================================================
@admin.register(CareerSubmission)
class CareerSubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'feature', 'status', 'lock_at', 'created_at')
    list_filter = ('feature', 'status')
    search_fields = ('user__email',)
    readonly_fields = ('grades_json', 'created_at', 'updated_at')
    actions = ['unlock_submissions']

    @admin.action(description='Unlock selected submissions (reset grace period — 5 min to edit)')
    def unlock_submissions(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        count = queryset.update(
            status=CareerSubmission.STATUS_PENDING,
            lock_at=timezone.now() + timedelta(minutes=5),
        )
        self.message_user(request, f"{count} submission(s) unlocked. Users have 5 minutes to edit.")
