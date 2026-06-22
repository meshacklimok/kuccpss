from datetime import date

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin
from .models import InstitutionType, Institution, InstitutionPromotion
from .resources import InstitutionResource, InstitutionTypeResource


@admin.register(InstitutionType)
class InstitutionTypeAdmin(ImportExportModelAdmin):
    resource_classes = [InstitutionTypeResource]

    list_display = ('name', 'slug', 'display_icon_tag', 'display_color_tag')
    search_fields = ('name', 'slug')
    prepopulated_fields = {"slug": ("name",)}

    def display_icon_tag(self, obj):
        return format_html('<i class="{}"></i>', obj.display_icon())
    display_icon_tag.short_description = "Icon"

    def display_color_tag(self, obj):
        color = obj.display_color()
        return format_html('<span style="display:inline-block;width:30px;height:20px;background-color:{};"></span>', color)
    display_color_tag.short_description = "Color"


@admin.register(Institution)
class InstitutionAdmin(ImportExportModelAdmin):
    resource_classes = [InstitutionResource]

    list_display = ('name', 'abbreviation', 'institution_type', 'display_logo_tag', 'display_pdf_tag', 'location', 'website')
    list_filter = ('institution_type',)
    search_fields = ('name', 'slug', 'location', 'website', 'email')
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'abbreviation', 'slug', 'institution_type', 'description')
        }),
        ('Contact Info', {
            'fields': ('location', 'website', 'email', 'phone')
        }),
        ('Media & Files', {
            'fields': ('logo', 'pdf_file')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def display_logo_tag(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="width:50px;height:50px;object-fit:cover;border-radius:5px;">', obj.logo.url)
        return "-"
    display_logo_tag.short_description = "Logo"

    def display_pdf_tag(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank"><i class="fa-solid fa-file-pdf" style="color:red;"></i></a>', obj.pdf_file.url)
        return "-"
    display_pdf_tag.short_description = "PDF"


@admin.register(InstitutionPromotion)
class InstitutionPromotionAdmin(admin.ModelAdmin):
    list_display = (
        'institution', 'tier', 'start_date', 'end_date',
        'live_status_tag', 'days_remaining_tag', 'contact_name',
    )
    list_filter = ('tier',)
    search_fields = ('institution__name', 'contact_name', 'contact_email')
    autocomplete_fields = ('institution',)
    readonly_fields = ('created_at', 'updated_at', 'live_status_tag', 'days_remaining_tag')
    date_hierarchy = 'end_date'

    fieldsets = (
        ('Partnership', {
            'fields': ('institution', 'tier', 'tagline', 'banner_image'),
        }),
        ('Scholarship Details', {
            'classes': ('collapse',),
            'description': 'Only fill in for Scholarship Alert tier.',
            'fields': (
                'scholarship_title', 'scholarship_description',
                'scholarship_amount', 'scholarship_deadline', 'scholarship_link',
            ),
        }),
        ('Campaign Window', {
            'fields': ('start_date', 'end_date', 'live_status_tag', 'days_remaining_tag'),
        }),
        ('Contact / Internal', {
            'classes': ('collapse',),
            'fields': ('contact_name', 'contact_email', 'contact_phone', 'notes'),
        }),
        ('Timestamps', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def live_status_tag(self, obj):
        if not obj.pk:
            return '—'
        today = date.today()
        if obj.start_date > today:
            return mark_safe('<span style="color:#b45309;font-weight:700;">Scheduled</span>')
        if obj.end_date < today:
            return mark_safe('<span style="color:#6b7280;">Expired</span>')
        return mark_safe('<span style="color:#16a34a;font-weight:700;">&#9679; Live</span>')
    live_status_tag.short_description = 'Status'

    def days_remaining_tag(self, obj):
        if not obj.pk:
            return '—'
        today = date.today()
        if obj.end_date < today:
            return mark_safe('<span style="color:#6b7280;">—</span>')
        days = (obj.end_date - today).days
        color = '#dc2626' if days <= 7 else '#d97706' if days <= 30 else '#16a34a'
        return format_html('<span style="color:{};font-weight:700;">{} day{}</span>', color, days, 's' if days != 1 else '')
    days_remaining_tag.short_description = 'Days left'
