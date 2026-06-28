import csv
from datetime import date, timedelta

from django.conf import settings
from django.contrib import admin
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path

from .models import (
    CareerEngineLog, DownloadLog, EventLog,
    PageViewLog, PWAInstallLog, SearchLog,
    SessionLog, UserActionLog, ViewLog,
)


@admin.action(description="Export selected to CSV")
def export_to_csv(_modeladmin, _request, queryset):
    model = queryset.model
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{model._meta.model_name}_export.csv"'
    writer = csv.writer(response)
    fields = [f.name for f in model._meta.fields]
    writer.writerow(fields)
    for row in queryset.values_list(*fields):
        writer.writerow(row)
    return response


def _overview_view(request):
    from accounts.models import User
    from payments.models import Payment

    today    = date.today()
    week_ago = today - timedelta(days=7)

    stats = {
        'total_users':    User.objects.count(),
        'new_today':      User.objects.filter(created_at__date=today).count(),
        'new_this_week':  User.objects.filter(created_at__date__gte=week_ago).count(),
        'searches_today': SearchLog.objects.filter(created_at__date=today).count(),
        'views_today':    ViewLog.objects.filter(created_at__date=today).count(),
        'page_hits_today': PageViewLog.objects.filter(created_at__date=today).count(),
        'actions_today':  UserActionLog.objects.filter(created_at__date=today).count(),
        'revenue_today':  Payment.objects.filter(
            created_at__date=today, status='completed'
        ).aggregate(t=Sum('amount'))['t'] or 0,
        'revenue_week':   Payment.objects.filter(
            created_at__date__gte=week_ago, status='completed'
        ).aggregate(t=Sum('amount'))['t'] or 0,
    }

    posthog_host    = getattr(settings, 'POSTHOG_HOST', 'https://eu.i.posthog.com')
    posthog_app_url = 'https://eu.posthog.com' if 'eu.' in posthog_host else 'https://app.posthog.com'
    sentry_dsn      = getattr(settings, '_SENTRY_DSN', '') or ''

    context = {
        **admin.site.each_context(request),
        'title':              'Analytics Overview',
        'stats':              stats,
        'posthog_configured': bool(getattr(settings, 'POSTHOG_API_KEY', '')),
        'posthog_embed_url':  getattr(settings, 'POSTHOG_EMBED_URL', ''),
        'posthog_app_url':    posthog_app_url,
        'sentry_configured':  bool(sentry_dsn),
        'sentry_dsn':         sentry_dsn,
        'ga_configured':      bool(getattr(settings, 'GA_MEASUREMENT_ID', '')),
        'ga_measurement_id':  getattr(settings, 'GA_MEASUREMENT_ID', ''),
        'ga_embed_url':       getattr(settings, 'GA_EMBED_URL', ''),
    }
    return render(request, 'admin/analytics/overview.html', context)


@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display   = ('query', 'result_count', 'user', 'created_at')
    list_filter    = ('created_at',)
    search_fields  = ('query',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    actions        = [export_to_csv]

    def get_urls(self):
        return [
            path('overview/', self.admin_site.admin_view(_overview_view), name='analytics-overview'),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context={'show_overview_link': True})


@admin.register(ViewLog)
class ViewLogAdmin(admin.ModelAdmin):
    list_display   = ('content_type', 'object_name', 'user', 'created_at')
    list_filter    = ('content_type', 'created_at')
    search_fields  = ('object_name',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    actions        = [export_to_csv]


@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    list_display   = ('content_type', 'object_name', 'user', 'created_at')
    list_filter    = ('content_type', 'created_at')
    search_fields  = ('object_name',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    actions        = [export_to_csv]


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display   = ('name', 'user', 'ip', 'created_at')
    list_filter    = ('name', 'created_at')
    search_fields  = ('name',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    actions        = [export_to_csv]


@admin.register(PWAInstallLog)
class PWAInstallLogAdmin(admin.ModelAdmin):
    list_display   = ('platform', 'user', 'ip', 'created_at')
    list_filter    = ('platform', 'created_at')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    actions        = [export_to_csv]


@admin.register(CareerEngineLog)
class CareerEngineLogAdmin(admin.ModelAdmin):
    list_display   = ('pathway', 'result_count', 'mean_grade', 'user', 'created_at')
    list_filter    = ('pathway', 'created_at')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    actions        = [export_to_csv]


@admin.register(PageViewLog)
class PageViewLogAdmin(admin.ModelAdmin):
    list_display    = ('path', 'method', 'status_code', 'device', 'response_time_ms', 'user', 'ip', 'created_at')
    list_filter     = ('method', 'status_code', 'device', 'created_at')
    search_fields   = ('path', 'ip')
    readonly_fields = ('created_at',)
    date_hierarchy  = 'created_at'
    actions         = [export_to_csv]


@admin.register(SessionLog)
class SessionLogAdmin(admin.ModelAdmin):
    list_display    = ('session_key', 'user', 'country', 'region', 'device', 'page_count', 'last_seen_at', 'created_at')
    list_filter     = ('device', 'country', 'created_at')
    search_fields   = ('session_key', 'user__email', 'country', 'region', 'ip')
    readonly_fields = ('created_at',)
    date_hierarchy  = 'created_at'
    actions         = [export_to_csv]


@admin.register(UserActionLog)
class UserActionLogAdmin(admin.ModelAdmin):
    list_display    = ('action', 'user', 'ip', 'created_at')
    list_filter     = ('action', 'created_at')
    search_fields   = ('user__email',)
    readonly_fields = ('created_at',)
    date_hierarchy  = 'created_at'
    actions         = [export_to_csv]
