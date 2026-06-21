import csv
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

staff_only = user_passes_test(lambda u: u.is_active and u.is_staff, login_url='/accounts/login/')

VALID_DAYS = {7, 30, 90, 365}


def _parse_days(request):
    try:
        d = int(request.GET.get('days', 30))
        return d if d in VALID_DAYS else 30
    except (ValueError, TypeError):
        return 30


def _date_labels(days, start):
    return [(start + timedelta(days=i)).isoformat() for i in range(days + 1)]


def _fill_series(qs_by_day, date_labels):
    mapping = {str(row['day']): row['n'] for row in qs_by_day}
    return [mapping.get(dt, 0) for dt in date_labels]


def _trend(current, previous):
    """Return pct change and direction vs previous period."""
    if previous == 0:
        return {'pct': None, 'up': True, 'neutral': previous == 0}
    pct = round((current - previous) / previous * 100)
    return {'pct': abs(pct), 'up': pct >= 0, 'neutral': False}


@staff_only
def analytics_dashboard(request):
    from .models import CareerEngineLog, DownloadLog, EventLog, SearchLog, ViewLog
    from accounts.models import SavedCourse, User
    from payments.models import Payment

    days     = _parse_days(request)
    today    = date.today()
    ago      = today - timedelta(days=days)
    prev_ago = today - timedelta(days=days * 2)
    labels   = _date_labels(days, ago)

    # ── User metrics ──────────────────────────────────────────────────────────
    total_users   = User.objects.count()
    new_users     = User.objects.filter(date_joined__date__gte=ago).count()
    prev_new      = User.objects.filter(date_joined__date__gte=prev_ago, date_joined__date__lt=ago).count()
    new_today     = User.objects.filter(date_joined__date=today).count()
    google_users  = User.objects.filter(is_google_user=True).count()
    verified      = User.objects.filter(is_verified=True).count()
    verified_pct  = round(verified / max(total_users, 1) * 100)
    google_pct    = round(google_users / max(total_users, 1) * 100)
    trend_users   = _trend(new_users, prev_new)

    # ── Search metrics ────────────────────────────────────────────────────────
    total_searches = SearchLog.objects.filter(created_at__date__gte=ago).count()
    prev_searches  = SearchLog.objects.filter(created_at__date__gte=prev_ago, created_at__date__lt=ago).count()
    searches_today = SearchLog.objects.filter(created_at__date=today).count()
    zero_result    = SearchLog.objects.filter(created_at__date__gte=ago, result_count=0).count()
    zero_pct       = round(zero_result / max(total_searches, 1) * 100, 1)
    trend_searches = _trend(total_searches, prev_searches)

    # ── View metrics ──────────────────────────────────────────────────────────
    total_views  = ViewLog.objects.filter(created_at__date__gte=ago).count()
    prev_views   = ViewLog.objects.filter(created_at__date__gte=prev_ago, created_at__date__lt=ago).count()
    views_today  = ViewLog.objects.filter(created_at__date=today).count()
    trend_views  = _trend(total_views, prev_views)

    # ── Career engine metrics ─────────────────────────────────────────────────
    total_engine = CareerEngineLog.objects.filter(created_at__date__gte=ago).count()
    prev_engine  = CareerEngineLog.objects.filter(created_at__date__gte=prev_ago, created_at__date__lt=ago).count()
    engine_today = CareerEngineLog.objects.filter(created_at__date=today).count()
    avg_results  = CareerEngineLog.objects.filter(created_at__date__gte=ago).aggregate(a=Avg('result_count'))['a'] or 0
    trend_engine = _trend(total_engine, prev_engine)

    # ── Downloads ─────────────────────────────────────────────────────────────
    total_downloads = DownloadLog.objects.filter(created_at__date__gte=ago).count()
    prev_downloads  = DownloadLog.objects.filter(created_at__date__gte=prev_ago, created_at__date__lt=ago).count()
    trend_downloads = _trend(total_downloads, prev_downloads)

    # ── Saves ────────────────────────────────────────────────────────────────
    total_saves = SavedCourse.objects.count()

    # ── Payment metrics ───────────────────────────────────────────────────────
    pay_qs         = Payment.objects.filter(created_at__date__gte=ago)
    pay_initiated  = pay_qs.count()
    pay_completed  = pay_qs.filter(status='completed').count()
    pay_failed     = pay_qs.filter(status='failed').count()
    pay_pending    = pay_qs.filter(status='pending').count()
    revenue        = pay_qs.filter(status='completed').aggregate(t=Sum('amount'))['t'] or Decimal('0')
    success_rate   = round(pay_completed / max(pay_initiated, 1) * 100)
    prev_revenue   = (Payment.objects.filter(
        created_at__date__gte=prev_ago, created_at__date__lt=ago, status='completed'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0'))
    trend_revenue  = _trend(float(revenue), float(prev_revenue))

    pay_by_feature = list(
        pay_qs.filter(status='completed')
        .values('feature').annotate(n=Count('id'), total=Sum('amount')).order_by('-total')
    )

    recent_payments = list(
        Payment.objects.select_related('user').order_by('-created_at')[:20]
        .values('user__email', 'feature', 'amount', 'status', 'created_at')
    )

    # ── Auth split ────────────────────────────────────────────────────────────
    auth_searches = SearchLog.objects.filter(created_at__date__gte=ago, user__isnull=False).count()
    auth_engine   = CareerEngineLog.objects.filter(created_at__date__gte=ago, user__isnull=False).count()
    auth_searches_pct = round(auth_searches / max(total_searches, 1) * 100)

    # ── Top content ───────────────────────────────────────────────────────────
    top_queries = list(
        SearchLog.objects.filter(created_at__date__gte=ago)
        .values('query').annotate(n=Count('id'), zeros=Count('id', filter=Q(result_count=0)))
        .order_by('-n')[:20]
    )
    zero_queries = list(
        SearchLog.objects.filter(created_at__date__gte=ago, result_count=0)
        .values('query').annotate(n=Count('id')).order_by('-n')[:15]
    )
    top_courses  = list(
        ViewLog.objects.filter(created_at__date__gte=ago, content_type='course')
        .values('object_name').annotate(n=Count('id')).order_by('-n')[:10]
    )
    top_insts    = list(
        ViewLog.objects.filter(created_at__date__gte=ago, content_type='institution')
        .values('object_name').annotate(n=Count('id')).order_by('-n')[:10]
    )
    top_saved    = list(
        SavedCourse.objects.values('course__name', 'course__course_type__name')
        .annotate(n=Count('id')).order_by('-n')[:10]
    )
    top_downloads = list(
        DownloadLog.objects.filter(created_at__date__gte=ago)
        .values('object_name', 'content_type').annotate(n=Count('id')).order_by('-n')[:12]
    )

    # ── Career engine detail ──────────────────────────────────────────────────
    pathway_dist = list(
        CareerEngineLog.objects.filter(created_at__date__gte=ago)
        .values('pathway').annotate(n=Count('id')).order_by('-n')
    )
    top_grades = list(
        CareerEngineLog.objects.filter(created_at__date__gte=ago).exclude(mean_grade='')
        .values('mean_grade').annotate(n=Count('id')).order_by('-n')[:10]
    )

    # ── Recent user sign-ups ──────────────────────────────────────────────────
    recent_users = list(
        User.objects.order_by('-date_joined')[:20]
        .values('email', 'full_name', 'is_google_user', 'is_verified', 'date_joined')
    )

    # ── Activity feed — merged last 60 events ─────────────────────────────────
    feed_items = []
    for s in SearchLog.objects.order_by('-created_at')[:20].values('query', 'result_count', 'created_at'):
        feed_items.append({'type': 'search', 'label': f'Search: "{s["query"]}"',
                           'sub': f'{s["result_count"]} results', 'ts': s['created_at']})
    for v in ViewLog.objects.order_by('-created_at')[:20].values('object_name', 'content_type', 'created_at'):
        feed_items.append({'type': 'view', 'label': f'Viewed {v["content_type"]}: {v["object_name"]}',
                           'sub': '', 'ts': v['created_at']})
    for e in CareerEngineLog.objects.order_by('-created_at')[:15].values('pathway', 'result_count', 'created_at'):
        feed_items.append({'type': 'career', 'label': f'Career Engine: {e["pathway"].title()} path',
                           'sub': f'{e["result_count"]} matches', 'ts': e['created_at']})
    for ev in EventLog.objects.order_by('-created_at')[:15].values('name', 'created_at', 'properties'):
        feed_items.append({'type': 'event', 'label': ev['name'].replace('_', ' ').title(),
                           'sub': ', '.join(f'{k}={v}' for k, v in (ev['properties'] or {}).items())[:80],
                           'ts': ev['created_at']})
    feed_items.sort(key=lambda x: x['ts'], reverse=True)
    feed_items = feed_items[:60]

    # ── Time-series (charts) ──────────────────────────────────────────────────
    reg_series = _fill_series(
        User.objects.filter(date_joined__date__gte=ago)
        .annotate(day=TruncDate('date_joined')).values('day').annotate(n=Count('id')).order_by('day'),
        labels,
    )
    search_series = _fill_series(
        SearchLog.objects.filter(created_at__date__gte=ago)
        .annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('id')).order_by('day'),
        labels,
    )
    engine_series = _fill_series(
        CareerEngineLog.objects.filter(created_at__date__gte=ago)
        .annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('id')).order_by('day'),
        labels,
    )
    views_series = _fill_series(
        ViewLog.objects.filter(created_at__date__gte=ago)
        .annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('id')).order_by('day'),
        labels,
    )
    payment_series = _fill_series(
        Payment.objects.filter(created_at__date__gte=ago, status='completed')
        .annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('id')).order_by('day'),
        labels,
    )

    # ── Conversion funnel ─────────────────────────────────────────────────────
    funnel = [
        {'label': 'Page Views',     'n': total_views},
        {'label': 'Searches',       'n': total_searches},
        {'label': 'Career Engine',  'n': total_engine},
        {'label': 'Registered',     'n': new_users},
        {'label': 'Payments',       'n': pay_initiated},
        {'label': 'Paid',           'n': pay_completed},
    ]
    funnel_max = max((f['n'] for f in funnel), default=1)
    for f in funnel:
        f['pct'] = round(f['n'] / max(funnel_max, 1) * 100)

    context = {
        'days': days,
        # User KPIs
        'total_users': total_users, 'new_users': new_users, 'new_today': new_today,
        'google_pct': google_pct, 'verified_pct': verified_pct,
        'trend_users': trend_users, 'google_users': google_users, 'verified': verified,
        # Search KPIs
        'total_searches': total_searches, 'searches_today': searches_today,
        'zero_pct': zero_pct, 'trend_searches': trend_searches,
        # Views
        'total_views': total_views, 'views_today': views_today, 'trend_views': trend_views,
        # Career engine
        'total_engine': total_engine, 'engine_today': engine_today,
        'avg_results': round(avg_results, 1), 'trend_engine': trend_engine,
        # Downloads + saves
        'total_downloads': total_downloads, 'trend_downloads': trend_downloads,
        'total_saves': total_saves,
        # Payments
        'pay_initiated': pay_initiated, 'pay_completed': pay_completed,
        'pay_failed': pay_failed, 'pay_pending': pay_pending,
        'revenue': revenue, 'success_rate': success_rate,
        'trend_revenue': trend_revenue, 'pay_by_feature': pay_by_feature,
        'recent_payments': recent_payments,
        # Auth split
        'auth_searches': auth_searches, 'anon_searches': total_searches - auth_searches,
        'auth_searches_pct': auth_searches_pct,
        'auth_engine': auth_engine, 'anon_engine': total_engine - auth_engine,
        # Tables
        'top_queries': top_queries, 'zero_queries': zero_queries,
        'top_courses': top_courses, 'top_insts': top_insts,
        'top_saved': top_saved, 'top_downloads': top_downloads,
        'pathway_dist': pathway_dist, 'top_grades': top_grades,
        'recent_users': recent_users,
        # Activity feed
        'feed_items': feed_items,
        # Funnel
        'funnel': funnel,
        # Chart JSON
        'chart_labels':   json.dumps(labels),
        'chart_regs':     json.dumps(reg_series),
        'chart_searches': json.dumps(search_series),
        'chart_engine':   json.dumps(engine_series),
        'chart_views':    json.dumps(views_series),
        'chart_payments': json.dumps(payment_series),
        'chart_pw_labels': json.dumps([p['pathway'].title() for p in pathway_dist]),
        'chart_pw_data':   json.dumps([p['n'] for p in pathway_dist]),
        'chart_grade_labels': json.dumps([g['mean_grade'].upper() for g in top_grades]),
        'chart_grade_data':   json.dumps([g['n'] for g in top_grades]),
    }
    return render(request, 'analytics/dashboard.html', context)


@staff_only
def export_csv(request):
    """Download a comprehensive CSV snapshot of key platform metrics."""
    from .models import CareerEngineLog, SearchLog, ViewLog
    from accounts.models import User
    from payments.models import Payment

    days  = _parse_days(request)
    today = date.today()
    ago   = today - timedelta(days=days)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="careernext_analytics_{today}_{days}d.csv"'
    w = csv.writer(response)

    w.writerow([f'CareerNext Analytics Export — last {days} days — {today}'])
    w.writerow([])

    w.writerow(['=== USER REGISTRATIONS BY DAY ==='])
    w.writerow(['Date', 'New Registrations'])
    for row in (User.objects.filter(date_joined__date__gte=ago)
                .annotate(day=TruncDate('date_joined'))
                .values('day').annotate(n=Count('id')).order_by('day')):
        w.writerow([row['day'], row['n']])
    w.writerow([])

    w.writerow(['=== TOP SEARCH QUERIES ==='])
    w.writerow(['Query', 'Count', 'Zero-Result Count'])
    for row in (SearchLog.objects.filter(created_at__date__gte=ago)
                .values('query')
                .annotate(n=Count('id'), zeros=Count('id', filter=Q(result_count=0)))
                .order_by('-n')[:50]):
        w.writerow([row['query'], row['n'], row['zeros']])
    w.writerow([])

    w.writerow(['=== TOP COURSES VIEWED ==='])
    w.writerow(['Course', 'Views'])
    for row in (ViewLog.objects.filter(created_at__date__gte=ago, content_type='course')
                .values('object_name').annotate(n=Count('id')).order_by('-n')[:30]):
        w.writerow([row['object_name'], row['n']])
    w.writerow([])

    w.writerow(['=== CAREER ENGINE PATHWAY DISTRIBUTION ==='])
    w.writerow(['Pathway', 'Uses'])
    for row in (CareerEngineLog.objects.filter(created_at__date__gte=ago)
                .values('pathway').annotate(n=Count('id')).order_by('-n')):
        w.writerow([row['pathway'].title(), row['n']])
    w.writerow([])

    w.writerow(['=== PAYMENT SUMMARY ==='])
    w.writerow(['Feature', 'Completed Payments', 'Revenue (KES)'])
    for row in (Payment.objects.filter(created_at__date__gte=ago, status='completed')
                .values('feature').annotate(n=Count('id'), total=Sum('amount')).order_by('-total')):
        w.writerow([row['feature'], row['n'], row['total']])

    return response


@staff_only
def live_feed_json(request):
    """AJAX endpoint returning the 30 most recent events as JSON."""
    from .models import CareerEngineLog, EventLog, SearchLog, ViewLog
    items = []
    for s in SearchLog.objects.order_by('-created_at')[:10].values('query', 'result_count', 'created_at'):
        items.append({'type': 'search', 'label': f'Search: "{s["query"]}"',
                      'sub': f'{s["result_count"]} results',
                      'ts': s['created_at'].strftime('%H:%M:%S')})
    for v in ViewLog.objects.order_by('-created_at')[:10].values('object_name', 'content_type', 'created_at'):
        items.append({'type': 'view', 'label': f'{v["content_type"].title()}: {v["object_name"]}',
                      'sub': '', 'ts': v['created_at'].strftime('%H:%M:%S')})
    for e in EventLog.objects.order_by('-created_at')[:10].values('name', 'created_at'):
        items.append({'type': 'event', 'label': e['name'].replace('_', ' ').title(),
                      'sub': '', 'ts': e['created_at'].strftime('%H:%M:%S')})
    items.sort(key=lambda x: x['ts'], reverse=True)
    return JsonResponse({'items': items[:30]})
