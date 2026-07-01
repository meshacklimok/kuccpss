import csv
import json
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

staff_only = user_passes_test(lambda u: u.is_active and u.is_staff, login_url='/accounts/login/')

VALID_DAYS = {1, 7, 30, 90, 180, 365}


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


@require_POST
def heartbeat(request):
    """JS pings this every 60 s while the tab is open → keeps SessionLog.last_seen_at fresh."""
    try:
        from .models import SessionLog
        from django.utils import timezone
        sk = request.session.session_key or ''
        if sk:
            SessionLog.objects.filter(session_key=sk).update(last_seen_at=timezone.now())
    except Exception:
        pass
    return JsonResponse({'ok': True})


@csrf_exempt
@require_POST
def pwa_install(request):
    """Receive a PWA install event from the browser."""
    from .models import PWAInstallLog

    platform = request.POST.get('platform', 'unknown')
    if platform not in {'android', 'ios', 'desktop', 'unknown'}:
        platform = 'unknown'

    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or \
         request.META.get('REMOTE_ADDR')

    PWAInstallLog.objects.create(
        platform=platform,
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or '',
        ip=ip or None,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
    )
    return JsonResponse({'ok': True})


@staff_only
def analytics_dashboard(request):
    from .models import CareerEngineLog, DownloadLog, EventLog, PWAInstallLog, SearchLog, ViewLog
    from accounts.models import SavedCourse, User
    from payments.models import Payment

    days     = _parse_days(request)
    today    = date.today()
    ago      = today - timedelta(days=days)
    prev_ago = today - timedelta(days=days * 2)
    labels   = _date_labels(days, ago)

    # ── User metrics ──────────────────────────────────────────────────────────
    total_users   = User.objects.count()
    new_users     = User.objects.filter(created_at__date__gte=ago).count()
    prev_new      = User.objects.filter(created_at__date__gte=prev_ago, created_at__date__lt=ago).count()
    new_today     = User.objects.filter(created_at__date=today).count()
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

    # ── PWA installs ──────────────────────────────────────────────────────────
    total_pwa_installs  = PWAInstallLog.objects.count()
    pwa_installs_period = PWAInstallLog.objects.filter(created_at__date__gte=ago).count()
    prev_pwa_installs   = PWAInstallLog.objects.filter(created_at__date__gte=prev_ago, created_at__date__lt=ago).count()
    trend_pwa           = _trend(pwa_installs_period, prev_pwa_installs)
    pwa_by_platform     = list(
        PWAInstallLog.objects.values('platform').annotate(n=Count('id')).order_by('-n')
    )
    pwa_series = _fill_series(
        PWAInstallLog.objects.filter(created_at__date__gte=ago)
        .annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('id')).order_by('day'),
        labels,
    )

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
        User.objects.order_by('-created_at')[:20]
        .values('email', 'full_name', 'is_google_user', 'is_verified', 'created_at')
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
        User.objects.filter(created_at__date__gte=ago)
        .annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('id')).order_by('day'),
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

    # ── Feedback ──────────────────────────────────────────────────────────────
    from resources.models import SiteFeedback
    feedback_new       = SiteFeedback.objects.filter(status='new').count()
    feedback_total     = SiteFeedback.objects.count()
    feedback_period    = SiteFeedback.objects.filter(created_at__date__gte=ago).count()
    feedback_by_type   = list(
        SiteFeedback.objects.values('feedback_type').annotate(n=Count('id')).order_by('-n')
    )
    feedback_by_status = list(
        SiteFeedback.objects.values('status').annotate(n=Count('id')).order_by('-n')
    )
    recent_feedback    = list(
        SiteFeedback.objects.order_by('-created_at')[:50]
        .values('id', 'feedback_type', 'message', 'email', 'page_url', 'status', 'created_at')
    )

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
        # PWA installs
        'total_pwa_installs': total_pwa_installs,
        'pwa_installs_period': pwa_installs_period,
        'trend_pwa': trend_pwa,
        'pwa_by_platform': pwa_by_platform,
        'chart_pwa': json.dumps(pwa_series),
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
        # Feedback
        'feedback_new': feedback_new, 'feedback_total': feedback_total,
        'feedback_period': feedback_period,
        'feedback_by_type': feedback_by_type, 'feedback_by_status': feedback_by_status,
        'recent_feedback': recent_feedback,
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
        'day_options': [1, 7, 30, 90, 180, 365],
        # External monitoring services
        'posthog_configured': bool(getattr(settings, 'POSTHOG_API_KEY', '')),
        'posthog_app_url':    ('https://eu.posthog.com' if 'eu.' in getattr(settings, 'POSTHOG_HOST', 'eu') else 'https://app.posthog.com'),
        'sentry_configured':  bool(getattr(settings, '_SENTRY_DSN', '')),
        'ga_configured':      bool(getattr(settings, 'GA_MEASUREMENT_ID', '')),
        'ga_measurement_id':  getattr(settings, 'GA_MEASUREMENT_ID', ''),
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
    for row in (User.objects.filter(created_at__date__gte=ago)
                .annotate(day=TruncDate('created_at'))
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
def mentor_analytics(request):
    from mentorship.models import MentorProfile, MentorshipSession
    from django.db.models import Max

    sort = request.GET.get('sort', 'earnings')
    sort_map = {
        'earnings': '-total_earned',
        'sessions': '-completed_count',
        'rating':   '-average_rating',
        'balance':  '-wallet_balance',
    }
    order_by = sort_map.get(sort, '-total_earned')

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_mentors       = MentorProfile.objects.count()
    approved            = MentorProfile.objects.filter(is_approved=True, is_active=True).count()
    pending             = MentorProfile.objects.filter(is_approved=False, is_rejected=False).count()
    rejected            = MentorProfile.objects.filter(is_rejected=True).count()
    inactive            = MentorProfile.objects.filter(is_active=False).count()
    total_sessions      = MentorshipSession.objects.count()
    completed_sessions  = MentorshipSession.objects.filter(status='completed').count()
    pending_sessions    = MentorshipSession.objects.filter(status='confirmed').count()
    cancelled_sessions  = MentorshipSession.objects.filter(status='cancelled').count()
    total_revenue       = MentorshipSession.objects.filter(status='completed').aggregate(
        t=Sum('amount'))['t'] or 0
    total_mentor_payout = MentorshipSession.objects.filter(status='completed').aggregate(
        t=Sum('mentor_payout'))['t'] or 0
    total_wallet_balance = MentorProfile.objects.aggregate(t=Sum('wallet_balance'))['t'] or 0

    # ── Mentor comparison table ───────────────────────────────────────────────
    now = timezone.now()
    mentor_qs = (
        MentorProfile.objects
        .select_related('user', 'course', 'institution')
        .annotate(
            completed_count=Count('sessions', filter=Q(sessions__status='completed')),
            pending_count=Count('sessions', filter=Q(sessions__status='confirmed')),
            last_session_date=Max('sessions__created_at'),
        )
        .order_by(order_by)
    )
    mentors = []
    for m in mentor_qs:
        age_days = (now - m.created_at).days
        unserious = (m.completed_count == 0 and age_days > 14)
        mentors.append({'profile': m, 'unserious': unserious})

    # ── Recent sessions ───────────────────────────────────────────────────────
    recent_sessions = list(
        MentorshipSession.objects
        .select_related('mentor__user', 'mentee', 'course_interest')
        .order_by('-created_at')[:30]
    )

    # ── Monthly chart (last 6 months) ─────────────────────────────────────────
    from django.db.models.functions import TruncMonth
    six_months_ago = now - timedelta(days=180)
    monthly_qs = (
        MentorshipSession.objects
        .filter(status='completed', created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'), payout=Sum('mentor_payout'))
        .order_by('month')
    )
    monthly_labels  = [row['month'].strftime('%b %Y') for row in monthly_qs]
    monthly_counts  = [row['count'] for row in monthly_qs]
    monthly_payouts = [float(row['payout'] or 0) for row in monthly_qs]

    # ── Rating distribution ───────────────────────────────────────────────────
    rating_dist = {}
    for star in range(1, 6):
        rating_dist[star] = MentorshipSession.objects.filter(rating=star).count()

    context = {
        'sort': sort,
        # KPIs
        'total_mentors': total_mentors,
        'approved': approved,
        'pending': pending,
        'rejected': rejected,
        'inactive': inactive,
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
        'pending_sessions': pending_sessions,
        'cancelled_sessions': cancelled_sessions,
        'total_revenue': total_revenue,
        'total_mentor_payout': total_mentor_payout,
        'total_wallet_balance': total_wallet_balance,
        # Tables
        'mentors': mentors,
        'recent_sessions': recent_sessions,
        # Chart JSON
        'chart_monthly_labels':  json.dumps(monthly_labels),
        'chart_monthly_counts':  json.dumps(monthly_counts),
        'chart_monthly_payouts': json.dumps(monthly_payouts),
        'chart_rating_labels':   json.dumps(['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars']),
        'chart_rating_data':     json.dumps([rating_dist[s] for s in range(1, 6)]),
    }
    return render(request, 'analytics/mentor_analytics.html', context)


@staff_only
def affiliate_analytics(request):
    from accounts.models import AffiliateProfile, AffiliateCommission
    from django.db.models.functions import TruncMonth

    sort = request.GET.get('sort', 'earnings')
    sort_map = {
        'earnings':  '-total_earned',
        'balance':   '-wallet_balance',
        'referrals': '-referral_count',
        'rate':      '-commission_rate',
    }
    order_by = sort_map.get(sort, '-total_earned')

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_affiliates     = AffiliateProfile.objects.count()
    active_affiliates    = AffiliateProfile.objects.filter(is_active=True).count()
    total_commissions    = AffiliateCommission.objects.count()
    paid_commissions     = AffiliateCommission.objects.filter(status='paid_out').count()
    pending_commissions  = AffiliateCommission.objects.filter(status='pending').count()
    total_commission_amount = AffiliateCommission.objects.aggregate(
        t=Sum('amount'))['t'] or Decimal('0')
    total_paid_out       = AffiliateCommission.objects.filter(status='paid_out').aggregate(
        t=Sum('amount'))['t'] or Decimal('0')
    total_wallet_balance = AffiliateProfile.objects.aggregate(
        t=Sum('wallet_balance'))['t'] or Decimal('0')

    # ── Affiliate comparison table ────────────────────────────────────────────
    now = timezone.now()
    affiliate_qs = (
        AffiliateProfile.objects
        .select_related('user', 'approved_by')
        .annotate(
            referral_count=Count('commissions'),
            paid_count=Count('commissions', filter=Q(commissions__status='paid_out')),
        )
        .order_by(order_by)
    )
    affiliates = []
    for a in affiliate_qs:
        age_days = (now - a.created_at).days
        unserious = (a.is_active and a.referral_count == 0 and age_days > 30)
        affiliates.append({'profile': a, 'unserious': unserious})

    # ── Recent commissions ────────────────────────────────────────────────────
    recent_commissions = list(
        AffiliateCommission.objects
        .select_related('affiliate__user', 'referred_user')
        .order_by('-created_at')[:30]
    )

    # ── Monthly chart (last 6 months) ─────────────────────────────────────────
    six_months_ago = now - timedelta(days=180)
    monthly_qs = (
        AffiliateCommission.objects
        .filter(status='paid_out', created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('month')
    )
    monthly_labels = [row['month'].strftime('%b %Y') for row in monthly_qs]
    monthly_counts = [row['count'] for row in monthly_qs]
    monthly_totals = [float(row['total'] or 0) for row in monthly_qs]

    context = {
        'sort': sort,
        # KPIs
        'total_affiliates': total_affiliates,
        'active_affiliates': active_affiliates,
        'inactive_affiliates': total_affiliates - active_affiliates,
        'total_commissions': total_commissions,
        'paid_commissions': paid_commissions,
        'pending_commissions': pending_commissions,
        'total_commission_amount': total_commission_amount,
        'total_paid_out': total_paid_out,
        'total_wallet_balance': total_wallet_balance,
        # Tables
        'affiliates': affiliates,
        'recent_commissions': recent_commissions,
        # Chart JSON
        'chart_monthly_labels': json.dumps(monthly_labels),
        'chart_monthly_counts': json.dumps(monthly_counts),
        'chart_monthly_totals': json.dumps(monthly_totals),
        'chart_status_labels':  json.dumps(['Active', 'Inactive']),
        'chart_status_data':    json.dumps([active_affiliates, total_affiliates - active_affiliates]),
    }
    return render(request, 'analytics/affiliate_analytics.html', context)


def _fmt_duration(td):
    """Timedelta → '4m 32s' string."""
    if not td:
        return '—'
    total_s = max(0, int(td.total_seconds()))
    m, s = divmod(total_s, 60)
    return f'{m}m {s:02d}s' if m else f'{s}s'


@staff_only
def pages_analytics(request):
    """Top pages, session duration, device breakdown, slow pages, and 4xx/5xx errors."""
    from django.db.models import DurationField, ExpressionWrapper, F as _F
    from .models import PageViewLog, SessionLog

    days  = _parse_days(request)
    today = date.today()
    ago   = today - timedelta(days=days)

    total_hits  = PageViewLog.objects.filter(created_at__date__gte=ago).count()
    human_hits  = PageViewLog.objects.filter(created_at__date__gte=ago).exclude(device='bot').count()
    bot_hits    = total_hits - human_hits
    errors_4xx  = PageViewLog.objects.filter(created_at__date__gte=ago, status_code__gte=400, status_code__lt=500).count()
    errors_5xx  = PageViewLog.objects.filter(created_at__date__gte=ago, status_code__gte=500).count()
    hits_today  = PageViewLog.objects.filter(created_at__date=today).count()
    avg_ms      = PageViewLog.objects.filter(created_at__date__gte=ago).exclude(device='bot').aggregate(a=Avg('response_time_ms'))['a'] or 0

    # ── Session duration ──────────────────────────────────────────────────────
    session_qs = SessionLog.objects.filter(created_at__date__gte=ago).exclude(device='bot')
    total_sessions   = session_qs.count()
    bounce_sessions  = session_qs.filter(page_count=1).count()
    engaged_sessions = session_qs.filter(page_count__gte=5).count()
    bounce_rate      = round(bounce_sessions / max(total_sessions, 1) * 100)

    duration_ann = session_qs.filter(page_count__gte=2).annotate(
        dur=ExpressionWrapper(_F('last_seen_at') - _F('created_at'), output_field=DurationField())
    )
    avg_duration_td  = duration_ann.aggregate(avg=Avg('dur'))['avg']
    avg_duration_str = _fmt_duration(avg_duration_td)
    avg_duration_s   = int(avg_duration_td.total_seconds()) if avg_duration_td else 0

    # Distribution buckets: <30s, 30s–2m, 2–5m, 5–15m, >15m
    def _bucket(qs, lo, hi):
        f = {}
        if lo is not None:
            f['last_seen_at__gte'] = _F('created_at') + timedelta(seconds=lo)
        if hi is not None:
            f['last_seen_at__lt']  = _F('created_at') + timedelta(seconds=hi)
        return qs.filter(**f).count()

    duration_buckets = [
        {'label': '<30s',   'n': _bucket(session_qs, None, 30)},
        {'label': '30s–2m', 'n': _bucket(session_qs, 30, 120)},
        {'label': '2–5m',   'n': _bucket(session_qs, 120, 300)},
        {'label': '5–15m',  'n': _bucket(session_qs, 300, 900)},
        {'label': '>15m',   'n': _bucket(session_qs, 900, None)},
    ]

    # ── Geo breakdown ─────────────────────────────────────────────────────────
    geo_qs = session_qs.exclude(country='')
    top_countries = list(
        geo_qs.values('country').annotate(n=Count('id')).order_by('-n')[:15]
    )
    # Kenya sessions → break down by region (county)
    top_counties = list(
        geo_qs.filter(country='Kenya').exclude(region='')
        .values('region').annotate(n=Count('id')).order_by('-n')[:47]
    )
    kenya_sessions = geo_qs.filter(country='Kenya').count()
    total_geo      = geo_qs.count()

    top_pages = list(
        PageViewLog.objects.filter(created_at__date__gte=ago).exclude(device='bot')
        .values('path').annotate(
            hits=Count('id'),
            unique_sessions=Count('session_key', distinct=True),
            avg_ms=Avg('response_time_ms'),
            errors=Count('id', filter=Q(status_code__gte=400)),
        ).order_by('-hits')[:50]
    )

    device_dist = list(
        PageViewLog.objects.filter(created_at__date__gte=ago)
        .values('device').annotate(n=Count('id')).order_by('-n')
    )

    status_dist = list(
        PageViewLog.objects.filter(created_at__date__gte=ago)
        .values('status_code').annotate(n=Count('id')).order_by('status_code')
    )

    slow_pages = list(
        PageViewLog.objects.filter(created_at__date__gte=ago, response_time_ms__gt=2000).exclude(device='bot')
        .values('path').annotate(n=Count('id'), avg_ms=Avg('response_time_ms'))
        .order_by('-avg_ms')[:20]
    )

    error_pages = list(
        PageViewLog.objects.filter(created_at__date__gte=ago, status_code__gte=400)
        .values('path', 'status_code').annotate(n=Count('id')).order_by('-n')[:30]
    )

    recent_errors = list(
        PageViewLog.objects.filter(created_at__date__gte=ago, status_code__gte=400)
        .order_by('-created_at')[:40]
        .values('path', 'status_code', 'method', 'referrer', 'ip', 'created_at')
    )

    labels     = _date_labels(days, ago)
    hit_series = _fill_series(
        PageViewLog.objects.filter(created_at__date__gte=ago).exclude(device='bot')
        .annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('id')).order_by('day'),
        labels,
    )

    context = {
        'days': days, 'day_options': [1, 7, 30, 90, 180, 365],
        'total_hits': total_hits, 'human_hits': human_hits, 'bot_hits': bot_hits,
        'errors_4xx': errors_4xx, 'errors_5xx': errors_5xx,
        'hits_today': hits_today, 'avg_ms': round(avg_ms),
        'top_pages': top_pages, 'slow_pages': slow_pages,
        'error_pages': error_pages, 'recent_errors': recent_errors,
        'device_dist': device_dist, 'status_dist': status_dist,
        # Session / time-on-site
        'total_sessions': total_sessions,
        'bounce_sessions': bounce_sessions, 'engaged_sessions': engaged_sessions,
        'bounce_rate': bounce_rate,
        'avg_duration_str': avg_duration_str,
        'avg_duration_s': avg_duration_s,
        'duration_buckets': duration_buckets,
        # Geo
        'top_countries': top_countries,
        'top_counties': top_counties,
        'kenya_sessions': kenya_sessions,
        'total_geo': total_geo,
        # Charts
        'chart_labels':           json.dumps(labels),
        'chart_hits':             json.dumps(hit_series),
        'chart_device_labels':    json.dumps([d['device'].title() for d in device_dist]),
        'chart_device_data':      json.dumps([d['n'] for d in device_dist]),
        'chart_dur_labels':       json.dumps([b['label'] for b in duration_buckets]),
        'chart_dur_data':         json.dumps([b['n'] for b in duration_buckets]),
        'chart_county_labels':    json.dumps([c['region'] for c in top_counties[:20]]),
        'chart_county_data':      json.dumps([c['n'] for c in top_counties[:20]]),
    }
    return render(request, 'analytics/pages.html', context)


@staff_only
def actions_analytics(request):
    """User action breakdown: logins, shortlists, quiz completions, etc."""
    from .models import UserActionLog

    days  = _parse_days(request)
    today = date.today()
    ago   = today - timedelta(days=days)

    total_actions  = UserActionLog.objects.filter(created_at__date__gte=ago).count()
    actions_today  = UserActionLog.objects.filter(created_at__date=today).count()

    action_dist = list(
        UserActionLog.objects.filter(created_at__date__gte=ago)
        .values('action').annotate(n=Count('id')).order_by('-n')
    )

    logins_ok   = UserActionLog.objects.filter(created_at__date__gte=ago, action='login').count()
    logins_fail = UserActionLog.objects.filter(created_at__date__gte=ago, action='login_failed').count()
    logouts     = UserActionLog.objects.filter(created_at__date__gte=ago, action='logout').count()
    shortlists  = UserActionLog.objects.filter(created_at__date__gte=ago, action='shortlist_add').count()
    ai_chats    = UserActionLog.objects.filter(created_at__date__gte=ago, action='ai_chat').count()
    quiz_done   = UserActionLog.objects.filter(created_at__date__gte=ago, action='quiz_complete').count()

    recent_actions = list(
        UserActionLog.objects.filter(created_at__date__gte=ago)
        .select_related('user').order_by('-created_at')[:60]
        .values('action', 'user__email', 'ip', 'properties', 'created_at')
    )

    labels         = _date_labels(days, ago)
    action_series  = _fill_series(
        UserActionLog.objects.filter(created_at__date__gte=ago)
        .annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('id')).order_by('day'),
        labels,
    )
    login_series   = _fill_series(
        UserActionLog.objects.filter(created_at__date__gte=ago, action='login')
        .annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('id')).order_by('day'),
        labels,
    )

    context = {
        'days': days, 'day_options': [1, 7, 30, 90, 180, 365],
        'total_actions': total_actions, 'actions_today': actions_today,
        'action_dist': action_dist,
        'logins_ok': logins_ok, 'logins_fail': logins_fail,
        'logouts': logouts, 'shortlists': shortlists,
        'ai_chats': ai_chats, 'quiz_done': quiz_done,
        'recent_actions': recent_actions,
        'chart_labels':       json.dumps(labels),
        'chart_actions':      json.dumps(action_series),
        'chart_logins':       json.dumps(login_series),
        'chart_act_labels':   json.dumps([a['action'].replace('_', ' ').title() for a in action_dist]),
        'chart_act_data':     json.dumps([a['n'] for a in action_dist]),
    }
    return render(request, 'analytics/actions.html', context)


@staff_only
def user_timeline(request, user_pk):
    """Full activity timeline for a single user."""
    from django.shortcuts import get_object_or_404
    from accounts.models import User
    from .models import (
        CareerEngineLog, DownloadLog, EventLog,
        PageViewLog, SearchLog, UserActionLog, ViewLog,
    )

    target = get_object_or_404(User, pk=user_pk)
    days   = _parse_days(request)
    today  = date.today()
    ago    = today - timedelta(days=days)

    events = []

    for r in PageViewLog.objects.filter(user=target, created_at__date__gte=ago).order_by('-created_at')[:150]:
        events.append({'type': 'page', 'icon': '🌐',
                       'label': f'{r.method} {r.path}',
                       'sub': f'HTTP {r.status_code} — {r.response_time_ms} ms',
                       'ts': r.created_at})

    for r in SearchLog.objects.filter(user=target, created_at__date__gte=ago).order_by('-created_at')[:80]:
        events.append({'type': 'search', 'icon': '🔍',
                       'label': f'Search: "{r.query}"',
                       'sub': f'{r.result_count} results', 'ts': r.created_at})

    for r in ViewLog.objects.filter(user=target, created_at__date__gte=ago).order_by('-created_at')[:80]:
        events.append({'type': 'view', 'icon': '👁',
                       'label': f'Viewed {r.content_type}: {r.object_name}',
                       'sub': '', 'ts': r.created_at})

    for r in CareerEngineLog.objects.filter(user=target, created_at__date__gte=ago).order_by('-created_at')[:60]:
        events.append({'type': 'career', 'icon': '🎯',
                       'label': f'Career Engine — {r.pathway.title()} path',
                       'sub': f'{r.result_count} matches, grade {r.mean_grade}',
                       'ts': r.created_at})

    for r in UserActionLog.objects.filter(user=target, created_at__date__gte=ago).order_by('-created_at')[:80]:
        props = ', '.join(f'{k}={v}' for k, v in r.properties.items())[:80]
        events.append({'type': 'action', 'icon': '⚡',
                       'label': r.get_action_display(),
                       'sub': props, 'ts': r.created_at})

    for r in DownloadLog.objects.filter(user=target, created_at__date__gte=ago).order_by('-created_at')[:40]:
        events.append({'type': 'download', 'icon': '⬇',
                       'label': f'Downloaded {r.content_type}: {r.object_name}',
                       'sub': '', 'ts': r.created_at})

    for r in EventLog.objects.filter(user=target, created_at__date__gte=ago).order_by('-created_at')[:40]:
        events.append({'type': 'event', 'icon': '📌',
                       'label': r.name.replace('_', ' ').title(),
                       'sub': '', 'ts': r.created_at})

    events.sort(key=lambda x: x['ts'], reverse=True)

    context = {
        'target': target,
        'events': events[:250],
        'days': days,
        'day_options': [1, 7, 30, 90, 180, 365],
    }
    return render(request, 'analytics/user_timeline.html', context)


@staff_only
def insights_dashboard(request):
    """Peak hours, referral sources, retention, funnels — all in one place."""
    import urllib.parse
    from django.db.models.functions import ExtractHour, ExtractWeekDay
    from .models import PageViewLog, SessionLog, UserActionLog, SearchLog, ViewLog, CareerEngineLog, EventLog

    days  = _parse_days(request)
    today = date.today()
    ago   = today - timedelta(days=days)

    # ── 1. Peak hours heatmap (UTC → EAT = UTC+3) ────────────────────────────
    heatmap_raw = list(
        PageViewLog.objects.filter(created_at__date__gte=ago).exclude(device='bot')
        .annotate(utc_h=ExtractHour('created_at'), utc_dow=ExtractWeekDay('created_at'))
        .values('utc_h', 'utc_dow').annotate(n=Count('id'))
    )
    # grid[dow_0mon][hour_local] = hit count
    grid = [[0] * 24 for _ in range(7)]
    for row in heatmap_raw:
        utc_h = row['utc_h']
        # ExtractWeekDay: 1=Sun, 2=Mon, ..., 7=Sat → convert to 0=Mon..6=Sun
        utc_dow_0mon = (row['utc_dow'] - 2) % 7
        local_h      = (utc_h + 3) % 24
        day_offset   = 1 if (utc_h + 3) >= 24 else 0
        local_dow    = (utc_dow_0mon + day_offset) % 7
        grid[local_dow][local_h] += row['n']
    heatmap_max = max((v for row in grid for v in row), default=1)
    # Precompute intensity level 0-4 for each cell so template avoids arithmetic
    def _heat_level(v, mx):
        if v == 0: return 0
        frac = v / mx
        if frac <= 0.25: return 1
        if frac <= 0.50: return 2
        if frac <= 0.75: return 3
        return 4
    heatmap_grid_with_level = [
        [{'n': grid[d][h], 'level': _heat_level(grid[d][h], heatmap_max)} for h in range(24)]
        for d in range(7)
    ]

    # ── 2. Referral sources ───────────────────────────────────────────────────
    OWN = {'careernext.co.ke', 'www.careernext.co.ke', 'localhost', '127.0.0.1', ''}
    referrer_raw = list(
        PageViewLog.objects.filter(created_at__date__gte=ago).exclude(referrer='')
        .values('referrer').annotate(n=Count('id')).order_by('-n')
    )
    domain_counts: dict[str, int] = {}
    for row in referrer_raw:
        try:
            domain = urllib.parse.urlparse(row['referrer']).netloc.lower().replace('www.', '')
        except Exception:
            domain = ''
        if domain and domain not in OWN:
            domain_counts[domain] = domain_counts.get(domain, 0) + row['n']

    top_referrers = sorted(domain_counts.items(), key=lambda x: -x[1])[:20]
    human_qs      = PageViewLog.objects.filter(created_at__date__gte=ago).exclude(device='bot')
    direct_hits   = human_qs.filter(referrer='').count()
    referred_hits = human_qs.exclude(referrer='').count()
    total_classified = direct_hits + referred_hits
    direct_pct    = round(direct_hits  / max(total_classified, 1) * 100)
    referred_pct  = 100 - direct_pct

    # ── 3. Returning vs new visitors ──────────────────────────────────────────
    active_sessions = SessionLog.objects.filter(created_at__date__gte=ago, user__isnull=False)
    prior_user_ids  = set(
        SessionLog.objects.filter(created_at__date__lt=ago, user__isnull=False)
        .values_list('user_id', flat=True)
    )
    active_user_ids = set(active_sessions.values_list('user_id', flat=True))
    returning_users  = len(active_user_ids & prior_user_ids)
    new_users_active = len(active_user_ids - prior_user_ids)
    total_active     = returning_users + new_users_active
    returning_pct    = round(returning_users / max(total_active, 1) * 100)

    # Avg sessions per authenticated user
    from django.db.models import FloatField
    sessions_per_user = round(
        (SessionLog.objects.filter(created_at__date__gte=ago, user__isnull=False).count()
         / max(len(active_user_ids), 1)),
        1,
    )

    # ── 4. Email / registration funnel ────────────────────────────────────────
    from accounts.models import User, SavedCourse
    from payments.models import Payment

    reg_qs    = User.objects.filter(created_at__date__gte=ago)
    total_reg = reg_qs.count()
    verified  = reg_qs.filter(is_verified=True).count()
    google_reg = reg_qs.filter(is_google_user=True).count()
    paid_new  = User.objects.filter(
        created_at__date__gte=ago,
        payments__status='completed',
    ).distinct().count()
    email_funnel = [
        {'label': 'Registered',     'n': total_reg,  'pct': 100, 'icon': '👤'},
        {'label': 'Email Verified', 'n': verified,   'pct': round(verified  / max(total_reg, 1) * 100), 'icon': '✉️'},
        {'label': 'Paid',           'n': paid_new,   'pct': round(paid_new  / max(total_reg, 1) * 100), 'icon': '💳'},
    ]

    # ── 5. Search → view → shortlist funnel ──────────────────────────────────
    from .models import SearchLog, ViewLog, CareerEngineLog
    searches     = SearchLog.objects.filter(created_at__date__gte=ago).count()
    engine_uses  = CareerEngineLog.objects.filter(created_at__date__gte=ago).count()
    course_views = ViewLog.objects.filter(created_at__date__gte=ago, content_type='course').count()
    saves        = SavedCourse.objects.filter(saved_at__date__gte=ago).count()
    funnel_max   = max(searches, engine_uses, course_views, saves, 1)
    search_funnel = [
        {'label': 'Searches',      'n': searches,     'pct': round(searches     / funnel_max * 100), 'icon': '🔍'},
        {'label': 'Career Engine', 'n': engine_uses,  'pct': round(engine_uses  / funnel_max * 100), 'icon': '🎯'},
        {'label': 'Course Views',  'n': course_views, 'pct': round(course_views / funnel_max * 100), 'icon': '👁'},
        {'label': 'Shortlisted',   'n': saves,        'pct': round(saves        / funnel_max * 100), 'icon': '❤️'},
    ]
    zero_result_pct = round(
        SearchLog.objects.filter(created_at__date__gte=ago, result_count=0).count()
        / max(searches, 1) * 100, 1
    )

    # ── 6. Mentor booking funnel ──────────────────────────────────────────────
    try:
        from mentorship.models import MentorshipSession
        mentor_page_hits = PageViewLog.objects.filter(
            created_at__date__gte=ago, path__contains='/mentorship/'
        ).exclude(device='bot').count()
        bookings   = MentorshipSession.objects.filter(created_at__date__gte=ago).count()
        confirmed  = MentorshipSession.objects.filter(created_at__date__gte=ago, status='confirmed').count()
        m_completed = MentorshipSession.objects.filter(created_at__date__gte=ago, status='completed').count()
        cancelled  = MentorshipSession.objects.filter(created_at__date__gte=ago, status='cancelled').count()
        m_funnel_max = max(mentor_page_hits, bookings, confirmed, m_completed, 1)
        mentor_funnel = [
            {'label': 'Mentorship Page Hits', 'n': mentor_page_hits, 'pct': round(mentor_page_hits / m_funnel_max * 100), 'icon': '🌐'},
            {'label': 'Session Requests',     'n': bookings,         'pct': round(bookings         / m_funnel_max * 100), 'icon': '📅'},
            {'label': 'Confirmed',            'n': confirmed,        'pct': round(confirmed        / m_funnel_max * 100), 'icon': '✅'},
            {'label': 'Completed',            'n': m_completed,      'pct': round(m_completed      / m_funnel_max * 100), 'icon': '🎓'},
        ]
        mentor_cancel_pct = round(cancelled / max(bookings, 1) * 100)
        mentor_ok = True
    except Exception:
        mentor_funnel, mentor_ok = [], False
        mentor_cancel_pct = 0

    # ── 7. Calculator grade distribution ─────────────────────────────────────
    from .models import EventLog
    grade_dist = list(
        EventLog.objects.filter(name='calculator_run', created_at__date__gte=ago)
        .values('properties__mean_grade')
        .annotate(n=Count('id'))
        .order_by('-n')
    )
    # Order by canonical grade scale
    GRADE_ORDER = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'E']
    grade_map = {r['properties__mean_grade']: r['n'] for r in grade_dist if r['properties__mean_grade']}
    grade_dist_ordered = [{'grade': g, 'n': grade_map.get(g, 0)} for g in GRADE_ORDER if g in grade_map]
    total_calc_runs = sum(r['n'] for r in grade_dist_ordered)

    context = {
        'days': days, 'day_options': [1, 7, 30, 90, 180, 365],
        # Heatmap
        'heatmap_grid': heatmap_grid_with_level,
        'heatmap_max': heatmap_max,
        'hour_labels': list(range(24)),
        'dow_labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        # Referrals
        'top_referrers': top_referrers,
        'direct_hits': direct_hits, 'referred_hits': referred_hits,
        'direct_pct': direct_pct, 'referred_pct': referred_pct,
        # Retention
        'returning_users': returning_users, 'new_users_active': new_users_active,
        'total_active': total_active, 'returning_pct': returning_pct,
        'sessions_per_user': sessions_per_user,
        # Reg funnel
        'email_funnel': email_funnel, 'total_reg': total_reg,
        'google_reg': google_reg, 'email_reg': total_reg - google_reg,
        # Search funnel
        'search_funnel': search_funnel, 'zero_result_pct': zero_result_pct,
        # Mentor funnel
        'mentor_funnel': mentor_funnel, 'mentor_ok': mentor_ok,
        'mentor_cancel_pct': mentor_cancel_pct,
        # Grade dist
        'grade_dist': grade_dist_ordered, 'total_calc_runs': total_calc_runs,
        # Chart JSON
        'chart_ref_labels': json.dumps([r[0] for r in top_referrers[:15]]),
        'chart_ref_data':   json.dumps([r[1] for r in top_referrers[:15]]),
        'chart_grade_labels': json.dumps([r['grade'] for r in grade_dist_ordered]),
        'chart_grade_data':   json.dumps([r['n'] for r in grade_dist_ordered]),
        'chart_ret_labels': json.dumps(['Returning', 'New']),
        'chart_ret_data':   json.dumps([returning_users, new_users_active]),
    }
    return render(request, 'analytics/insights.html', context)


@staff_only
def payments_overview(request):
    """Actionable payment dashboard — pending, stale, failed, recent completions."""
    from payments.models import Payment
    from django.utils import timezone

    now   = timezone.now()
    today = date.today()

    status_filter = request.GET.get('status', '')  # '', 'pending', 'failed', 'completed', 'refunded'

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_pending    = Payment.objects.filter(status='pending').count()
    stale_cutoff     = now - timedelta(hours=1)
    stale_pending    = Payment.objects.filter(status='pending', created_at__lte=stale_cutoff).count()
    very_stale       = Payment.objects.filter(status='pending', created_at__lte=now - timedelta(hours=6)).count()
    total_failed     = Payment.objects.filter(status='failed').count()
    completed_today  = Payment.objects.filter(status='completed', created_at__date=today).count()
    revenue_today    = Payment.objects.filter(status='completed', created_at__date=today).aggregate(
        t=Sum('amount'))['t'] or 0
    with_mpesa_code  = Payment.objects.filter(status='pending').exclude(mpesa_code='').count()

    # ── Tables ────────────────────────────────────────────────────────────────
    pending_qs = (
        Payment.objects
        .select_related('user')
        .filter(status='pending')
        .order_by('created_at')          # oldest first so you can see what's stuck
    )

    failed_qs = (
        Payment.objects
        .select_related('user')
        .filter(status='failed')
        .order_by('-created_at')[:50]
    )

    completed_qs = (
        Payment.objects
        .select_related('user')
        .filter(status='completed')
        .order_by('-created_at')[:30]
    )

    refunded_qs = (
        Payment.objects
        .select_related('user')
        .filter(status='refunded')
        .order_by('-created_at')[:20]
    )

    # Apply optional status filter to show a full list
    if status_filter in ('pending', 'failed', 'completed', 'refunded'):
        filtered_qs = (
            Payment.objects
            .select_related('user')
            .filter(status=status_filter)
            .order_by('-created_at')[:200]
        )
    else:
        filtered_qs = None

    # Annotate pending rows with age info
    pending_annotated = []
    for p in pending_qs:
        age_s   = int((now - p.created_at).total_seconds())
        age_min = age_s // 60
        if age_s < 3600:
            age_label = f'{age_min}m ago'
            urgency   = 'ok' if age_min < 10 else 'warn'
        elif age_s < 21600:
            age_label = f'{age_s // 3600}h {(age_s % 3600) // 60}m ago'
            urgency   = 'warn'
        else:
            age_label = f'{age_s // 3600}h ago'
            urgency   = 'err'
        pending_annotated.append({'p': p, 'age_label': age_label, 'urgency': urgency})

    context = {
        # KPIs
        'total_pending': total_pending,
        'stale_pending': stale_pending,
        'very_stale': very_stale,
        'total_failed': total_failed,
        'completed_today': completed_today,
        'revenue_today': revenue_today,
        'with_mpesa_code': with_mpesa_code,
        # Tables
        'pending_annotated': pending_annotated,
        'failed_qs': failed_qs,
        'completed_qs': completed_qs,
        'refunded_qs': refunded_qs,
        'filtered_qs': filtered_qs,
        'status_filter': status_filter,
    }
    return render(request, 'analytics/payments.html', context)


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


GRADE_ORDER = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'E']


@staff_only
def calculator_analytics(request):
    """Cluster-points calculator usage: runs, exports, shares, grade & cluster breakdowns."""
    from .models import EventLog, DownloadLog
    from clusterpoints.models import ClusterCalculationResult

    days  = _parse_days(request)
    today = date.today()
    ago   = today - timedelta(days=days)
    prev_ago = ago - timedelta(days=days)

    runs_qs = EventLog.objects.filter(name='calculator_run', created_at__date__gte=ago)
    total_runs = runs_qs.count()
    prev_runs = EventLog.objects.filter(
        name='calculator_run', created_at__date__gte=prev_ago, created_at__date__lt=ago
    ).count()
    runs_trend = _trend(total_runs, prev_runs)

    guest_runs = runs_qs.filter(properties__auth=False).count()
    auth_runs = runs_qs.filter(properties__auth=True).count()

    pdf_exports = DownloadLog.objects.filter(
        content_type='cluster_pdf', created_at__date__gte=ago
    ).count()
    shares = EventLog.objects.filter(name='calculator_share', created_at__date__gte=ago).count()

    # Daily run trend
    date_labels = _date_labels(days, ago)
    runs_by_day = list(
        runs_qs.annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('id')).order_by('day')
    )
    runs_series = _fill_series(runs_by_day, date_labels)

    # Mean grade distribution
    grade_raw = list(
        runs_qs.values('properties__mean_grade').annotate(n=Count('id'))
    )
    grade_map = {r['properties__mean_grade']: r['n'] for r in grade_raw if r['properties__mean_grade']}
    grade_dist = [{'grade': g, 'n': grade_map.get(g, 0)} for g in GRADE_ORDER if g in grade_map]

    # Average cluster points per cluster
    cluster_stats = list(
        ClusterCalculationResult.objects.filter(created_at__date__gte=ago)
        .values('cluster__name', 'cluster__number')
        .annotate(avg_points=Avg('cluster_points'), n=Count('id'))
        .order_by('-avg_points')
    )
    strongest_clusters = cluster_stats[:10]
    weakest_clusters = sorted(cluster_stats, key=lambda r: r['avg_points'])[:10]

    # Pathway recommendation split — same thresholds as clusterpoints/views.py:_pathway_recommendation
    pathway_buckets = {'degree': 0, 'diploma': 0, 'kmtc_tvet': 0, 'certificate': 0}
    for tp in runs_qs.values_list('properties__total_points', flat=True):
        if tp is None:
            continue
        try:
            tp = float(tp)
        except (TypeError, ValueError):
            continue
        if tp >= 60:
            pathway_buckets['degree'] += 1
        elif tp >= 46:
            pathway_buckets['diploma'] += 1
        elif tp >= 32:
            pathway_buckets['kmtc_tvet'] += 1
        else:
            pathway_buckets['certificate'] += 1

    context = {
        'days': days, 'day_options': [1, 7, 30, 90, 180, 365],
        'total_runs': total_runs, 'runs_trend': runs_trend,
        'guest_runs': guest_runs, 'auth_runs': auth_runs,
        'pdf_exports': pdf_exports, 'shares': shares,
        'grade_dist': grade_dist,
        'strongest_clusters': strongest_clusters,
        'weakest_clusters': weakest_clusters,
        'pathway_buckets': pathway_buckets,
        'chart_run_labels': json.dumps(date_labels),
        'chart_run_data': json.dumps(runs_series),
        'chart_grade_labels': json.dumps([r['grade'] for r in grade_dist]),
        'chart_grade_data': json.dumps([r['n'] for r in grade_dist]),
        'chart_pathway_labels': json.dumps(['Degree', 'Diploma', 'KMTC/TVET', 'Certificate']),
        'chart_pathway_data': json.dumps([
            pathway_buckets['degree'], pathway_buckets['diploma'],
            pathway_buckets['kmtc_tvet'], pathway_buckets['certificate'],
        ]),
    }
    return render(request, 'analytics/calculator.html', context)


@staff_only
def conversion_analytics(request):
    """Course discovery → shortlist conversion: funnel, top/zero-converting courses, institutions."""
    from .models import ViewLog
    from accounts.models import SavedCourse
    from courses.models import Course

    days  = _parse_days(request)
    today = date.today()
    ago   = today - timedelta(days=days)

    course_views_qs = ViewLog.objects.filter(content_type='course', created_at__date__gte=ago)
    total_views = course_views_qs.count()
    total_saves = SavedCourse.objects.filter(saved_at__date__gte=ago).count()

    funnel_max = max(total_views, total_saves, 1)
    funnel = [
        {'label': 'Course Views', 'n': total_views, 'pct': round(total_views / funnel_max * 100), 'icon': '👁'},
        {'label': 'Shortlisted', 'n': total_saves, 'pct': round(total_saves / funnel_max * 100), 'icon': '❤️'},
    ]
    conversion_pct = round(total_saves / max(total_views, 1) * 100, 1)

    # Per-course view counts (object_id = Course.pk)
    view_counts = list(
        course_views_qs.values('object_id').annotate(n=Count('id')).order_by('-n')
    )
    view_map = {r['object_id']: r['n'] for r in view_counts}
    save_counts = list(
        SavedCourse.objects.filter(saved_at__date__gte=ago).values('course_id').annotate(n=Count('id'))
    )
    save_map = {r['course_id']: r['n'] for r in save_counts}

    course_ids = set(view_map.keys()) | set(save_map.keys())
    courses_by_id = {
        c.pk: c for c in Course.objects.filter(id__in=course_ids).select_related('course_type')
    }

    top_converting = []
    zero_conversion = []
    for cid, views in view_map.items():
        course = courses_by_id.get(cid)
        if not course:
            continue
        saves = save_map.get(cid, 0)
        row = {
            'course': course, 'views': views, 'saves': saves,
            'conv_pct': round(saves / views * 100, 1) if views else 0,
        }
        if views >= 5:
            top_converting.append(row)
        if views >= 10 and saves == 0:
            zero_conversion.append(row)
    top_converting.sort(key=lambda r: -r['conv_pct'])
    zero_conversion.sort(key=lambda r: -r['views'])

    # Course-type breakdown
    type_views = list(
        course_views_qs.values('object_id').annotate(n=Count('id'))
    )
    type_view_totals: dict[str, int] = {}
    type_save_totals: dict[str, int] = {}
    for r in type_views:
        c = courses_by_id.get(r['object_id'])
        if c and c.course_type:
            type_view_totals[c.course_type.name] = type_view_totals.get(c.course_type.name, 0) + r['n']
    for cid, saves in save_map.items():
        c = courses_by_id.get(cid)
        if c and c.course_type:
            type_save_totals[c.course_type.name] = type_save_totals.get(c.course_type.name, 0) + saves
    type_breakdown = sorted(
        [{'type': t, 'views': v, 'saves': type_save_totals.get(t, 0)} for t, v in type_view_totals.items()],
        key=lambda r: -r['views'],
    )

    # Top institutions by course views
    inst_totals: dict[str, int] = {}
    for cid, views in view_map.items():
        course = courses_by_id.get(cid)
        if not course:
            continue
        for inst_name in course.offerings.values_list('institution__name', flat=True):
            inst_totals[inst_name] = inst_totals.get(inst_name, 0) + views
    top_institutions = sorted(
        [{'institution': n, 'views': v} for n, v in inst_totals.items()], key=lambda r: -r['views']
    )[:15]

    context = {
        'days': days, 'day_options': [1, 7, 30, 90, 180, 365],
        'total_views': total_views, 'total_saves': total_saves, 'conversion_pct': conversion_pct,
        'funnel': funnel,
        'top_converting': top_converting[:20],
        'zero_conversion': zero_conversion[:20],
        'type_breakdown': type_breakdown,
        'top_institutions': top_institutions,
        'chart_type_labels': json.dumps([r['type'] for r in type_breakdown]),
        'chart_type_views': json.dumps([r['views'] for r in type_breakdown]),
        'chart_type_saves': json.dumps([r['saves'] for r in type_breakdown]),
    }
    return render(request, 'analytics/conversion.html', context)


@staff_only
def retention_analytics(request):
    """Weekly cohort retention grid + returning/new visitor KPIs."""
    from .models import SessionLog
    from accounts.models import User

    days  = _parse_days(request)
    today = date.today()
    ago   = today - timedelta(days=days)

    # Returning vs new (reused from insights_dashboard)
    active_sessions = SessionLog.objects.filter(created_at__date__gte=ago, user__isnull=False)
    prior_user_ids  = set(
        SessionLog.objects.filter(created_at__date__lt=ago, user__isnull=False)
        .values_list('user_id', flat=True)
    )
    active_user_ids = set(active_sessions.values_list('user_id', flat=True))
    returning_users  = len(active_user_ids & prior_user_ids)
    new_users_active = len(active_user_ids - prior_user_ids)
    total_active     = returning_users + new_users_active
    returning_pct    = round(returning_users / max(total_active, 1) * 100)
    sessions_per_user = round(
        active_sessions.count() / max(len(active_user_ids), 1), 1
    )

    # Weekly cohort grid — cap at 12 weeks
    WEEKS = 12
    cohort_start = today - timedelta(weeks=WEEKS)
    cohorts = User.objects.filter(created_at__date__gte=cohort_start).values('id', 'created_at')

    def _week_of(dt):
        return dt.isocalendar()[1], dt.isocalendar()[0]

    cohort_users: dict[tuple, list] = {}
    for u in cohorts:
        wk = (u['created_at'].isocalendar()[0], u['created_at'].isocalendar()[1])
        cohort_users.setdefault(wk, []).append(u['id'])

    active_by_user_week: dict[int, set] = {}
    sessions = SessionLog.objects.filter(
        created_at__date__gte=cohort_start, user__isnull=False
    ).values_list('user_id', 'created_at')
    for uid, dt in sessions:
        wk = (dt.isocalendar()[0], dt.isocalendar()[1])
        active_by_user_week.setdefault(uid, set()).add(wk)

    def _heat_level(v, mx):
        if v == 0: return 0
        frac = v / mx
        if frac <= 0.25: return 1
        if frac <= 0.50: return 2
        if frac <= 0.75: return 3
        return 4

    sorted_cohort_weeks = sorted(cohort_users.keys())
    cohort_grid = []
    for (yr, wk) in sorted_cohort_weeks:
        users = cohort_users[(yr, wk)]
        n_users = len(users)
        row = {'label': f'{yr}-W{wk:02d}', 'n_users': n_users, 'cells': []}
        # week offsets 0..min(WEEKS, weeks since cohort started)
        cohort_monday = date.fromisocalendar(yr, wk, 1)
        max_offset = min(WEEKS, (today - cohort_monday).days // 7)
        for offset in range(max_offset + 1):
            target_date = cohort_monday + timedelta(weeks=offset)
            t_yr, t_wk, _ = target_date.isocalendar()
            active_n = sum(1 for uid in users if (t_yr, t_wk) in active_by_user_week.get(uid, set()))
            pct = round(active_n / max(n_users, 1) * 100)
            row['cells'].append({'pct': pct, 'level': _heat_level(pct, 100)})
        cohort_grid.append(row)

    context = {
        'days': days, 'day_options': [1, 7, 30, 90, 180, 365],
        'returning_users': returning_users, 'new_users_active': new_users_active,
        'total_active': total_active, 'returning_pct': returning_pct,
        'sessions_per_user': sessions_per_user,
        'cohort_grid': cohort_grid,
        'week_offsets': list(range(WEEKS + 1)),
        'chart_ret_labels': json.dumps(['Returning', 'New']),
        'chart_ret_data': json.dumps([returning_users, new_users_active]),
    }
    return render(request, 'analytics/retention.html', context)


@staff_only
def ai_chat_analytics(request):
    """CareerNext AI chat usage: volume, free/paid split, KB hit rate, paywall hits."""
    from .models import EventLog

    days  = _parse_days(request)
    today = date.today()
    ago   = today - timedelta(days=days)
    prev_ago = ago - timedelta(days=days)

    msgs_qs = EventLog.objects.filter(name='ai_chat_message', created_at__date__gte=ago)
    total_messages = msgs_qs.count()
    prev_messages = EventLog.objects.filter(
        name='ai_chat_message', created_at__date__gte=prev_ago, created_at__date__lt=ago
    ).count()
    messages_trend = _trend(total_messages, prev_messages)

    active_users = msgs_qs.filter(user__isnull=False).values('user_id').distinct().count()
    avg_per_user = round(total_messages / max(active_users, 1), 1)

    paid_messages = msgs_qs.filter(properties__is_paid=True).count()
    free_messages = total_messages - paid_messages
    kb_hits = msgs_qs.filter(properties__kb_hit=True).count()
    kb_hit_rate = round(kb_hits / max(total_messages, 1) * 100, 1)

    paywall_hits = EventLog.objects.filter(
        name='ai_chat_paywall_hit', created_at__date__gte=ago
    ).count()

    # Daily message volume
    date_labels = _date_labels(days, ago)
    msgs_by_day = list(
        msgs_qs.annotate(day=TruncDate('created_at')).values('day').annotate(n=Count('id')).order_by('day')
    )
    msgs_series = _fill_series(msgs_by_day, date_labels)

    # AIChatCredit summary
    try:
        from career.models import AIChatCredit
        credit_agg = AIChatCredit.objects.aggregate(
            total_free_used=Sum('free_messages_used'),
            total_paid_ever=Sum('total_paid_ever'),
        )
        total_free_used = credit_agg['total_free_used'] or 0
        total_paid_ever = credit_agg['total_paid_ever'] or 0
    except Exception:
        total_free_used = total_paid_ever = 0

    try:
        from payments.models import Payment
        ai_revenue = Payment.objects.filter(
            feature='ai_chat_access', status='completed', created_at__date__gte=ago
        ).aggregate(total=Sum('amount'))['total'] or 0
    except Exception:
        ai_revenue = 0

    context = {
        'days': days, 'day_options': [1, 7, 30, 90, 180, 365],
        'total_messages': total_messages, 'messages_trend': messages_trend,
        'active_users': active_users, 'avg_per_user': avg_per_user,
        'paid_messages': paid_messages, 'free_messages': free_messages,
        'kb_hit_rate': kb_hit_rate, 'paywall_hits': paywall_hits,
        'total_free_used': total_free_used, 'total_paid_ever': total_paid_ever,
        'ai_revenue': ai_revenue,
        'chart_msg_labels': json.dumps(date_labels),
        'chart_msg_data': json.dumps(msgs_series),
        'chart_split_labels': json.dumps(['Free', 'Paid']),
        'chart_split_data': json.dumps([free_messages, paid_messages]),
    }
    return render(request, 'analytics/ai_chat.html', context)
