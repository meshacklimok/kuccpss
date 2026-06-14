from django.contrib import admin
from .models import (
    KCSEGrade, CourseCategory, University, Course, CourseCutoff, CourseCutoffHistory,
    TVETCategory, TVETCourse, KMTCampus, KMTCourse, TTCCollege, TTCCourse,
    StudentCourseMatch, AIRecommendation, CareerInsight,
    CareerProfile, QuizQuestion, QuizOption, QuizSubmission, QuizAnswer,
)

# =====================================================
# KCSE Grades
# =====================================================
@admin.register(KCSEGrade)
class KCSEGradeAdmin(admin.ModelAdmin):
    list_display = ("subject_name", "grade")
    search_fields = ("subject_name", "grade")
    list_filter = ("grade",)


# =====================================================
# Course Categories
# =====================================================
@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


# =====================================================
# Universities
# =====================================================
@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("name", "county", "description")
    search_fields = ("name", "county")


# =====================================================
# Courses
# =====================================================
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name",)
    list_filter = ("category",)
    filter_horizontal = ("cluster_subjects",)


# =====================================================
# Course Cutoff Points
# =====================================================
@admin.register(CourseCutoff)
class CourseCutoffAdmin(admin.ModelAdmin):
    list_display = ("course", "university", "cutoff_points", "year")
    search_fields = ("course__name", "university__name")
    list_filter = ("year",)


# =====================================================
# Historical Cutoff Trends
# =====================================================
@admin.register(CourseCutoffHistory)
class CourseCutoffHistoryAdmin(admin.ModelAdmin):
    list_display = ("course", "university", "cutoff_points", "year")
    search_fields = ("course__name", "university__name")
    list_filter = ("year",)


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
# Student Course Matches
# =====================================================
@admin.register(StudentCourseMatch)
class StudentCourseMatchAdmin(admin.ModelAdmin):
    list_display = ("get_course_name", "university", "admission_chance", "match_score", "recommended_by_ai", "created_at")
    search_fields = ("course__name", "tvet_course__name", "kmc_course__name", "ttc_course__name")
    list_filter = ("admission_chance", "recommended_by_ai", "created_at")
    readonly_fields = ("match_score", "admission_chance", "recommended_by_ai", "created_at")

    def get_course_name(self, obj):
        course_obj = obj.course or obj.tvet_course or obj.kmc_course or obj.ttc_course
        return course_obj.name if course_obj else "N/A"
    get_course_name.short_description = "Course"


# =====================================================
# AI Recommendations
# =====================================================
@admin.register(AIRecommendation)
class AIRecommendationAdmin(admin.ModelAdmin):
    list_display = ("advice_text", "created_at")
    readonly_fields = ("advice_text", "created_at")
    search_fields = ("advice_text",)


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