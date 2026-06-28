import secrets
import time
from typing import Any, Dict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from kuccpss.email_utils import send_branded_email
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_http_methods
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme

from .decorators import require_recent_auth
from .forms import UserRegistrationForm, UserLoginForm
from .models import (
    User,
    EmailVerificationToken,
    RememberToken,
    DeviceSession,
)


# =====================================================
# Helper
# =====================================================
def get_client_ip(request: HttpRequest) -> str:
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        # Trust the last IP — Render appends the real client IP at the end,
        # preventing spoofing via a forged X-Forwarded-For header.
        return x_forwarded.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '')


def _is_rate_limited(key: str, limit: int, window: int) -> bool:
    """Increment hit counter; return True if over the limit."""
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, window)
    return False


# =====================================================
# REGISTER VIEW (Class-Based)
# =====================================================
class RegisterView(View):
    template_name = "accounts/register.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        form = UserRegistrationForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        ip = get_client_ip(request)
        if _is_rate_limited(f"register:{ip}", limit=5, window=3600):
            messages.error(request, "Too many registration attempts. Please wait 1 hour and try again.")
            return render(request, self.template_name, {"form": UserRegistrationForm()})

        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.is_verified = True
            user.save()

            # Send a welcome / confirm-your-email message in the background (non-blocking)
            token = secrets.token_urlsafe(32)
            EmailVerificationToken.objects.create(user=user, token=token)
            verify_url = request.build_absolute_uri(f"/accounts/verify-email/{token}/")
            try:
                send_branded_email(
                    to=user.email,
                    subject="Welcome to CareerNext — Verify Your Email",
                    heading="Welcome to CareerNext!",
                    banner_label="✓ Account Created",
                    banner_color="green",
                    greeting=f"Hi {user.full_name or user.email},",
                    body_lines=[
                        "Your account is ready and you're already logged in!",
                        "To keep your account secure, please confirm your email address by clicking the button below. This link expires in 24 hours.",
                    ],
                    cta_url=verify_url,
                    cta_label="Verify My Email →",
                    note="If you didn't create a CareerNext account, you can safely ignore this email.",
                    user_email=user.email,
                )
            except Exception:
                pass

            # ── Referral attribution ──────────────────────────────
            ref_code = request.session.pop('referral_code', None)
            if ref_code:
                from accounts.models import Referral as ReferralModel
                try:
                    ref = ReferralModel.objects.get(code=ref_code, converted=False)
                    ref.referred_user  = user
                    ref.referred_email = user.email
                    ref.converted      = True
                    ref.converted_at   = timezone.now()
                    ref.save(update_fields=['referred_user', 'referred_email', 'converted', 'converted_at'])
                except Exception:
                    pass

            # ── Email lead conversion ─────────────────────────────
            try:
                from accounts.models import EmailLead
                EmailLead.objects.filter(email=user.email, converted_to_user__isnull=True).update(
                    converted_to_user=user
                )
            except Exception:
                pass

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            request.session['_auth_verified_at'] = time.time()
            messages.success(request, f"Welcome to CareerNext, {user.full_name or user.email}!")
            return redirect("accounts:dashboard")

        return render(request, self.template_name, {"form": form})


# =====================================================
# EMAIL VERIFICATION VIEW
# =====================================================
@require_http_methods(["GET"])
def email_verify_view(request: HttpRequest, token: str) -> HttpResponse:
    verification = get_object_or_404(
        EmailVerificationToken, token=token, is_used=False
    )
    if not verification.is_valid():
        messages.error(request, "Verification link is invalid or expired.")
        return redirect("accounts:login")

    user = verification.user
    user.is_verified = True
    user.save(update_fields=["is_verified"])

    verification.is_used = True
    verification.save(update_fields=["is_used"])

    messages.success(request, "Email verified successfully. You may now log in.")
    return redirect("accounts:login")


# =====================================================
# LOGIN VIEW (Class-Based)
# =====================================================
class LoginView(View):
    template_name = "accounts/login.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        form = UserLoginForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        ip = get_client_ip(request)
        rl_key = f"login_fail:{ip}"

        # Block IP after 10 failed credential attempts within 15 minutes
        if cache.get(rl_key, 0) >= 10:
            messages.error(request, "Too many failed login attempts. Please wait 15 minutes and try again.")
            return render(request, self.template_name, {"form": UserLoginForm()})

        form = UserLoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["user"]

            # Enforce account status
            if not user.is_active:
                messages.error(request, "Your account is deactivated.")
                return redirect("accounts:login")
            if user.is_suspended:
                messages.error(request, "Your account is suspended.")
                return redirect("accounts:login")

            cache.delete(rl_key)  # Clear fail counter on successful login
            login(request, user)

            # Mark as recently verified (re-auth window starts from login)
            request.session['_auth_verified_at'] = time.time()

            # Mentor sessions are shorter (stricter security)
            try:
                from mentorship.models import MentorProfile
                is_mentor = MentorProfile.objects.filter(user=user).exists()
            except Exception:
                is_mentor = False

            remember_me = form.cleaned_data.get("remember_me")
            if remember_me:
                token = secrets.token_urlsafe(32)
                expires_at = timezone.now() + timezone.timedelta(days=30 if is_mentor else 90)
                RememberToken.objects.create(
                    user=user,
                    token=token,
                    expires_at=expires_at,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
                # Mentors: 30 days with remember me; regular: 90 days
                request.session.set_expiry(30 * 24 * 3600 if is_mentor else 90 * 24 * 3600)
            else:
                # Mentors: 14 days; regular users: 30 days
                request.session.set_expiry(14 * 24 * 3600 if is_mentor else 30 * 24 * 3600)

            messages.success(
                request, f"Welcome back, {user.full_name or user.email}!"
            )
            return redirect("accounts:dashboard")

        # Bad credentials — count this failure toward the rate limit
        fails = cache.get(rl_key, 0) + 1
        cache.set(rl_key, fails, 900)  # 15-minute window
        return render(request, self.template_name, {"form": form})


# =====================================================
# LOGOUT VIEW
# =====================================================
@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect("accounts:login")


# =====================================================
# DASHBOARD VIEW
# =====================================================
def dashboard_view(request: HttpRequest) -> HttpResponse:
    # ── Guest (unauthenticated) fast path ─────────────────────────────────────
    if not request.user.is_authenticated:
        from django.utils import timezone as tz
        from datetime import timezone as _dtz
        from career.models import CareerProfile
        from resources.models import Article
        from institutions.models import InstitutionType, Institution
        from django.urls import reverse
        _INST_ICONS = {
            'public university': 'fas fa-university', 'private university': 'fas fa-school',
            'kmtc': 'fas fa-heartbeat', 'tvet': 'fas fa-tools',
            'ttc': 'fas fa-chalkboard-teacher', 'specialized': 'fas fa-flask',
        }
        from django.db.models import Count as _Count
        _inst_counts = dict(
            Institution.objects
            .values('institution_type_id')
            .annotate(_c=_Count('id'))
            .values_list('institution_type_id', '_c')
        )
        inst_type_links = []
        for itype in InstitutionType.objects.all()[:6]:
            _icon_key = next((k for k in _INST_ICONS if k in itype.name.lower()), None)
            inst_type_links.append({'label': itype.name, 'count': _inst_counts.get(itype.pk, 0),
                'url': reverse('institutions:institution_type_detail', kwargs={'type_slug': itype.slug}),
                'icon': _INST_ICONS.get(_icon_key, 'fas fa-building')})
        now = tz.now()
        kuccps_open  = tz.datetime(2026, 7, 3,  12, 0, tzinfo=_dtz.utc)
        kuccps_close = tz.datetime(2026, 8, 21, 23, 59, tzinfo=_dtz.utc)
        days_to_open  = (kuccps_open  - now).days
        days_to_close = (kuccps_close - now).days
        if days_to_open > 0:
            timeline_phase, timeline_days, timeline_label, timeline_date = 'before_open', days_to_open, 'Days until portal opens', 'Est. 3 Jul 2026'
        elif days_to_close > 0:
            timeline_phase, timeline_days, timeline_label, timeline_date = 'open', days_to_close, 'Days left to apply', 'Closes Est. 21 Aug 2026'
        else:
            timeline_phase, timeline_days, timeline_label, timeline_date = 'closed', 0, 'Portal closed for 2026', 'Check kuccps.ac.ke for 2027 dates'
        from institutions.models import InstitutionPromotion as _IP
        from datetime import date as _date
        _today = _date.today()
        _live = _IP.objects.filter(start_date__lte=_today, end_date__gte=_today).select_related(
            'institution', 'institution__institution_type'
        ).prefetch_related('institution__offerings__course')
        from clusters.models import Cluster as _Cluster
        _all_clusters = list(_Cluster.objects.all().only('name', 'slug', 'number', 'color_code', 'icon')[:4])
        from courses.trends import get_trends_context as _get_trends
        _trends = _get_trends()
        from career.models import CareerConfig as _CCfg
        from mentorship.models import MentorshipConfig as _MCfg
        _cfg = _CCfg.get()
        return render(request, "accounts/dashboard.html", {
            "guest": True,
            "tawk_enabled": _cfg.tawk_enabled,
            "mentor_signup_enabled": _MCfg.get().mentor_signup_enabled,
            "eligible_count": 0, "saved_count": 0, "shortlist_count": 0,
            "saved_courses": [], "shortlist_items": [], "notifications": [],
            "cluster_results": [], "latest_result": None, "snapshot": None,
            "quiz_submission": None, "saved_course_ids": [],
            "all_clusters": _all_clusters,
            "recommended_careers": CareerProfile.objects.all()[:3],
            "recent_news": Article.objects.filter(is_published=True).order_by('-created_at')[:3],
            "featured_promos": list(_live.filter(tier='featured')[:3]),
            "scholarship_alerts": list(_live.filter(tier='scholarship')[:4]),
            "preview_courses": [
                {'name': 'Medicine and Surgery',   'cluster_num': 15, 'cutoff': '42.0', 'icon': 'fa-stethoscope',      'bg': '#fee2e2', 'color': '#dc2626'},
                {'name': 'Civil Engineering',      'cluster_num': 4,  'cutoff': '38.5', 'icon': 'fa-cogs',             'bg': '#dbeafe', 'color': '#1d4ed8'},
                {'name': 'Computer Science',       'cluster_num': 9,  'cutoff': '36.0', 'icon': 'fa-laptop-code',      'bg': '#ede9fe', 'color': '#6d28d9'},
                {'name': 'Bachelor of Laws (LLB)', 'cluster_num': 12, 'cutoff': '40.0', 'icon': 'fa-gavel',            'bg': '#fef3c7', 'color': '#b45309'},
                {'name': 'Nursing (B.Sc.)',        'cluster_num': 13, 'cutoff': '35.5', 'icon': 'fa-heartbeat',        'bg': '#dcfce7', 'color': '#15803d'},
                {'name': 'Architecture',           'cluster_num': 5,  'cutoff': '37.0', 'icon': 'fa-drafting-compass', 'bg': '#ccfbf1', 'color': '#0f766e'},
            ],
            "timeline_phase": timeline_phase, "timeline_days": timeline_days,
            "timeline_label": timeline_label, "timeline_date": timeline_date,
            "inst_type_links": inst_type_links,
            "trending_viewed": _trends.get('trending_viewed', []),
            "spotlight": _trends.get('spotlight'),
        })

    user = request.user
    if not user.is_active or user.is_suspended:
        messages.error(request, "Your account is inactive or suspended.")
        return redirect("accounts:login")

    from django.utils import timezone as tz
    from clusterpoints.models import UserKCSEResult, ClusterCalculationResult
    from .models import SavedCourse, CourseShortlist, Notification, CareerSessionSnapshot
    from career.models import CareerProfile, QuizSubmission

    # ── KCSE results & cluster chart ──────────────────────────────────────────
    latest_result = UserKCSEResult.objects.filter(user=user).order_by("-created_at").first()
    cluster_results = []
    eligible_count = 0
    if latest_result:
        cluster_results = list(
            ClusterCalculationResult.objects.filter(kcse_result=latest_result)
            .select_related("cluster").order_by("-cluster_points")
        )
        from courses.models import CourseOffering
        kcn_map = {}
        cluster_pks_for_user = []
        for r in cluster_results:
            knum = r.cluster.kuccps_number if r.cluster else None
            if knum:
                kcn_map[knum] = float(r.cluster_points)
                cluster_pks_for_user.append(r.cluster.pk)
        if kcn_map:
            eligible_set: set = set()
            for offering in CourseOffering.objects.filter(
                cutoff_points__isnull=False,
                course__cluster__pk__in=cluster_pks_for_user,
            ).select_related("course__cluster"):
                knum = offering.course.cluster.kuccps_number if offering.course.cluster else None
                if knum is None:
                    continue
                user_pts = kcn_map.get(knum, 0.0)
                cp = offering.cutoff_points
                cutoff = cp.get("2024") or cp.get(
                    max((k for k in cp if cp[k] is not None), default=None)
                )
                if cutoff is not None and user_pts >= float(cutoff):
                    eligible_set.add(offering.course_id)
            eligible_count = len(eligible_set)

    # ── Watchlist ─────────────────────────────────────────────────────────────
    # Single query for IDs + count; separate query for display rows (needs select_related)
    saved_course_ids = list(SavedCourse.objects.filter(user=user).values_list('course_id', flat=True))
    saved_count = len(saved_course_ids)
    saved_courses = (
        SavedCourse.objects.filter(user=user)
        .select_related('course', 'course__course_type', 'course__cluster')
        .order_by('-saved_at')[:6]
    )

    # ── Shortlist & notifications ─────────────────────────────────────────────
    shortlist_items = list(
        CourseShortlist.objects.filter(user=user)
        .select_related('course', 'course__course_type', 'course__cluster')
        .order_by('rank', '-added_at')
    )
    shortlist_count = len(shortlist_items)
    all_unread = list(Notification.objects.filter(user=user, is_read=False).order_by("-created_at"))
    unread_count  = len(all_unread)
    notifications = all_unread[:5]

    # ── Mentorship ────────────────────────────────────────────────────────────
    from mentorship.models import MentorProfile as _MentorProfile, MentorshipSession as _MSession
    user_mentor_profile = _MentorProfile.objects.filter(user=user).first()
    next_session = (
        _MSession.objects
        .filter(mentee=user, status="confirmed", slot__date__gte=timezone.now().date())
        .select_related("mentor", "mentor__user", "mentor__course", "slot")
        .order_by("slot__date", "slot__start_time")
        .first()
    )
    mentor_pending = (
        _MSession.objects
        .filter(mentor=user_mentor_profile, status="confirmed", slot__date__gte=timezone.now().date())
        .select_related("mentee", "slot")
        .order_by("slot__date")[:3]
    ) if user_mentor_profile else []

    # ── Latest news articles ─────────────────────────────────────────────────
    from resources.models import Article
    recent_news = Article.objects.filter(is_published=True).order_by('-created_at')[:3]

    # ── Career data ───────────────────────────────────────────────────────────
    recommended_careers = CareerProfile.objects.all()[:3]
    snapshot            = CareerSessionSnapshot.objects.filter(user=user).order_by('-computed_at').first()
    quiz_submission     = QuizSubmission.objects.filter(user=user).order_by('-created_at').first()

    # ── Affiliate ─────────────────────────────────────────────────────────────
    from .models import AffiliateProfile
    try:
        affiliate_profile = AffiliateProfile.objects.get(user=user, is_active=True)
    except AffiliateProfile.DoesNotExist:
        affiliate_profile = None

    # ── Preview courses for new users (no career session yet) ─────────────
    preview_courses = []
    if not snapshot:
        from courses.models import Course, CourseOffering
        from django.db.models import Q as _Q

        _ICON_MAP = [
            ('medicine',             'fa-stethoscope',        '#fee2e2', '#dc2626'),
            ('surgery',              'fa-stethoscope',        '#fee2e2', '#dc2626'),
            ('engineer',             'fa-cogs',               '#dbeafe', '#1d4ed8'),
            ('computer science',     'fa-laptop-code',        '#ede9fe', '#6d28d9'),
            ('information tech',     'fa-laptop-code',        '#ede9fe', '#6d28d9'),
            ('law',                  'fa-gavel',              '#fef3c7', '#b45309'),
            ('nurs',                 'fa-heartbeat',          '#dcfce7', '#15803d'),
            ('architect',            'fa-drafting-compass',   '#ccfbf1', '#0f766e'),
            ('pharmacy',             'fa-pills',              '#fce7f3', '#be185d'),
            ('education',            'fa-chalkboard-teacher', '#ffedd5', '#c2410c'),
            ('account',              'fa-chart-bar',          '#e0f2fe', '#0369a1'),
            ('finance',              'fa-coins',              '#e0f2fe', '#0369a1'),
            ('veterinary',           'fa-paw',                '#fdf4ff', '#7e22ce'),
            ('agriculture',          'fa-seedling',           '#f0fdf4', '#166534'),
        ]
        _DEFAULT = ('fa-graduation-cap', '#f1f5f9', '#475569')

        def _course_meta(name):
            nl = name.lower()
            for kw, icon, bg, color in _ICON_MAP:
                if kw in nl:
                    return icon, bg, color
            return _DEFAULT

        _q = _Q()
        for kw in ['Medicine', 'Engineer', 'Computer Science', 'Law',
                   'Nurs', 'Architect', 'Pharmacy', 'Education', 'Veterinary']:
            _q |= _Q(name__icontains=kw)

        _qs = list(
            Course.objects
            .filter(_q, course_type__name='Degree', cluster__isnull=False)
            .select_related('cluster')
            .prefetch_related('offerings')
            .distinct()[:20]
        )
        _seen = set()
        for _c in _qs:
            _knum = _c.cluster.kuccps_number if _c.cluster else None
            if _knum in _seen:
                continue
            _seen.add(_knum)
            _off = next((o for o in _c.offerings.all() if o.cutoff_points), None)
            _cutoff = None
            if _off and _off.cutoff_points:
                _cutoff = (_off.cutoff_points.get('2024') or
                           next((v for v in _off.cutoff_points.values() if v is not None), None))
            _icon, _bg, _color = _course_meta(_c.name)
            preview_courses.append({
                'name': _c.name, 'cluster_num': _knum,
                'cutoff': _cutoff, 'icon': _icon, 'bg': _bg, 'color': _color,
            })
            if len(preview_courses) >= 6:
                break

        if not preview_courses:
            preview_courses = [
                {'name': 'Medicine and Surgery',   'cluster_num': 15, 'cutoff': '42.0', 'icon': 'fa-stethoscope',        'bg': '#fee2e2', 'color': '#dc2626'},
                {'name': 'Civil Engineering',      'cluster_num': 4,  'cutoff': '38.5', 'icon': 'fa-cogs',               'bg': '#dbeafe', 'color': '#1d4ed8'},
                {'name': 'Computer Science',       'cluster_num': 9,  'cutoff': '36.0', 'icon': 'fa-laptop-code',        'bg': '#ede9fe', 'color': '#6d28d9'},
                {'name': 'Bachelor of Laws (LLB)', 'cluster_num': 12, 'cutoff': '40.0', 'icon': 'fa-gavel',              'bg': '#fef3c7', 'color': '#b45309'},
                {'name': 'Nursing (B.Sc.)',        'cluster_num': 13, 'cutoff': '35.5', 'icon': 'fa-heartbeat',          'bg': '#dcfce7', 'color': '#15803d'},
                {'name': 'Architecture',           'cluster_num': 5,  'cutoff': '37.0', 'icon': 'fa-drafting-compass',   'bg': '#ccfbf1', 'color': '#0f766e'},
            ]

    # ── KUCCPS 2026 Application Timeline ─────────────────────────────────────
    now           = tz.now()
    from datetime import timezone as _dtz
    kuccps_open   = tz.datetime(2026, 7, 3,  12, 0, tzinfo=_dtz.utc)
    kuccps_close  = tz.datetime(2026, 8, 21, 23, 59, tzinfo=_dtz.utc)
    days_to_open  = (kuccps_open  - now).days
    days_to_close = (kuccps_close - now).days

    if days_to_open > 0:
        timeline_phase = 'before_open'
        timeline_days  = days_to_open
        timeline_label = 'Days until portal opens'
        timeline_date  = 'Est. 3 Jul 2026'
    elif days_to_close > 0:
        timeline_phase = 'open'
        timeline_days  = days_to_close
        timeline_label = 'Days left to apply'
        timeline_date  = 'Closes Est. 21 Aug 2026'
    else:
        timeline_phase = 'closed'
        timeline_days  = 0
        timeline_label = 'Portal closed for 2026'
        timeline_date  = 'Check kuccps.ac.ke for 2027 dates'

    # ── Active promotions ─────────────────────────────────────────────────────
    from institutions.models import InstitutionType, Institution, InstitutionPromotion
    from datetime import date as _date
    _today = _date.today()
    _live_promos = (
        InstitutionPromotion.objects
        .filter(start_date__lte=_today, end_date__gte=_today)
        .select_related('institution', 'institution__institution_type')
        .prefetch_related('institution__offerings__course')
    )
    featured_promos    = list(_live_promos.filter(tier='featured')[:3])
    scholarship_alerts = list(_live_promos.filter(tier='scholarship')[:4])

    # ── Institutions quick links ──────────────────────────────────────────────
    from django.urls import reverse
    from django.db.models import Count as _Count
    _INST_ICONS = {
        'public university':   'fas fa-university',
        'private university':  'fas fa-school',
        'kmtc':                'fas fa-heartbeat',
        'tvet':                'fas fa-tools',
        'ttc':                 'fas fa-chalkboard-teacher',
        'specialized':         'fas fa-flask',
    }
    # Batch count in a single query instead of one COUNT per type
    _inst_counts = dict(
        Institution.objects
        .values('institution_type_id')
        .annotate(_c=_Count('id'))
        .values_list('institution_type_id', '_c')
    )
    inst_type_links = []
    for itype in InstitutionType.objects.all()[:6]:
        _icon_key = next((k for k in _INST_ICONS if k in itype.name.lower()), None)
        inst_type_links.append({
            'label': itype.name,
            'url':   reverse('institutions:institution_type_detail', kwargs={'type_slug': itype.slug}),
            'icon':  _INST_ICONS.get(_icon_key, 'fas fa-building'),
            'count': _inst_counts.get(itype.pk, 0),
        })

    from clusters.models import Cluster
    all_clusters = list(Cluster.objects.all().only('name', 'slug', 'number', 'color_code', 'icon')[:4])

    from courses.trends import get_trends_context
    trends_ctx = get_trends_context()

    # ── Application Readiness ─────────────────────────────────────────────────
    from django.urls import reverse as _rev
    _readiness_steps = [
        {'key': 'grades',    'label': 'Enter KCSE grades',     'icon': 'fas fa-calculator',     'done': bool(latest_result),  'url': _rev('clusterpoints:calculator'), 'desc': 'Calculate your cluster points'},
        {'key': 'profile',   'label': 'Complete your profile',  'icon': 'fas fa-user-check',    'done': bool(user.county),    'url': _rev('accounts:profile'),        'desc': 'Add county & KCSE year'},
        {'key': 'engine',    'label': 'Run Career Engine',      'icon': 'fas fa-rocket',        'done': bool(snapshot),       'url': _rev('career:home'),             'desc': 'See all matching courses'},
        {'key': 'shortlist', 'label': 'Shortlist top picks',    'icon': 'fas fa-list-check',    'done': shortlist_count > 0,  'url': _rev('accounts:shortlist'),      'desc': 'Rank your favourite courses'},
        {'key': 'quiz',      'label': 'Take Career Quiz',       'icon': 'fas fa-clipboard-list','done': bool(quiz_submission),'url': _rev('career:quiz'),             'desc': '3-min quiz for personalised advice'},
    ]
    _readiness_done = sum(1 for s in _readiness_steps if s['done'])
    _readiness_pct  = int(_readiness_done / len(_readiness_steps) * 100)

    # ── Shortlist offering map (built for all users with shortlist items) ────
    _shared_offering_map: dict = {}
    if shortlist_items:
        from courses.models import CourseOffering as _CO
        for _off in _CO.objects.filter(
            course_id__in=[i.course_id for i in shortlist_items],
        ).select_related('institution').order_by('id'):
            if _off.course_id not in _shared_offering_map:
                _shared_offering_map[_off.course_id] = _off

    # ── Cutoff comparisons + trends for shortlisted courses ──────────────────
    cutoff_comparisons: list = []
    if shortlist_items and cluster_results:
        _kcn_map = {
            r.cluster.kuccps_number: float(r.cluster_points)
            for r in cluster_results if r.cluster
        }
        from predictor.services import (
            predict_cutoff as _predict_cutoff,
            TREND_ICON as _TICON,
            TREND_COLOR as _TCOLOR,
            TREND_TIP as _TTIP,
        )
        for _item in shortlist_items[:6]:
            _c = _item.course
            if not _c.cluster:
                continue
            _user_pts = _kcn_map.get(_c.cluster.kuccps_number)
            if _user_pts is None:
                continue
            _off2 = _shared_offering_map.get(_c.id)
            _cutoff_history = (_off2.cutoff_points if _off2 else None) or _c.cutoff_points
            _cutoff = _off2.latest_cutoff() if _off2 else None
            if _cutoff is None and _c.cutoff_points:
                _yr = max(
                    (k for k in _c.cutoff_points if _c.cutoff_points[k] is not None),
                    default=None,
                )
                _cutoff = _c.cutoff_points.get(_yr) if _yr else None
            if _cutoff is None:
                continue
            _diff = round(float(_user_pts) - float(_cutoff), 1)
            _pred = _predict_cutoff(_cutoff_history)
            _trend = _pred.get('trend', 'stable') if _pred else 'stable'
            _predicted = round(_pred['predicted'], 1) if _pred else None
            _history_pairs = (
                sorted(
                    [(k, v) for k, v in _cutoff_history.items() if v is not None],
                    key=lambda x: x[0],
                )
                if _cutoff_history else []
            )
            cutoff_comparisons.append({
                'name':        _c.name,
                'inst':        _off2.institution.name if _off2 else '—',
                'cluster_num': _c.cluster.kuccps_number,
                'user_pts':    round(_user_pts, 1),
                'cutoff':      float(_cutoff),
                'diff':        _diff,
                'qualifies':   _diff >= 0,
                'url':         _c.get_absolute_url(),
                'trend':       _trend,
                'trend_icon':  _TICON.get(_trend, 'fa-minus'),
                'trend_color': _TCOLOR.get(_trend, 'text-muted'),
                'trend_tip':   _TTIP.get(_trend, ''),
                'predicted':   _predicted,
                'history':     _history_pairs,
            })

    # ── Subject requirements check ────────────────────────────────────────────
    subject_req_checks: list = []
    if shortlist_items and latest_result:
        _GRADE_PTS = {
            'A': 12, 'A-': 11, 'B+': 10, 'B': 9, 'B-': 8,
            'C+': 7, 'C': 6, 'C-': 5, 'D+': 4, 'D': 3, 'D-': 2, 'E': 1,
        }
        _SUBJ_MAP = {
            'ENG': 'English', 'KIS': 'Kiswahili', 'MAT': 'Mathematics',
            'BIO': 'Biology', 'CHE': 'Chemistry', 'PHY': 'Physics',
            'GEO': 'Geography', 'HIS': 'History', 'CRE': 'Christian Religious Education',
            'IRE': 'Islamic Religious Education', 'BST': 'Business Studies',
            'ECO': 'Economics', 'AGR': 'Agriculture', 'ART': 'Art and Design',
            'MUS': 'Music', 'HOM': 'Home Science', 'COM': 'Computer Studies',
            'FRE': 'French', 'GER': 'German', 'ARB': 'Arabic',
            'ACC': 'Accounting',
        }
        _student_pts: dict = {
            sr.subject.name.strip(): sr.points
            for sr in latest_result.subject_results.select_related('subject').all()
        }
        for _item in shortlist_items[:6]:
            _c = _item.course
            _reqs = _c.subject_requirements
            if not _reqs:
                continue
            _checks: list = []
            _all_pass = True
            for _req in _reqs:
                _subjects_str = _req.get('subjects_str', '')
                _min_grade = _req.get('min_grade', 'E')
                _min_pts_req = _GRADE_PTS.get(_min_grade, 1)
                _options = [s.strip() for s in _subjects_str.split('/')]
                _slot_met = False
                for _opt in _options:
                    _full_name = _SUBJ_MAP.get(_opt.upper(), _opt)
                    _pts_have = _student_pts.get(_full_name)
                    if _pts_have is not None and _pts_have >= _min_pts_req:
                        _slot_met = True
                        break
                if not _slot_met:
                    _all_pass = False
                _checks.append({
                    'label': _subjects_str,
                    'min_grade': _min_grade,
                    'met': _slot_met,
                })
            subject_req_checks.append({
                'course_name': _c.name,
                'url': _c.get_absolute_url(),
                'checks': _checks,
                'all_pass': _all_pass,
            })

    # ── Shortlist comparison table ────────────────────────────────────────────
    shortlist_comparison: list = []
    if shortlist_items:
        for _item in shortlist_items[:6]:
            _c = _item.course
            _off = _shared_offering_map.get(_c.id)
            _cv = _off.latest_cutoff() if _off else None
            if _cv is None and _c.cutoff_points:
                _yr = max(
                    (k for k in _c.cutoff_points if _c.cutoff_points[k] is not None),
                    default=None,
                )
                _cv = _c.cutoff_points.get(_yr) if _yr else None
            shortlist_comparison.append({
                'name':      _c.name,
                'inst':      _off.institution.name if _off else '—',
                'type':      _c.course_type.name if _c.course_type else '—',
                'cluster':   _c.cluster.kuccps_number if _c.cluster else '—',
                'cutoff':    float(_cv) if _cv is not None else None,
                'min_grade': _c.minimum_mean_grade or '—',
                'duration':  _c.duration or '—',
                'url':       _c.get_absolute_url(),
            })

    from career.models import CareerConfig as _CCfg
    from mentorship.models import MentorshipConfig as _MCfg
    _cfg = _CCfg.get()

    # ── AI chat credit info ───────────────────────────────────────────────────
    from career.models import AIChatCredit as _AIChatCredit
    _credit = _AIChatCredit.for_user(user)
    _free_limit = getattr(_cfg, 'ai_free_message_limit', 20)
    _free_remaining = max(0, _free_limit - _credit.free_messages_used)
    _paid_remaining = _credit.paid_messages_remaining
    ai_credit_info = {
        'free_remaining':  _free_remaining,
        'paid_remaining':  _paid_remaining,
        'total_remaining': _free_remaining + _paid_remaining,
        'has_access':      (_free_remaining + _paid_remaining) > 0 or user.is_staff,
        'free_limit':      _free_limit,
    }

    # ── Activity Feed ─────────────────────────────────────────────────────────
    _activity_events: list = []
    for _sc in SavedCourse.objects.filter(user=user).select_related('course').order_by('-saved_at')[:5]:
        _activity_events.append({
            'ts': _sc.saved_at,
            'icon': 'fas fa-bookmark',
            'icon_bg': '#fef3c7', 'icon_color': '#d97706',
            'label': f'Saved {_sc.course.name}',
            'sub': 'Watchlist',
            'url': _sc.course.get_absolute_url(),
        })
    for _sl in CourseShortlist.objects.filter(user=user).select_related('course').order_by('-added_at')[:5]:
        _activity_events.append({
            'ts': _sl.added_at,
            'icon': 'fas fa-list-check',
            'icon_bg': '#eff6ff', 'icon_color': '#2563eb',
            'label': f'Shortlisted {_sl.course.name}',
            'sub': 'Shortlist',
            'url': _sl.course.get_absolute_url(),
        })
    if latest_result:
        _activity_events.append({
            'ts': latest_result.created_at,
            'icon': 'fas fa-calculator',
            'icon_bg': '#f0fdf4', 'icon_color': '#16a34a',
            'label': 'Calculated cluster points',
            'sub': 'KCSE Result',
            'url': _rev('clusterpoints:calculator'),
        })
    if snapshot:
        _activity_events.append({
            'ts': snapshot.computed_at,
            'icon': 'fas fa-rocket',
            'icon_bg': '#eef2ff', 'icon_color': '#4f46e5',
            'label': f'Ran Career Engine — {snapshot.pathway}',
            'sub': 'Career Engine',
            'url': _rev('career:career_results'),
        })
    if quiz_submission:
        _activity_events.append({
            'ts': quiz_submission.created_at,
            'icon': 'fas fa-clipboard-list',
            'icon_bg': '#fdf4ff', 'icon_color': '#7c3aed',
            'label': 'Completed career quiz',
            'sub': 'Quiz',
            'url': _rev('career:quiz_results'),
        })
    activity_feed = sorted(_activity_events, key=lambda x: x['ts'], reverse=True)[:6]

    # ── Suggested Mentors (matched to shortlist) ──────────────────────────────
    _shortlist_course_ids = [_i.course_id for _i in shortlist_items]
    suggested_mentors = []
    if _shortlist_course_ids:
        suggested_mentors = list(
            _MentorProfile.objects
            .filter(is_approved=True, is_active=True, course_id__in=_shortlist_course_ids)
            .select_related('user', 'course', 'institution')
            .order_by('-average_rating', '-total_sessions')[:2]
        )

    return render(request, "accounts/dashboard.html", {
        # Platform config
        "tawk_enabled":           _cfg.tawk_enabled,
        "mentor_signup_enabled":  _MCfg.get().mentor_signup_enabled,
        # KCSE / clusters
        "latest_result":     latest_result,
        "cluster_results":   cluster_results,
        "eligible_count":    eligible_count,
        "all_clusters":      all_clusters,
        # Watchlist
        "saved_count":       saved_count,
        "saved_courses":     saved_courses,
        "saved_course_ids":  saved_course_ids,
        # Shortlist & notifications
        "shortlist_items":   shortlist_items,
        "shortlist_count":   shortlist_count,
        "notifications":     notifications,
        "unread_count":      unread_count,
        # Career
        "recommended_careers": recommended_careers,
        "snapshot":            snapshot,
        "quiz_submission":     quiz_submission,
        "preview_courses":     preview_courses,
        # News
        # Mentorship
        "user_mentor_profile": user_mentor_profile,
        "next_session":        next_session,
        "mentor_pending":      mentor_pending,
        # News
        "recent_news":         recent_news,
        # Timeline
        "timeline_phase":    timeline_phase,
        "timeline_days":     timeline_days,
        "timeline_label":    timeline_label,
        "timeline_date":     timeline_date,
        # Institutions
        "inst_type_links":   inst_type_links,
        # Promotions
        "featured_promos":    featured_promos,
        "scholarship_alerts": scholarship_alerts,
        # Affiliate
        "affiliate_profile":  affiliate_profile,
        # Trending
        "trending_viewed":    trends_ctx.get('trending_viewed', []),
        "spotlight":          trends_ctx.get('spotlight'),
        # Readiness
        "readiness_steps":      _readiness_steps,
        "readiness_pct":        _readiness_pct,
        "readiness_done":       _readiness_done,
        # Cutoff comparisons + trends
        "cutoff_comparisons":   cutoff_comparisons,
        # Subject requirements
        "subject_req_checks":   subject_req_checks,
        # Comparison table
        "shortlist_comparison": shortlist_comparison,
        # AI chat
        "ai_credit_info":       ai_credit_info,
        # Activity feed
        "activity_feed":        activity_feed,
        # Suggested mentors
        "suggested_mentors":    suggested_mentors,
    })


# =====================================================
# PROFILE UPDATE VIEW (Removed Profile model)
# =====================================================
@login_required
def profile_update_view(request: HttpRequest) -> HttpResponse:
    """
    Update user fields directly (no Profile model).
    """
    from .forms import UserProfileForm  # create a form that edits User fields

    form = UserProfileForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("accounts:profile")

    return render(request, "accounts/profile.html", {"form": form})


# =====================================================
# PASSWORD CHANGE VIEW
# =====================================================
@require_recent_auth
@require_http_methods(["GET", "POST"])
def change_password_view(request: HttpRequest) -> HttpResponse:
    error = None
    if request.method == "POST":
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")
        if not password1:
            error = "Please enter a new password."
        elif len(password1) < 4:
            error = "Password must be at least 4 characters."
        elif password1 != password2:
            error = "Passwords do not match."
        else:
            request.user.set_password(password1)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully.")
            return redirect("accounts:dashboard")
        if error:
            messages.error(request, error)

    return render(request, "accounts/change_password.html")


# =====================================================
# RE-AUTHENTICATION VIEW
# =====================================================
@login_required
@require_http_methods(["GET", "POST"])
def re_auth_view(request: HttpRequest) -> HttpResponse:
    """Ask the user to confirm their password before a sensitive action."""
    raw_next = request.POST.get("next") or request.GET.get("next") or ""
    next_url = (
        raw_next
        if url_has_allowed_host_and_scheme(raw_next, allowed_hosts={request.get_host()})
        else "/accounts/dashboard/"
    )

    if request.method == "POST":
        password = request.POST.get("password", "")
        user = authenticate(request, email=request.user.email, password=password)
        if user and user.pk == request.user.pk:
            request.session["_auth_verified_at"] = time.time()
            return redirect(next_url)
        messages.error(request, "Incorrect password. Please try again.")

    return render(request, "accounts/re_auth.html", {"next": next_url})



def terms_view(request):
    return render(request, "accounts/terms.html")


@login_required
def referral_view(request):
    from accounts.models import Referral, _make_referral_code
    # Get or create a referral entry for this user (their personal invite code)
    ref, _ = Referral.objects.get_or_create(
        referrer=request.user, referred_user__isnull=True, converted=False,
        defaults={'code': _make_referral_code()}
    )
    # If somehow all codes are used (converted), make a fresh one
    if ref.converted:
        ref = Referral.objects.create(referrer=request.user, code=_make_referral_code())

    conversions = Referral.objects.filter(referrer=request.user, converted=True).select_related('referred_user')
    pending     = Referral.objects.filter(referrer=request.user, converted=False).exclude(id=ref.id)
    ref_url = request.build_absolute_uri(f"/?ref={ref.code}")
    share_msg = (
        f"🎓 I use CareerNext to calculate my KCSE cluster points & discover every university, KMTC, TVET and TTC course I qualify for — it's 100% FREE!\n\n"
        f"It covers all Kenya placements in one place. Try it:\n{ref_url}\n\n"
        f"👉 Or visit: www.careernext.co.ke"
    )
    return render(request, 'accounts/referral.html', {
        'ref': ref,
        'ref_url': ref_url,
        'conversions': conversions,
        'pending': pending,
        'total_referred': conversions.count(),
        'whatsapp_text': share_msg,
        'twitter_text': "🎓 Check your KCSE cluster points & find every university, KMTC & TVET course you qualify for — 100% free! www.careernext.co.ke",
        'telegram_text': share_msg,
    })


@login_required
def affiliate_dashboard(request):
    from accounts.models import AffiliateProfile, AffiliateCommission, Referral, _make_referral_code
    from django.http import Http404

    try:
        affiliate = request.user.affiliate_profile
    except AffiliateProfile.DoesNotExist:
        raise Http404

    if not affiliate.is_active:
        raise Http404

    # Ensure a referral code exists for this affiliate
    ref, _ = Referral.objects.get_or_create(
        referrer=request.user, referred_user__isnull=True, converted=False,
        defaults={'code': _make_referral_code()}
    )
    if ref.converted:
        ref = Referral.objects.create(referrer=request.user, code=_make_referral_code())

    ref_url   = request.build_absolute_uri(f"/?ref={ref.code}")
    share_msg = (
        f"🎓 Join CareerNext — Kenya's #1 KCSE career guidance platform!\n\n"
        f"✅ Calculate your cluster points instantly\n"
        f"✅ See every university, KMTC, TVET & TTC course you qualify for\n"
        f"✅ 100% FREE\n\n"
        f"Sign up via my link: {ref_url}\n\n"
        f"👉 Or visit: www.careernext.co.ke"
    )

    # All sign-up conversions via this affiliate's link
    referrals = (
        Referral.objects
        .filter(referrer=request.user, converted=True)
        .select_related('referred_user')
        .order_by('-converted_at')
    )

    # All commissions earned
    commissions = (
        AffiliateCommission.objects
        .filter(affiliate=affiliate)
        .select_related('referred_user', 'payment')
        .order_by('-created_at')
    )

    # Build a quick lookup: referred_user_id → commission
    commission_by_user = {c.referred_user_id: c for c in commissions if c.referred_user_id}

    def _mask(user):
        if not user:
            return '—', '—'
        email = user.email
        parts = email.split('@')
        masked_email = (parts[0][:2] + '***@' + parts[1]) if len(parts) == 2 else '***'
        name = (user.full_name or '').strip()
        if name:
            words = name.split()
            masked_name = words[0][0] + '*** ' + (words[-1][0] + '***' if len(words) > 1 else '')
        else:
            masked_name = masked_email
        return masked_email, masked_name.strip()

    referral_rows = []
    for r in referrals:
        email, name = _mask(r.referred_user)
        uid = r.referred_user_id
        commission = commission_by_user.get(uid)
        referral_rows.append({
            'email':      email,
            'name':       name,
            'joined':     r.converted_at,
            'has_paid':   uid in commission_by_user,
            'commission': commission.amount if commission else None,
            'feature':    commission.payment.get_feature_display() if commission else None,
        })

    pending_amount  = sum(c.amount for c in commissions if c.status == 'pending')
    paid_out_amount = sum(c.amount for c in commissions if c.status == 'paid_out')

    from django.conf import settings as _settings
    payout_phone = getattr(_settings, 'AFFILIATE_PAYOUT_PHONE', '254700000000')

    return render(request, 'accounts/affiliate_dashboard.html', {
        'affiliate':        affiliate,
        'ref_url':          ref_url,
        'ref_code':         ref.code,
        'share_msg':        share_msg,
        'total_referred':   referrals.count(),
        'paid_conversions': len(commission_by_user),
        'referral_rows':    referral_rows,
        'commissions':      commissions,
        'pending_amount':   pending_amount,
        'paid_out_amount':  paid_out_amount,
        'can_request_payout': affiliate.wallet_balance >= 500,
        'payout_phone':     payout_phone,
        'withdrawal_form':  _build_affiliate_withdrawal_form(affiliate),
        'withdrawals':      affiliate.withdrawals.all()[:5],
    })


def _build_affiliate_withdrawal_form(affiliate, data=None):
    from accounts.forms import AffiliateWithdrawalForm
    return AffiliateWithdrawalForm(int(affiliate.wallet_balance), data)


@login_required
@require_recent_auth
def request_affiliate_payout(request):
    import logging
    from django.conf import settings as django_settings
    from accounts.models import AffiliateProfile, AffiliateWithdrawalRequest, AffiliateCommission
    from accounts.forms import AffiliateWithdrawalForm
    from django.http import Http404

    if request.method != 'POST':
        return redirect('accounts:affiliate_dashboard')

    try:
        affiliate = request.user.affiliate_profile
    except AffiliateProfile.DoesNotExist:
        raise Http404
    if not affiliate.is_active:
        raise Http404

    form = AffiliateWithdrawalForm(int(affiliate.wallet_balance), request.POST)
    if not form.is_valid():
        for err in form.errors.values():
            messages.error(request, err.as_text())
        return redirect('accounts:affiliate_dashboard')

    amount = form.cleaned_data['amount']
    mpesa  = form.cleaned_data['mpesa_number']

    if affiliate.wallet_balance < 500:
        messages.error(request, "Minimum payout is KES 500.")
        return redirect('accounts:affiliate_dashboard')

    if affiliate.withdrawals.filter(status='pending').exists():
        messages.error(request, "You already have a pending withdrawal. Please wait for it to complete.")
        return redirect('accounts:affiliate_dashboard')

    wr = AffiliateWithdrawalRequest.objects.create(
        affiliate=affiliate, amount=amount, mpesa_number=mpesa, status='pending'
    )
    try:
        from payments.services import send_affiliate_payout
        send_affiliate_payout(
            phone=mpesa,
            amount=amount,
            affiliate_name=request.user.full_name or request.user.email,
            ref=str(affiliate.pk)[:8],
        )
        wr.status = 'processed'
        wr.processed_at = timezone.now()
        wr.save(update_fields=['status', 'processed_at'])

        affiliate.wallet_balance -= amount
        affiliate.save(update_fields=['wallet_balance'])

        AffiliateCommission.objects.filter(affiliate=affiliate, status='pending').update(
            status='paid_out', paid_out_at=timezone.now()
        )

        send_branded_email(
            to=request.user.email,
            subject="CareerNext — Your Affiliate Payout Has Been Sent",
            heading="Payout Sent!",
            banner_label="✓ M-Pesa Sent",
            banner_color="green",
            greeting=f"Hi {request.user.full_name or 'there'},",
            body_lines=["Your affiliate earnings have been sent to your M-Pesa number. Thank you for referring students to CareerNext!"],
            table_rows=[
                {"label": "Amount", "value": f"KES {amount}", "highlight": True},
                {"label": "M-Pesa Number", "value": mpesa},
            ],
            cta_url="https://careernext.co.ke/accounts/affiliate-dashboard/",
            cta_label="View Affiliate Dashboard →",
            user_email=request.user.email,
        )
        messages.success(request, f"KES {amount} has been sent to {mpesa} via M-Pesa!")

    except Exception as exc:
        wr.status = 'failed'
        wr.admin_note = str(exc)[:500]
        wr.save(update_fields=['status', 'admin_note'])
        logging.getLogger(__name__).error("Affiliate payout failed for %s: %s", affiliate.pk, exc)
        messages.error(request, "Payout failed — please try again or contact support.")

    return redirect('accounts:affiliate_dashboard')


def email_lead_capture(request):
    """AJAX endpoint — capture visitor email before registration."""
    if request.method != 'POST':
        from django.http import JsonResponse
        return JsonResponse({'ok': False}, status=405)

    import json
    from django.http import JsonResponse
    from accounts.models import EmailLead

    try:
        body  = json.loads(request.body)
        email = body.get('email', '').strip().lower()
        source = body.get('source', 'other')[:20]
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'ok': False, 'error': 'invalid'}, status=400)

    if not email or '@' not in email or len(email) > 254:
        return JsonResponse({'ok': False, 'error': 'invalid_email'}, status=400)

    if request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'already_registered'}, status=400)

    # Don't duplicate within the same session
    session_key = f'lead_captured_{source}'
    if request.session.get(session_key):
        return JsonResponse({'ok': True, 'dup': True})

    ip = get_client_ip(request)
    ref_code = request.session.get('referral_code', '')
    EmailLead.objects.get_or_create(
        email=email,
        source=source,
        defaults={'ip_address': ip, 'ref_code': ref_code}
    )
    request.session[session_key] = True
    return JsonResponse({'ok': True})


def public_home_view(request):
    if request.user.is_authenticated:
        visits = request.session.get('home_visit_count', 0) + 1
        request.session['home_visit_count'] = visits
        if visits > 4:
            return redirect('accounts:dashboard')

    from resources.models import SuccessStory
    from institutions.models import InstitutionPromotion
    from courses.trends import get_trends_context
    from datetime import date as _date

    stories = SuccessStory.objects.filter(is_active=True).order_by('order', 'id')

    _today = _date.today()
    _live = InstitutionPromotion.objects.filter(
        start_date__lte=_today, end_date__gte=_today
    ).select_related('institution', 'institution__institution_type').prefetch_related(
        'institution__offerings__course'
    )
    featured_promos    = list(_live.filter(tier='featured')[:4])
    scholarship_alerts = list(_live.filter(tier='scholarship')[:4])

    # Sample cluster preview bars for the hero card (static illustrative data)
    sample_clusters = [
        ("Cluster 1", 75, "#4f46e5"),
        ("Cluster 4", 60, "#0891b2"),
        ("Cluster 9", 88, "#16a34a"),
        ("Cluster 12", 52, "#d97706"),
    ]

    from resources.models import Article as _HomeArticle
    recent_articles = list(_HomeArticle.objects.filter(is_published=True).order_by('-featured', '-created_at')[:3])

    ctx = {
        "stories": stories,
        "sample_clusters": sample_clusters,
        "featured_promos":    featured_promos,
        "scholarship_alerts": scholarship_alerts,
        "recent_articles":    recent_articles,
    }
    ctx.update(get_trends_context())
    return render(request, "accounts/home.html", ctx)


def privacy_view(request):
    return render(request, "accounts/privacy.html")


def about_view(request):
    from resources.models import SiteSetting
    settings_qs = SiteSetting.objects.all()
    site = {s.key: s.value for s in settings_qs}
    return render(request, "accounts/about.html", {"site": site})


def faq_view(request):
    from resources.models import FAQItem
    from collections import defaultdict
    items = FAQItem.objects.filter(is_active=True).order_by('category', 'order', 'id')
    by_cat = defaultdict(list)
    for item in items:
        by_cat[item.category].append(item)
    CATEGORIES = [
        ('general', 'General'),
        ('cluster', 'Cluster Points'),
        ('courses', 'Courses & Pathways'),
        ('kuccps',  'KUCCPS Process'),
        ('account', 'My Account'),
    ]
    # Build list of (key, label, [items]) — easy to iterate in templates
    faq_groups = [(k, label, by_cat.get(k, [])) for k, label in CATEGORIES]
    return render(request, "accounts/faq.html", {
        "faq_groups": faq_groups,
        "has_content": items.exists(),
    })


def how_it_works_view(request):
    return render(request, "accounts/how_it_works.html")


# =====================================================
# APPLICATION TRACKER
# =====================================================
@login_required
def applications_view(request):
    from .models import Application
    apps = Application.objects.filter(user=request.user)
    return render(request, "accounts/applications.html", {"applications": apps})


@login_required
def application_add_view(request):
    from .models import Application
    from .forms import ApplicationForm
    form = ApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        app = form.save(commit=False)
        app.user = request.user
        app.save()
        return redirect("accounts:applications")
    return render(request, "accounts/application_form.html", {"form": form})


@login_required
def application_update_view(request, pk):
    from .models import Application
    from .forms import ApplicationForm
    app = get_object_or_404(Application, pk=pk, user=request.user)
    form = ApplicationForm(request.POST or None, instance=app)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("accounts:applications")
    return render(request, "accounts/application_form.html", {"form": form})


@login_required
def application_delete_view(request, pk):
    from .models import Application
    app = get_object_or_404(Application, pk=pk, user=request.user)
    if request.method == "POST":
        app.delete()
    return redirect("accounts:applications")


# =====================================================
# SAVED COURSES
# =====================================================
@login_required
def saved_courses_view(request: HttpRequest) -> HttpResponse:
    from .models import SavedCourse, CareerSessionSnapshot
    saved = (
        SavedCourse.objects
        .filter(user=request.user)
        .select_related("course", "course__course_type", "course__category", "course__cluster")
        .prefetch_related("course__institutions")
        .order_by("-saved_at")
    )
    snapshot = CareerSessionSnapshot.objects.filter(user=request.user).order_by("-computed_at").first()
    return render(request, "accounts/saved_courses.html", {"saved": saved, "snapshot": snapshot})


@login_required
@require_http_methods(["POST"])
def toggle_save_course(request: HttpRequest, course_id: int) -> HttpResponse:
    from django.http import JsonResponse
    from .models import SavedCourse
    from courses.models import Course
    course = get_object_or_404(Course, pk=course_id)
    obj, created = SavedCourse.objects.get_or_create(user=request.user, course=course)
    if not created:
        obj.delete()
        return JsonResponse({"saved": False, "message": "Removed from saved"})
    return JsonResponse({"saved": True, "message": "Course saved!"})


@login_required
@require_http_methods(["POST"])
def toggle_save_career(request: HttpRequest, profile_id: int) -> HttpResponse:
    from django.http import JsonResponse
    from .models import SavedCareer
    from career.models import CareerProfile
    profile = get_object_or_404(CareerProfile, pk=profile_id)
    obj, created = SavedCareer.objects.get_or_create(user=request.user, career_profile=profile)
    if not created:
        obj.delete()
        return JsonResponse({"saved": False})
    return JsonResponse({"saved": True})


# =====================================================
# COURSE SHORTLIST
# =====================================================
@login_required
def shortlist_view(request: HttpRequest) -> HttpResponse:
    from .models import CourseShortlist
    from clusterpoints.models import ClusterCalculationResult, UserKCSEResult

    items = list(
        CourseShortlist.objects.filter(user=request.user)
        .select_related('course', 'course__course_type', 'course__cluster', 'course__category')
        .prefetch_related('course__offerings__institution', 'course__core_subjects')
        .order_by('rank', '-added_at')
    )

    # Build cluster_map for eligibility badges
    kcse_result = UserKCSEResult.objects.filter(user=request.user).order_by('-created_at').first()
    cluster_map = {}
    if kcse_result:
        for r in ClusterCalculationResult.objects.filter(
            kcse_result=kcse_result
        ).select_related('cluster'):
            knum = r.cluster.kuccps_number if r.cluster else None
            if knum is not None:
                cluster_map[knum] = float(r.cluster_points)

    # Annotate each item with eligibility and competition level
    from clusterpoints.eligibility import NEARLY_ELIGIBLE_GAP, CURRENT_YEAR
    RANK_CHOICES = [1, 2, 3, 4]
    for item in items:
        course = item.course
        # Eligibility
        knum = course.cluster.kuccps_number if course.cluster else None
        user_pts = cluster_map.get(knum) if knum else None
        offerings = list(course.offerings.all())
        min_cutoff = None
        for off in offerings:
            cp = off.cutoff_points or {}
            v = cp.get(CURRENT_YEAR) or cp.get(max((k for k in cp if cp[k]), default=None))
            if v is not None:
                v = float(v)
                if min_cutoff is None or v < min_cutoff:
                    min_cutoff = v
        if user_pts is not None and min_cutoff is not None:
            gap = user_pts - min_cutoff
            if gap >= 0:
                item.eligibility = 'eligible'
            elif abs(gap) <= NEARLY_ELIGIBLE_GAP:
                item.eligibility = 'nearly'
            else:
                item.eligibility = 'not_eligible'
            item.eligibility_gap = round(gap, 1)
        else:
            item.eligibility = None
            item.eligibility_gap = None
        # Competition level from cutoff
        if min_cutoff is not None:
            if min_cutoff >= 40:
                item.competition = 'high'
            elif min_cutoff >= 28:
                item.competition = 'medium'
            else:
                item.competition = 'low'
        else:
            item.competition = None
        item.min_cutoff = min_cutoff

    used_ranks = {item.rank for item in items if item.rank}

    cutoffs = [item.min_cutoff for item in items if item.min_cutoff is not None]
    cutoff_min = min(cutoffs) if cutoffs else None
    cutoff_max = max(cutoffs) if cutoffs else None

    return render(request, 'accounts/shortlist.html', {
        'items': items,
        'has_cluster_data': bool(cluster_map),
        'rank_choices': RANK_CHOICES,
        'used_ranks': list(used_ranks),
        'cutoff_min': cutoff_min,
        'cutoff_max': cutoff_max,
    })


@login_required
@require_http_methods(["POST"])
def shortlist_toggle(request: HttpRequest, course_id: int) -> HttpResponse:
    from django.http import JsonResponse
    from .models import CourseShortlist
    from courses.models import Course
    MAX = 5
    course = get_object_or_404(Course, pk=course_id)
    obj, created = CourseShortlist.objects.get_or_create(user=request.user, course=course)
    if not created:
        obj.delete()
        return JsonResponse({'shortlisted': False, 'message': 'Removed from shortlist'})
    if CourseShortlist.objects.filter(user=request.user).count() > MAX:
        obj.delete()
        return JsonResponse({'shortlisted': False, 'message': f'Shortlist is full (max {MAX} courses)', 'full': True})
    return JsonResponse({'shortlisted': True, 'message': 'Added to shortlist!'})


@login_required
@require_http_methods(["POST"])
def shortlist_update_notes(request: HttpRequest, course_id: int) -> HttpResponse:
    from django.http import JsonResponse
    from .models import CourseShortlist
    obj = get_object_or_404(CourseShortlist, user=request.user, course_id=course_id)
    obj.notes = request.POST.get('notes', '')[:1000]
    obj.save(update_fields=['notes'])
    return JsonResponse({'ok': True})


@login_required
@require_http_methods(["POST"])
def shortlist_set_rank(request: HttpRequest, course_id: int) -> HttpResponse:
    from django.http import JsonResponse
    from .models import CourseShortlist
    obj = get_object_or_404(CourseShortlist, user=request.user, course_id=course_id)
    raw = request.POST.get('rank', '')
    if raw == '' or raw == '0':
        obj.rank = None
    else:
        try:
            rank = int(raw)
            if 1 <= rank <= 4:
                # Clear any other item with the same rank
                CourseShortlist.objects.filter(user=request.user, rank=rank).exclude(pk=obj.pk).update(rank=None)
                obj.rank = rank
            else:
                return JsonResponse({'ok': False, 'error': 'Rank must be 1–4'})
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'Invalid rank'})
    obj.save(update_fields=['rank'])
    return JsonResponse({'ok': True, 'rank': obj.rank})


@login_required
def export_shortlist_pdf(request: HttpRequest) -> HttpResponse:
    from .models import CourseShortlist
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    from django.utils import timezone

    items = list(
        CourseShortlist.objects.filter(user=request.user)
        .select_related('course', 'course__course_type', 'course__cluster')
        .prefetch_related('course__offerings__institution')
        .order_by('rank', '-added_at')
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="my_shortlist.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    w, h = A4

    NAVY    = colors.HexColor('#1e3a8a')
    TEAL    = colors.HexColor('#0e7490')
    PURPLE  = colors.HexColor('#7c3aed')
    SLATE   = colors.HexColor('#475569')
    LIGHT   = colors.HexColor('#f0f9ff')
    WHITE   = colors.white

    name = request.user.full_name or request.user.email
    page_num = [0]

    def new_page():
        page_num[0] += 1
        if page_num[0] > 1:
            p.showPage()
        # Header
        p.setFillColor(NAVY)
        p.rect(0, h - 2.6*cm, w, 2.6*cm, fill=1, stroke=0)
        p.setFillColor(TEAL)
        p.rect(0, h - 2.7*cm, w, 0.12*cm, fill=1, stroke=0)
        p.setFillColor(WHITE)
        p.setFont('Helvetica-Bold', 16)
        p.drawString(1.5*cm, h - 1.3*cm, 'CareerNext — My Course Shortlist')
        p.setFont('Helvetica-Oblique', 7.5)
        p.setFillColor(colors.HexColor('#93c5fd'))
        p.drawString(1.5*cm, h - 1.78*cm, 'Your Journey Begins Here')
        p.setFont('Helvetica', 8.5)
        p.setFillColor(colors.HexColor('#bfdbfe'))
        p.drawString(1.5*cm, h - 2.22*cm,
            f'Student: {name}   |   Generated: {timezone.now().strftime("%d %b %Y")}')
        p.setFont('Helvetica', 8)
        p.drawRightString(w - 1.5*cm, h - 1.35*cm,
            f'careernext.co.ke   |   Page {page_num[0]}')
        # Footer
        p.setFillColor(TEAL)
        p.rect(0, 1.35*cm, w, 0.08*cm, fill=1, stroke=0)
        p.setFillColor(NAVY)
        p.rect(0, 0, w, 1.35*cm, fill=1, stroke=0)
        p.setFillColor(WHITE)
        p.setFont('Helvetica-Bold', 7.5)
        p.drawCentredString(w / 2, 0.82*cm,
            'careernext.co.ke  —  Your Journey Begins Here')
        p.setFont('Helvetica', 6.5)
        p.setFillColor(colors.HexColor('#93c5fd'))
        p.drawCentredString(w / 2, 0.45*cm,
            'Apply officially at kuccps.net  |  For guidance only — verify all details before applying')
        return h - 3.2*cm

    y = new_page()
    p.setFillColor(colors.HexColor('#1e293b'))

    if not items:
        p.setFont('Helvetica', 11)
        p.setFillColor(SLATE)
        p.drawString(1.5*cm, y, 'Your shortlist is empty.')
        p.save()
        return response

    for i, item in enumerate(items, 1):
        course = item.course
        if y < 6*cm:
            y = new_page()

        rank_label = f'Choice #{item.rank}' if item.rank else f'#{i}'

        # Course title row with choice badge
        p.setFillColor(PURPLE)
        p.roundRect(1.5*cm, y - 0.32*cm, 1.1*cm, 0.32*cm, 3, fill=1, stroke=0)
        p.setFillColor(WHITE)
        p.setFont('Helvetica-Bold', 7.5)
        p.drawCentredString(2.05*cm, y - 0.2*cm, rank_label)

        p.setFont('Helvetica-Bold', 10.5)
        p.setFillColor(NAVY)
        course_name = course.name[:55] if len(course.name) > 55 else course.name
        p.drawString(2.8*cm, y - 0.2*cm, course_name)
        y -= 0.5*cm

        p.setFont('Helvetica', 8.5)
        p.setFillColor(SLATE)
        type_label     = course.course_type.name if course.course_type else '—'
        cluster_label  = course.cluster.name if course.cluster else '—'
        grade_label    = course.minimum_mean_grade or '—'
        duration_label = course.duration or '—'
        p.drawString(1.5*cm, y,
            f'Type: {type_label}   |   Cluster: {cluster_label}   |   Min Grade: {grade_label}   |   Duration: {duration_label}')
        y -= 0.42*cm

        offs = list(course.offerings.all()[:4])
        if offs:
            inst_names = ', '.join(o.institution.name for o in offs)
            if course.offerings.count() > 4:
                inst_names += f' +{course.offerings.count()-4} more'
            p.drawString(1.5*cm, y, f'Institutions: {inst_names}')
            y -= 0.42*cm

        if item.notes:
            p.setFont('Helvetica-Oblique', 8)
            p.setFillColor(colors.HexColor('#64748b'))
            p.drawString(1.5*cm, y, f'Notes: {item.notes[:120]}')
            y -= 0.42*cm

        # Divider
        p.setStrokeColor(colors.HexColor('#e2e8f0'))
        p.line(1.5*cm, y, w - 1.5*cm, y)
        y -= 0.55*cm

    p.save()
    return response


# =====================================================
# NOTIFICATIONS
# =====================================================
@login_required
def notifications_view(request: HttpRequest) -> HttpResponse:
    from .models import Notification
    notifs = Notification.objects.filter(user=request.user).select_related("published_by")
    return render(request, "accounts/notifications.html", {"notifications": notifs})


@login_required
@require_http_methods(["POST"])
def mark_notifications_read(request: HttpRequest) -> HttpResponse:
    from django.http import JsonResponse
    from django.core.cache import cache
    from .models import Notification
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    cache.delete(f'notif_unread:{request.user.pk}')
    return JsonResponse({"status": "ok"})


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request: HttpRequest, notif_id: int) -> HttpResponse:
    from django.http import JsonResponse
    from django.core.cache import cache
    from .models import Notification
    Notification.objects.filter(user=request.user, id=notif_id).update(is_read=True)
    cache.delete(f'notif_unread:{request.user.pk}')
    return JsonResponse({"status": "ok"})


# =====================================================
# BROADCAST NOTIFICATION (staff only)
# =====================================================
def broadcast_notification_view(request: HttpRequest) -> HttpResponse:
    from django.contrib.admin.views.decorators import staff_member_required as _smr
    if not (request.user.is_authenticated and request.user.is_staff):
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())

    from .models import Notification

    sent_count = None
    push_count = 0
    if request.method == "POST":
        msg   = request.POST.get("message", "").strip()
        ntype = request.POST.get("notif_type", "info")
        link  = request.POST.get("link", "").strip()
        if msg:
            users = User.objects.filter(is_active=True)
            Notification.objects.bulk_create([
                Notification(user=u, message=msg, notif_type=ntype, link=link, published_by=request.user)
                for u in users
            ])
            sent_count = users.count()
            push_count = _send_push_to_all(msg, link or "/accounts/notifications/")
            messages.success(request, f"Notification sent to {sent_count} users ({push_count} push delivered).")

    active_count = User.objects.filter(is_active=True).count()
    from .models import PushSubscription
    push_sub_count = PushSubscription.objects.count()
    return render(request, "accounts/broadcast_notification.html", {
        "type_choices":   Notification.TYPE_CHOICES,
        "active_count":   active_count,
        "push_sub_count": push_sub_count,
        "sent_count":     sent_count,
        "push_count":     push_count,
    })


def _send_push_to_all(message: str, url: str = "/") -> int:
    """Send a Web Push to every stored subscription. Returns count of successful sends."""
    import json
    from django.conf import settings as _s
    from .models import PushSubscription

    if not _s.VAPID_PRIVATE_KEY or not _s.VAPID_PUBLIC_KEY:
        return 0

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return 0

    payload = json.dumps({
        "title": "CareerNext",
        "body":  message,
        "icon":  "/static/images/icon-192.png",
        "badge": "/static/images/icon-192.png",
        "url":   url,
    })

    ok = 0
    dead = []
    for sub in PushSubscription.objects.all():
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=_s.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{_s.VAPID_MAILTO}"},
            )
            ok += 1
        except Exception:
            dead.append(sub.pk)
    if dead:
        PushSubscription.objects.filter(pk__in=dead).delete()
    return ok


def _send_push_to_user(user, title: str, body: str, url: str = "/") -> int:
    """Send a Web Push to all subscriptions belonging to a specific user. Returns sends count."""
    import json
    from django.conf import settings as _s
    from .models import PushSubscription

    if not _s.VAPID_PRIVATE_KEY or not _s.VAPID_PUBLIC_KEY:
        return 0

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return 0

    subs = list(PushSubscription.objects.filter(user=user))
    if not subs:
        return 0

    payload = json.dumps({
        "title": title,
        "body":  body,
        "icon":  "/static/images/icon-192.png",
        "badge": "/static/images/icon-192.png",
        "url":   url,
    })

    ok = 0
    dead = []
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=_s.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{_s.VAPID_MAILTO}"},
            )
            ok += 1
        except Exception:
            dead.append(sub.pk)
    if dead:
        PushSubscription.objects.filter(pk__in=dead).delete()
    return ok


@require_http_methods(["POST"])
def push_subscribe(request: HttpRequest) -> JsonResponse:
    """Save a Web Push subscription from the browser."""
    import json
    from .models import PushSubscription

    try:
        data = json.loads(request.body)
        endpoint = data["endpoint"]
        p256dh   = data["keys"]["p256dh"]
        auth     = data["keys"]["auth"]
    except (KeyError, ValueError):
        return JsonResponse({"ok": False}, status=400)

    user = request.user if request.user.is_authenticated else None
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"p256dh": p256dh, "auth": auth, "user": user},
    )
    return JsonResponse({"ok": True})


# =====================================================
# FULL COURSE COMPARISON
# =====================================================
@login_required
def course_comparison_view(request: HttpRequest) -> HttpResponse:
    from .models import CourseShortlist
    from courses.models import CourseOffering

    items = list(
        CourseShortlist.objects.filter(user=request.user)
        .select_related('course', 'course__course_type', 'course__cluster')
        .order_by('rank', '-added_at')
    )

    offering_map: dict = {}
    for off in CourseOffering.objects.filter(
        course_id__in=[i.course_id for i in items],
    ).select_related('institution').order_by('id'):
        if off.course_id not in offering_map:
            offering_map[off.course_id] = off

    comparison = []
    for item in items:
        c = item.course
        off = offering_map.get(c.id)
        cv = off.latest_cutoff() if off else None
        if cv is None and c.cutoff_points:
            yr = max(
                (k for k in c.cutoff_points if c.cutoff_points[k] is not None),
                default=None,
            )
            cv = c.cutoff_points.get(yr) if yr else None
        comparison.append({
            'name':      c.name,
            'inst':      off.institution.name if off else '—',
            'type':      c.course_type.name if c.course_type else '—',
            'cluster':   c.cluster.kuccps_number if c.cluster else '—',
            'cutoff':    float(cv) if cv is not None else None,
            'min_grade': c.minimum_mean_grade or '—',
            'duration':  c.duration or '—',
            'url':       c.get_absolute_url(),
            'notes':     item.notes,
            'rank':      item.rank,
        })

    return render(request, 'accounts/comparison.html', {
        'comparison': comparison,
        'shortlist_count': len(items),
    })