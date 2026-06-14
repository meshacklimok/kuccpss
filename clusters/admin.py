# clusters/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Cluster, Subject, SubjectGroup
from .forms import SubjectGroupForm

# ------------------------
# Subject Admin
# ------------------------
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'created_at', 'updated_at')
    search_fields = ('name', 'code')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')


# ------------------------
# SubjectGroup Inline for Cluster
# ------------------------
class SubjectGroupInline(admin.TabularInline):
    model = SubjectGroup
    form = SubjectGroupForm
    extra = 1
    filter_horizontal = ('subjects',)
    verbose_name = "Subject Group"
    verbose_name_plural = "Subject Groups"


# ------------------------
# Cluster Admin
# ------------------------
@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'display_color_tag', 'display_icon_tag', 'image_preview', 'created_at')
    search_fields = ('name',)
    ordering = ('number',)
    inlines = [SubjectGroupInline]
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {'fields': ('number', 'name', 'description')}),
        ('UI / Display', {'fields': ('color_code', 'icon', 'image')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    def display_color_tag(self, obj):
        color = obj.color_code or "#3498db"
        return format_html('<span style="display:inline-block;width:30px;height:20px;background-color:{};"></span>', color)
    display_color_tag.short_description = "Color"

    def display_icon_tag(self, obj):
        icon = obj.icon or "fa-solid fa-graduation-cap"
        return format_html('<i class="{}"></i>', icon)
    display_icon_tag.short_description = "Icon"

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width:60px;height:auto;border-radius:5px;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Image"