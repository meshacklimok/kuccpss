from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from .models import InstitutionType, Institution
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
