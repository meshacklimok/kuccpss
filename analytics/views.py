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
