import secrets
from typing import Any, Dict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_http_methods
from django.http import HttpRequest, HttpResponse, JsonResponse

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
        return x_forwarded.split(',')[0].strip()
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
            user.is_verified = False  # stays False until they click the email link
            user.save()

            # Generate and send email verification link
            token = secrets.token_urlsafe(32)
            EmailVerificationToken.objects.create(user=user, token=token)
            verify_url = request.build_absolute_uri(f"/accounts/verify-email/{token}/")
            send_mail(
                subject="Verify your CareerNext account",
                message=(
                    f"Hi {user.full_name or user.email},\n\n"
                    f"Click the link below to verify your email address:\n\n"
                    f"{verify_url}\n\n"
                    f"This link expires in 24 hours.\n\n"
                    f"If you did not create a CareerNext account, ignore this email.\n\n"
                    f"— The CareerNext Team"
                ),
                from_email=None,  # uses DEFAULT_FROM_EMAIL from settings
                recipient_list=[user.email],
                fail_silently=False,
            )
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
                except ReferralModel.DoesNotExist:
                    pass

            # ── Email lead conversion ─────────────────────────────
            from accounts.models import EmailLead
            EmailLead.objects.filter(email=user.email, converted_to_user__isnull=True).update(
                converted_to_user=user
            )

            messages.success(
                request,
                "Account created! Check your email and click the verification link to log in."
            )
            return redirect("accounts:login")

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
            if not user.is_verified:
                messages.error(
                    request,
                    "Please verify your email first — check your inbox (and spam) for a link from CareerNext."
                )
                return redirect("accounts:login")

            cache.delete(rl_key)  # Clear fail counter on successful login
            login(request, user)

            # Remember me token
            remember_me = form.cleaned_data.get("remember_me")
            if remember_me:
                token = secrets.token_urlsafe(32)
                expires_at = timezone.now() + timezone.timedelta(hours=72)
                RememberToken.objects.create(
                    user=user,
                    token=token,
                    expires_at=expires_at,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
                request.session.set_expiry(604800)  # 7 days
            else:
                request.session.set_expiry(0)  # Browser close

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
        inst_type_links = []
        for itype in InstitutionType.objects.all()[:6]:
            _count = Institution.objects.filter(institution_type=itype).count()
            _icon_key = next((k for k in _INST_ICONS if k in itype.name.lower()), None)
            inst_type_links.append({'label': itype.name, 'count': _count,
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
        return render(request, "accounts/dashboard.html", {
            "guest": True,
            "eligible_count": 0, "saved_count": 0, "shortlist_count": 0,
            "saved_courses": [], "shortlist_items": [], "notifications": [],
            "cluster_results": [], "latest_result": None, "snapshot": None,
            "quiz_submission": None, "saved_course_ids": [],
            "recommended_careers": CareerProfile.objects.all()[:3],
            "recent_news": Article.objects.filter(is_published=True).order_by('-created_at')[:3],
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
        })

    user = request.user
    if not user.is_verified:
        messages.warning(request, "You must verify your email to access the dashboard.")
        return redirect("accounts:login")
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
            .select_related("cluster").order_by("-cluster_points")[:8]
        )
        from courses.models import CourseOffering
        kcn_map = {}
        for r in cluster_results:
            knum = r.cluster.kuccps_number if r.cluster else None
            if knum:
                kcn_map[knum] = float(r.cluster_points)
        eligible_set: set = set()
        for offering in CourseOffering.objects.filter(
            cutoff_points__isnull=False, course__cluster__isnull=False
        ).select_related("course__cluster"):
            if not offering.cutoff_points:
                continue
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
    saved_count   = SavedCourse.objects.filter(user=user).count()
    saved_courses = (
        SavedCourse.objects.filter(user=user)
        .select_related('course', 'course__course_type', 'course__cluster')
        .order_by('-saved_at')[:6]
    )
    saved_course_ids = list(
        SavedCourse.objects.filter(user=user).values_list('course_id', flat=True)
    )

    # ── Shortlist & notifications ─────────────────────────────────────────────
    shortlist_items = (
        CourseShortlist.objects.filter(user=user)
        .select_related('course', 'course__course_type', 'course__cluster')
        [:4]
    )
    shortlist_count = CourseShortlist.objects.filter(user=user).count()
    notifications = Notification.objects.filter(user=user, is_read=False).order_by("-created_at")[:5]
    unread_count  = Notification.objects.filter(user=user, is_read=False).count()

    # ── Latest news articles ─────────────────────────────────────────────────
    from resources.models import Article
    recent_news = Article.objects.filter(is_published=True).order_by('-created_at')[:3]

    # ── Career data ───────────────────────────────────────────────────────────
    recommended_careers = CareerProfile.objects.all()[:3]
    snapshot            = CareerSessionSnapshot.objects.filter(user=user).order_by('-computed_at').first()
    quiz_submission     = QuizSubmission.objects.filter(user=user).order_by('-created_at').first()

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

        _qs = (
            Course.objects
            .filter(_q, course_type__name='Degree', cluster__isnull=False)
            .select_related('cluster')
            .distinct()[:20]
        )
        _seen = set()
        for _c in _qs:
            _knum = _c.cluster.kuccps_number if _c.cluster else None
            if _knum in _seen:
                continue
            _seen.add(_knum)
            _off = CourseOffering.objects.filter(course=_c, cutoff_points__isnull=False).first()
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

    # ── Institutions quick links ──────────────────────────────────────────────
    from institutions.models import InstitutionType, Institution
    from django.urls import reverse
    _INST_ICONS = {
        'public university':   'fas fa-university',
        'private university':  'fas fa-school',
        'kmtc':                'fas fa-heartbeat',
        'tvet':                'fas fa-tools',
        'ttc':                 'fas fa-chalkboard-teacher',
        'specialized':         'fas fa-flask',
    }
    inst_type_links = []
    for itype in InstitutionType.objects.all()[:6]:
        _count = Institution.objects.filter(institution_type=itype).count()
        _icon_key = next((k for k in _INST_ICONS if k in itype.name.lower()), None)
        inst_type_links.append({
            'label': itype.name,
            'url':   reverse('institutions:institution_type_detail', kwargs={'type_slug': itype.slug}),
            'icon':  _INST_ICONS.get(_icon_key, 'fas fa-building'),
            'count': _count,
        })

    return render(request, "accounts/dashboard.html", {
        # KCSE / clusters
        "latest_result":     latest_result,
        "cluster_results":   cluster_results,
        "eligible_count":    eligible_count,
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
        "recent_news":         recent_news,
        # Timeline
        "timeline_phase":    timeline_phase,
        "timeline_days":     timeline_days,
        "timeline_label":    timeline_label,
        "timeline_date":     timeline_date,
        # Institutions
        "inst_type_links":   inst_type_links,
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
@login_required
@require_http_methods(["GET", "POST"])
def change_password_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")
        if not password1 or password1 != password2:
            messages.error(request, "Passwords do not match.")
        else:
            request.user.set_password(password1)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully.")
            return redirect("accounts:dashboard")

    return render(request, "accounts/change_password.html")



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
    share_msg = f"I use CareerNext to check KCSE cluster points & find courses I qualify for — it's free! Join via my link: {ref_url}"
    return render(request, 'accounts/referral.html', {
        'ref': ref,
        'ref_url': ref_url,
        'conversions': conversions,
        'pending': pending,
        'total_referred': conversions.count(),
        'whatsapp_text': share_msg,
        'twitter_text': "Check your KCSE cluster points & find courses you qualify for — free! 🎓",
        'telegram_text': share_msg,
    })


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
    from resources.models import SuccessStory
    stories = SuccessStory.objects.filter(is_active=True).order_by('order', 'id')

    # Sample cluster preview bars for the hero card (static illustrative data)
    sample_clusters = [
        ("Cluster 1", 75, "#4f46e5"),
        ("Cluster 4", 60, "#0891b2"),
        ("Cluster 9", 88, "#16a34a"),
        ("Cluster 12", 52, "#d97706"),
    ]
    return render(request, "accounts/home.html", {
        "stories": stories,
        "sample_clusters": sample_clusters,
    })


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

    return render(request, 'accounts/shortlist.html', {
        'items': items,
        'has_cluster_data': bool(cluster_map),
        'rank_choices': RANK_CHOICES,
        'used_ranks': list(used_ranks),
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

    # Header
    p.setFillColor(colors.HexColor('#1e3a8a'))
    p.rect(0, h - 3*cm, w, 3*cm, fill=1, stroke=0)
    p.setFillColor(colors.white)
    p.setFont('Helvetica-Bold', 18)
    p.drawString(1.5*cm, h - 1.6*cm, 'CareerNext — My Course Shortlist')
    p.setFont('Helvetica', 9)
    name = request.user.full_name or request.user.email
    p.drawString(1.5*cm, h - 2.3*cm, f'Student: {name}   |   Generated: {timezone.now().strftime("%d %b %Y")}')

    y = h - 4*cm
    p.setFillColor(colors.HexColor('#1e293b'))

    if not items:
        p.setFont('Helvetica', 11)
        p.drawString(1.5*cm, y, 'Your shortlist is empty.')
        p.save()
        return response

    for i, item in enumerate(items, 1):
        course = item.course
        if y < 6*cm:
            p.showPage()
            y = h - 2*cm

        rank_label = f'Choice #{item.rank}' if item.rank else f'#{i}'
        p.setFont('Helvetica-Bold', 11)
        p.setFillColor(colors.HexColor('#1d4ed8'))
        p.drawString(1.5*cm, y, f'{rank_label}  {course.name}')
        y -= 0.5*cm

        p.setFont('Helvetica', 9)
        p.setFillColor(colors.HexColor('#475569'))
        type_label = course.course_type.name if course.course_type else '—'
        cluster_label = course.cluster.name if course.cluster else '—'
        grade_label = course.minimum_mean_grade or '—'
        duration_label = course.duration or '—'
        p.drawString(2*cm, y, f'Type: {type_label}   |   Cluster: {cluster_label}   |   Min Grade: {grade_label}   |   Duration: {duration_label}')
        y -= 0.45*cm

        offs = list(course.offerings.all()[:4])
        if offs:
            inst_names = ', '.join(o.institution.name for o in offs)
            if course.offerings.count() > 4:
                inst_names += f' +{course.offerings.count()-4} more'
            p.drawString(2*cm, y, f'Institutions: {inst_names}')
            y -= 0.45*cm

        if item.notes:
            p.setFont('Helvetica-Oblique', 8)
            p.setFillColor(colors.HexColor('#64748b'))
            p.drawString(2*cm, y, f'Notes: {item.notes[:120]}')
            y -= 0.45*cm

        # Divider
        p.setStrokeColor(colors.HexColor('#e2e8f0'))
        p.line(1.5*cm, y, w - 1.5*cm, y)
        y -= 0.6*cm

    # Footer
    p.setFont('Helvetica', 7)
    p.setFillColor(colors.HexColor('#94a3b8'))
    p.drawCentredString(w/2, 1.5*cm, 'careernext.co.ke  |  CareerNext — Empowering Kenyan Students')
    p.drawCentredString(w/2, 1*cm, 'Apply officially at kuccps.ac.ke')
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
    from .models import Notification
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"status": "ok"})


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request: HttpRequest, notif_id: int) -> HttpResponse:
    from django.http import JsonResponse
    from .models import Notification
    Notification.objects.filter(user=request.user, id=notif_id).update(is_read=True)
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