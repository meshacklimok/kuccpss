from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import (
    TVETCategory, TVETCourse, KMTCampus, KMTCourse, TTCCollege, TTCCourse,
    CareerInsight,
    CareerProfile, QuizQuestion, QuizOption, QuizSubmission, QuizAnswer,
    CareerConfig, AIKnowledgeEntry, JobMarketData,
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

    def get_course_name(self, obj):
        course_obj = obj.course or obj.tvet_course or obj.kmc_course or obj.ttc_course
        return course_obj.name if course_obj else "N/A"
    get_course_name.short_description = "Course"


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
        ("AI Career Insight (Quiz Results)", {
            "description": (
                "Controls the AI summary shown on the quiz results page. "
                "Uses GPT-4o-mini. Requires OPENAI_API_KEY in .env. "
                "Available placeholders: {tag_str} = student interest tags, {careers_str} = top matched careers."
            ),
            "fields": ("ai_enabled", "ai_prompt_template"),
        }),
    )

    def has_add_permission(self, request):
        return not CareerConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
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

    def question_short(self, obj):
        return obj.question[:90]
    question_short.short_description = "Question"


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

    def salary_display(self, obj):
        return obj.salary_display()
    salary_display.short_description = 'Salary Range'
