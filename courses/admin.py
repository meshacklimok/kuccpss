from django import forms
from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from import_export.formats.base_formats import CSV
from .models import CourseType, CourseCategory, Course, CourseOffering, Review
from .resources import CourseResource, CourseOfferingResource


class CourseOfferingForm(forms.ModelForm):
    cutoff_2024 = forms.FloatField(required=False, label="Cutoff 2024", min_value=0, max_value=84)
    cutoff_2023 = forms.FloatField(required=False, label="Cutoff 2023", min_value=0, max_value=84)
    cutoff_2022 = forms.FloatField(required=False, label="Cutoff 2022", min_value=0, max_value=84)
    cutoff_2021 = forms.FloatField(required=False, label="Cutoff 2021", min_value=0, max_value=84)

    class Meta:
        model = CourseOffering
        fields = ('course', 'institution', 'cutoff_2024', 'cutoff_2023', 'cutoff_2022', 'cutoff_2021')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = kwargs.get('instance')
        if obj and obj.cutoff_points:
            for year in ('2024', '2023', '2022', '2021'):
                val = obj.cutoff_points.get(year)
                if val is not None:
                    self.fields[f'cutoff_{year}'].initial = val

    def save(self, commit=True):
        instance = super().save(commit=False)
        cutoffs = {}
        for year in ('2024', '2023', '2022', '2021'):
            val = self.cleaned_data.get(f'cutoff_{year}')
            if val is not None:
                cutoffs[year] = val
        instance.cutoff_points = cutoffs if cutoffs else None
        if commit:
            instance.save()
        return instance


@admin.register(CourseType)
class CourseTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'display_icon_tag', 'display_color_tag')
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ('name', 'slug')

    def display_icon_tag(self, obj):
        return format_html('<i class="{}"></i>', obj.display_icon())
    display_icon_tag.short_description = "Icon"

    def display_color_tag(self, obj):
        color = obj.display_color()
        return format_html('<span style="display:inline-block;width:30px;height:20px;background-color:{};"></span>', color)
    display_color_tag.short_description = "Color"


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'course_type', 'slug')
    list_filter = ('course_type',)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ('name', 'slug')


class CourseOfferingInline(admin.TabularInline):
    model = CourseOffering
    form = CourseOfferingForm
    extra = 1
    fields = ('institution', 'cutoff_2024', 'cutoff_2023', 'cutoff_2022', 'cutoff_2021')
    autocomplete_fields = ('institution',)


@admin.register(Course)
class CourseAdmin(ImportExportModelAdmin):
    resource_classes = [CourseResource]
    formats = [CSV]

    list_display = ('name', 'course_type', 'category', 'cluster', 'offering_count', 'pdf_icon', 'created_at')
    list_filter = ('course_type', 'category', 'cluster')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ('core_subjects',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CourseOfferingInline]

    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'course_type', 'category', 'cluster', 'description')
        }),
        ('Core Subjects', {
            'fields': ('core_subjects',)
        }),
        ('PDF', {
            'fields': ('pdf_file',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def offering_count(self, obj):
        return obj.offerings.count()
    offering_count.short_description = "Institutions"

    def pdf_icon(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank"><i class="fa-solid fa-file-pdf" style="color:red;"></i></a>', obj.pdf_file.url)
        return "-"
    pdf_icon.short_description = "PDF"


@admin.register(CourseOffering)
class CourseOfferingAdmin(ImportExportModelAdmin):
    resource_classes = [CourseOfferingResource]
    formats = [CSV]
    form = CourseOfferingForm

    list_display = ('course', 'institution', 'latest_cutoff_display')
    list_filter = ('institution__institution_type', 'course__course_type')
    search_fields = ('course__name', 'institution__name')
    autocomplete_fields = ('course', 'institution')
    fields = ('course', 'institution', 'cutoff_2024', 'cutoff_2023', 'cutoff_2022', 'cutoff_2021')

    def latest_cutoff_display(self, obj):
        val = obj.latest_cutoff()
        return f"{val} pts" if val else "-"
    latest_cutoff_display.short_description = "Latest Cutoff"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'rating', 'course', 'institution', 'short_body', 'created_at')
    list_filter = ('rating',)
    search_fields = ('user__email', 'course__name', 'institution__name', 'body')
    readonly_fields = ('created_at',)

    def short_body(self, obj):
        return obj.body[:60] + '…' if len(obj.body) > 60 else obj.body
    short_body.short_description = "Review"
