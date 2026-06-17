import json
from datetime import date, timedelta

from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q
from django.db.models.functions import TruncDate

staff_only = user_passes_test(lambda u: u.is_active and u.is_staff, login_url='/accounts/login/')


def _date_range(days=30):
    today = date.today()
    return [(today - timedelta(days=days - i)).isoformat() for i in range(days + 1)]


def _fill_series(qs_by_day, date_range):
    d = {str(row['day']): row['n'] for row in qs_by_day}
    return [d.get(dt, 0) for dt in date_range]


@staff_only
def analytics_dashboard(request):
    from .models import SearchLog, ViewLog, DownloadLog, CareerEngineLog
    from accounts.models import User, SavedCourse

    today  = date.today()
    ago30  = today - timedelta(days=30)
    ago7   = today - timedelta(days=7)
    dates30 = _date_range(30)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_users   = User.objects.count()
    new_users_30d = User.objects.filter(date_joined__date__gte=ago30).count()
    new_users_7d  = User.objects.filter(date_joined__date__gte=ago7).count()
    verified_pct  = round(User.objects.filter(is_verified=True).count() / max(total_users, 1) * 100)

    total_searches  = SearchLog.objects.count()
    searches_today  = SearchLog.objects.filter(created_at__date=today).count()
    unique_queries  = SearchLog.objects.values('query').distinct().count()
    zero_result_pct = round(
        SearchLog.objects.filter(result_count=0).count() / max(total_searches, 1) * 100, 1
    )

    total_views  = ViewLog.objects.count()
    views_today  = ViewLog.objects.filter(created_at__date=today).count()
    views_7d     = ViewLog.objects.filter(created_at__date__gte=ago7).count()

    total_downloads = DownloadLog.objects.count()
    downloads_7d    = DownloadLog.objects.filter(created_at__date__gte=ago7).count()

    total_saves  = SavedCourse.objects.count()

    total_engine = CareerEngineLog.objects.count()
    engine_today = CareerEngineLog.objects.filter(created_at__date=today).count()
    engine_7d    = CareerEngineLog.objects.filter(created_at__date__gte=ago7).count()

    # ── Search tables ──────────────────────────────────────────────────────────
    top_queries = list(
        SearchLog.objects.values('query')
        .annotate(n=Count('id'), zeros=Count('id', filter=Q(result_count=0)))
        .order_by('-n')[:20]
    )

    zero_result_queries = list(
        SearchLog.objects.filter(result_count=0)
        .values('query').annotate(n=Count('id'))
        .order_by('-n')[:15]
    )

    # ── Content views ──────────────────────────────────────────────────────────
    top_courses_viewed = list(
        ViewLog.objects.filter(content_type='course')
        .values('object_name').annotate(n=Count('id'))
        .order_by('-n')[:10]
    )

    top_insts_viewed = list(
        ViewLog.objects.filter(content_type='institution')
        .values('object_name').annotate(n=Count('id'))
        .order_by('-n')[:10]
    )

    view_type_dist = list(
        ViewLog.objects.values('content_type')
        .annotate(n=Count('id')).order_by('-n')
    )

    # ── Downloads ──────────────────────────────────────────────────────────────
    top_downloads = list(
        DownloadLog.objects.values('object_name', 'content_type')
        .annotate(n=Count('id')).order_by('-n')[:12]
    )

    download_type_dist = list(
        DownloadLog.objects.values('content_type')
        .annotate(n=Count('id')).order_by('-n')
    )

    # ── Saved courses ──────────────────────────────────────────────────────────
    top_saved = list(
        SavedCourse.objects.values('course__name', 'course__course_type__name')
        .annotate(n=Count('id')).order_by('-n')[:10]
    )

    # ── Career engine ──────────────────────────────────────────────────────────
    pathway_dist = list(
        CareerEngineLog.objects.values('pathway')
        .annotate(n=Count('id')).order_by('-n')
    )

    top_grades = list(
        CareerEngineLog.objects.exclude(mean_grade='')
        .values('mean_grade').annotate(n=Count('id'))
        .order_by('-n')[:10]
    )

    # ── Time-series (30 days) ──────────────────────────────────────────────────
    reg_by_day = list(
        User.objects.filter(date_joined__date__gte=ago30)
        .annotate(day=TruncDate('date_joined'))
        .values('day').annotate(n=Count('id')).order_by('day')
    )
    search_by_day = list(
        SearchLog.objects.filter(created_at__date__gte=ago30)
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(n=Count('id')).order_by('day')
    )
    engine_by_day = list(
        CareerEngineLog.objects.filter(created_at__date__gte=ago30)
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(n=Count('id')).order_by('day')
    )
    views_by_day = list(
        ViewLog.objects.filter(created_at__date__gte=ago30)
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(n=Count('id')).order_by('day')
    )

    # ── Auth vs anonymous split ────────────────────────────────────────────────
    auth_searches = SearchLog.objects.filter(user__isnull=False).count()
    auth_engine   = CareerEngineLog.objects.filter(user__isnull=False).count()

    context = {
        # KPIs
        'total_users': total_users, 'new_users_30d': new_users_30d,
        'new_users_7d': new_users_7d, 'verified_pct': verified_pct,
        'total_searches': total_searches, 'searches_today': searches_today,
        'unique_queries': unique_queries, 'zero_result_pct': zero_result_pct,
        'total_views': total_views, 'views_today': views_today, 'views_7d': views_7d,
        'total_downloads': total_downloads, 'downloads_7d': downloads_7d,
        'total_saves': total_saves,
        'total_engine': total_engine, 'engine_today': engine_today, 'engine_7d': engine_7d,
        # tables
        'top_queries': top_queries, 'zero_result_queries': zero_result_queries,
        'top_courses_viewed': top_courses_viewed, 'top_insts_viewed': top_insts_viewed,
        'top_downloads': top_downloads, 'top_saved': top_saved,
        'pathway_dist': pathway_dist, 'top_grades': top_grades,
        'view_type_dist': view_type_dist, 'download_type_dist': download_type_dist,
        # auth split
        'auth_searches': auth_searches, 'anon_searches': total_searches - auth_searches,
        'auth_engine': auth_engine,     'anon_engine': total_engine - auth_engine,
        # Chart.js JSON
        'chart_dates':     json.dumps(dates30),
        'chart_regs':      json.dumps(_fill_series(reg_by_day,    dates30)),
        'chart_searches':  json.dumps(_fill_series(search_by_day, dates30)),
        'chart_engine':    json.dumps(_fill_series(engine_by_day, dates30)),
        'chart_views':     json.dumps(_fill_series(views_by_day,  dates30)),
        'chart_pw_labels': json.dumps([p['pathway'].title() for p in pathway_dist]),
        'chart_pw_data':   json.dumps([p['n'] for p in pathway_dist]),
    }
    return render(request, 'analytics/dashboard.html', context)
