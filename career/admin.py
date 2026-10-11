from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import (
    CareerProfile, QuizQuestion, QuizOption, QuizSubmission, QuizAnswer,
    CareerConfig, AIKnowledgeEntry, JobMarketData, AICallLog,
    SubmissionLockConfig, CareerSubmission, AIChatCredit, AIChatLog,
)


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
    list_select_related = ("submission__user", "question", "option__question")
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
        ("CareerNext AI Custom Instructions", {
            "description": (
                "Free-text guidance added to every chat (tone, focus, announcements). "
                "To teach it facts, add verified Q&As under AI Knowledge Base, or promote "
                "good answers from AI Chat Logs."
            ),
            "fields": ("ai_custom_instructions",),
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
# AI Chat Logs — review queue for improving CareerNext AI
# =====================================================
@admin.register(AIChatLog)
class AIChatLogAdmin(admin.ModelAdmin):
    list_display    = ("question_short", "rating", "kb_hit", "tools_short", "review_status", "created_at")
    list_filter     = ("rating", "review_status", "kb_hit", "created_at")
    search_fields   = ("question", "reply", "rating_note")
    list_editable   = ("review_status",)
    readonly_fields = ("user", "question", "reply", "tools_used", "kb_hit", "model_name",
                       "rating", "rating_note", "created_at")
    actions         = ("promote_to_knowledge_base", "mark_reviewed", "mark_ignored")
    date_hierarchy  = "created_at"

    change_list_template = "admin/career/aichatlog/change_list.html"

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        from django.urls import path
        return [path("insights/", self.admin_site.admin_view(self.insights_view),
                     name="career_aichatlog_insights")] + super().get_urls()

    def insights_view(self, request):
        """What to teach the AI next: repeated questions it got wrong or couldn't ground."""
        from collections import Counter
        from django.db.models import Count, Q
        from django.template.response import TemplateResponse
        logs = AIChatLog.objects.exclude(review_status__in=("promoted", "ignored"))
        weak = logs.filter(Q(rating=-1) | Q(kb_hit=False, tools_used=[]))
        norm = Counter()
        sample = {}
        for log in weak.order_by("-created_at")[:1000]:
            key = " ".join(sorted(w for w in log.question.lower().replace("?", " ").split() if len(w) > 3))
            norm[key] += 1
            sample.setdefault(key, log)
        rows = [{"count": n, "log": sample[k]} for k, n in norm.most_common(25) if k]
        total = AIChatLog.objects.count()
        stats = AIChatLog.objects.aggregate(
            up=Count("id", filter=Q(rating=1)), down=Count("id", filter=Q(rating=-1)),
            kb=Count("id", filter=Q(kb_hit=True)),
        )
        ctx = {**self.admin_site.each_context(request), "title": "CareerNext AI — what to teach next",
               "rows": rows, "total": total, **stats, "opts": self.model._meta}
        return TemplateResponse(request, "admin/career/aichatlog/insights.html", ctx)

    @admin.display(description="Question")
    def question_short(self, obj):
        return obj.question[:90]

    @admin.display(description="Tools")
    def tools_short(self, obj):
        return ", ".join(sorted(set(obj.tools_used)))[:60]

    @admin.action(description="Promote to knowledge base (creates INACTIVE drafts to edit)")
    def promote_to_knowledge_base(self, request, queryset):
        made = 0
        for log in queryset.exclude(review_status="promoted").exclude(reply=""):
            AIKnowledgeEntry.objects.create(
                question=log.question[:500], answer=log.reply, is_active=False,
                keywords=",".join(w for w in log.question.lower().split() if len(w) > 3)[:500],
            )
            log.review_status = "promoted"
            log.save(update_fields=["review_status"])
            made += 1
        self.message_user(
            request,
            f"{made} draft(s) added to the AI Knowledge Base. Edit them and tick Active to teach the AI.",
        )

    @admin.action(description="Mark as reviewed")
    def mark_reviewed(self, request, queryset):
        queryset.update(review_status="reviewed")

    @admin.action(description="Mark as ignored")
    def mark_ignored(self, request, queryset):
        queryset.update(review_status="ignored")


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
