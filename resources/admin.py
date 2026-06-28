from django.contrib import admin
from django.utils.html import format_html
from .models import ResourceCategory, Resource, Article, FAQItem, SuccessStory, SiteSetting, Announcement, SiteFeedback


@admin.register(ResourceCategory)
class ResourceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("order",)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "resource_type", "is_free", "download_count", "created_at")
    list_filter = ("category", "resource_type", "is_free")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("download_count", "created_at", "updated_at")


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "is_published", "featured", "created_at")
    list_filter = ("is_published", "featured")
    search_fields = ("title", "content", "tags")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("featured",)


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display  = ("question_short", "category", "order", "is_active")
    list_filter   = ("category", "is_active")
    search_fields = ("question", "answer")
    list_editable = ("order", "is_active")
    ordering      = ("category", "order")

    fieldsets = (
        (None, {"fields": ("question", "answer")}),
        ("Settings", {"fields": ("category", "order", "is_active")}),
    )

    def question_short(self, obj):
        return obj.question[:80] + ("…" if len(obj.question) > 80 else "")
    question_short.short_description = "Question"


@admin.register(SuccessStory)
class SuccessStoryAdmin(admin.ModelAdmin):
    list_display  = ("name", "county", "course_name", "institution", "pathway", "year", "order", "is_active")
    list_filter   = ("pathway", "is_active")
    search_fields = ("name", "course_name", "institution", "quote")
    list_editable = ("order", "is_active")

    fieldsets = (
        ("Student", {
            "fields": ("name", "initials", "county", "kcse_grade", "work_location"),
        }),
        ("Story", {
            "fields": ("quote",),
        }),
        ("Programme", {
            "fields": ("course_name", "institution", "pathway", "year"),
        }),
        ("Display", {
            "fields": ("avatar_bg", "avatar_color", "order", "is_active"),
            "classes": ("collapse",),
        }),
    )


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display  = ("label", "key", "setting_type", "group", "value_preview")
    list_filter   = ("setting_type", "group")
    search_fields = ("key", "label", "value")
    ordering      = ("group", "key")

    fieldsets = (
        (None, {"fields": ("key", "label", "value")}),
        ("Meta", {"fields": ("setting_type", "group", "help_note"), "classes": ("collapse",)}),
    )

    def value_preview(self, obj):
        v = obj.value
        return (v[:55] + "…") if len(v) > 55 else v
    value_preview.short_description = "Value"


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display  = ('title', 'kind', 'is_active', 'starts_at', 'ends_at', 'created_at')
    list_filter   = ('kind', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('title', 'body')
    readonly_fields = ('created_at',)

    fieldsets = (
        (None, {'fields': ('title', 'body', 'kind', 'is_active')}),
        ('Call to Action', {'fields': ('link_url', 'link_label'), 'classes': ('collapse',)}),
        ('Schedule', {'fields': ('starts_at', 'ends_at'), 'classes': ('collapse',)}),
        ('Meta', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )


@admin.register(SiteFeedback)
class SiteFeedbackAdmin(admin.ModelAdmin):
    list_display  = ('short_message', 'feedback_type', 'status', 'email', 'page_url', 'created_at')
    list_filter   = ('feedback_type', 'status')
    list_editable = ('status',)
    search_fields = ('message', 'email', 'page_url')
    readonly_fields = ('created_at', 'feedback_type', 'message', 'email', 'page_url')

    fieldsets = (
        ('Submission', {'fields': ('feedback_type', 'message', 'email', 'page_url', 'created_at')}),
        ('Review', {'fields': ('status', 'admin_note')}),
    )

    actions = ['mark_resolved', 'mark_dismissed']

    @admin.action(description='Mark selected as Resolved')
    def mark_resolved(self, request, queryset):
        queryset.update(status='resolved')

    @admin.action(description='Mark selected as Dismissed')
    def mark_dismissed(self, request, queryset):
        queryset.update(status='dismissed')

    def short_message(self, obj):
        return obj.message[:70] + ('…' if len(obj.message) > 70 else '')
    short_message.short_description = 'Message'

    def has_add_permission(self, request):
        return False
