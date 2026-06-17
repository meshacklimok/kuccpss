from django.contrib import admin
from .models import SearchLog, ViewLog, DownloadLog, CareerEngineLog


@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display  = ('query', 'result_count', 'user', 'created_at')
    list_filter   = ('created_at',)
    search_fields = ('query',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(ViewLog)
class ViewLogAdmin(admin.ModelAdmin):
    list_display  = ('content_type', 'object_name', 'user', 'created_at')
    list_filter   = ('content_type', 'created_at')
    search_fields = ('object_name',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    list_display  = ('content_type', 'object_name', 'user', 'created_at')
    list_filter   = ('content_type', 'created_at')
    search_fields = ('object_name',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(CareerEngineLog)
class CareerEngineLogAdmin(admin.ModelAdmin):
    list_display  = ('pathway', 'result_count', 'mean_grade', 'user', 'created_at')
    list_filter   = ('pathway', 'created_at')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
