import logging
import threading
import time

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render

from kuccpss.ip_utils import get_client_ip

log = logging.getLogger(__name__)


class ContentSecurityPolicyMiddleware:
    """
    Sends a Content-Security-Policy in **report-only** mode.

    The site loads first-party assets plus a fairly wide set of third parties
    (jsdelivr/cdnjs/unpkg CDNs, Google Fonts, Google OAuth, GA, Sentry,
    PostHog, Tawk.to chat, Cloudinary images) and there's no browser available
    in this environment to verify an enforcing policy wouldn't break login,
    checkout, or the chat widget in production. Report-Only lets browsers
    report violations (visible in devtools / the `CSP-Report-Only` header)
    without blocking anything, so the policy below can be tightened and
    promoted to `Content-Security-Policy` once verified against real traffic.
    """
    POLICY = "; ".join([
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com "
            "https://code.jquery.com https://www.googletagmanager.com "
            "https://browser.sentry-cdn.com https://embed.tawk.to https://va.tawk.to "
            "https://accounts.google.com https://apis.google.com",
        "style-src 'self' 'unsafe-inline' "
            "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:",
        "img-src 'self' data: blob: https://res.cloudinary.com https://images.unsplash.com "
            "https://cdn-icons-png.flaticon.com https://flagcdn.com https://ssl.gstatic.com "
            "https://www.googletagmanager.com https://embed.tawk.to",
        "connect-src 'self' https://www.google-analytics.com https://analytics.google.com "
            "https://eu.posthog.com https://app.posthog.com https://*.sentry.io "
            "https://embed.tawk.to https://va.tawk.to wss://va.tawk.to",
        "frame-src 'self' https://accounts.google.com https://embed.tawk.to",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self' https://accounts.google.com",
    ])

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy-Report-Only'] = self.POLICY
        return response


class ReferralMiddleware:
    """Capture ?ref=CODE from URL → store in session for later attribution on registration."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code = request.GET.get('ref', '').strip().upper()
        if code and len(code) <= 12 and not request.session.get('referral_code'):
            cache_key = f'ref_valid:{code}'
            is_valid = cache.get(cache_key)
            if is_valid is None:
                from accounts.models import Referral
                is_valid = Referral.objects.filter(code=code, converted=False).exists()
                cache.set(cache_key, is_valid, 300)
            if is_valid:
                request.session['referral_code'] = code
        return self.get_response(request)


class DisableHttp3Middleware:
    """
    Clears Cloudflare/Render's alt-svc header so browsers don't
    attempt HTTP/3 (QUIC), which fails on some Kenyan ISPs.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['alt-svc'] = 'clear'
        return response


class SlowRequestLogMiddleware:
    """
    Logs any request that takes more than SLOW_REQUEST_THRESHOLD_MS milliseconds.
    Helps identify performance bottlenecks without full APM tooling.
    """
    THRESHOLD_MS = 1500  # log requests slower than 1.5 s

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        t0 = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = (time.monotonic() - t0) * 1000
        if elapsed_ms > self.THRESHOLD_MS:
            log.warning(
                "SLOW REQUEST %.0fms  %s %s",
                elapsed_ms,
                request.method,
                request.path,
            )
        return response


class GracefulErrorMiddleware:
    """
    Catches unhandled exceptions and returns a friendly response instead of a raw
    Django debug traceback in production.  Technical details are still sent to Sentry.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # Let Django handle 404 / permission errors normally
        from django.http import Http404
        from django.core.exceptions import PermissionDenied, SuspiciousOperation
        if isinstance(exception, (Http404, PermissionDenied, SuspiciousOperation)):
            return None

        log.exception("Unhandled exception on %s %s", request.method, request.path)

        is_htmx = request.headers.get('HX-Request') == 'true'
        if is_htmx:
            # HTMX partial — return a small error fragment the front-end can swap in
            return JsonResponse(
                {'error': 'Something went wrong. Please try again.'},
                status=500,
            )

        from django.conf import settings
        if settings.DEBUG:
            return None  # let Django show the traceback in dev

        return render(request, '500.html', status=500)


class MaintenanceModeMiddleware:
    """
    Serves a 503 "we'll be right back" page to everyone while
    ``settings.MAINTENANCE_MODE`` is on.

    Deliberately let through so you can still work on a sleeping site:
      * staff / superusers (session cookie must already exist, or log in via /admin/)
      * /cn-staff/ (admin) and the login pages, so you can *become* staff
      * any IP listed in ``settings.MAINTENANCE_ALLOWED_IPS``
      * static & media files, and health checks

    Returns HTTP 503 with ``Retry-After`` — the correct status for planned
    downtime, so Google treats it as temporary and keeps your rankings.
    """

    # Prefixes that stay reachable while maintenance mode is on.
    EXEMPT_PREFIXES = (
        '/cn-staff/',          # Django admin
        '/accounts/login/',
        '/accounts/logout/',
        '/static/',
        '/media/',
        '/health/',
        '/robots.txt',         # keep 200 — a 503 here can stall crawling
        '/sw.js',
        '/offline/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings

        if not getattr(settings, 'MAINTENANCE_MODE', False):
            return self.get_response(request)

        if request.path.startswith(self.EXEMPT_PREFIXES):
            return self.get_response(request)

        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and user.is_staff:
            return self.get_response(request)

        allowed_ips = getattr(settings, 'MAINTENANCE_ALLOWED_IPS', [])
        if allowed_ips and get_client_ip(request) in allowed_ips:
            return self.get_response(request)

        retry_after = getattr(settings, 'MAINTENANCE_RETRY_AFTER', 3600)

        if request.headers.get('HX-Request') == 'true' or request.path.startswith('/api/'):
            response = JsonResponse(
                {'error': settings.MAINTENANCE_MESSAGE, 'maintenance': True},
                status=503,
            )
        else:
            response = render(
                request,
                '503.html',
                {
                    'maintenance_message': settings.MAINTENANCE_MESSAGE,
                    'maintenance_until': getattr(settings, 'MAINTENANCE_UNTIL', ''),
                },
                status=503,
            )

        response['Retry-After'] = str(retry_after)
        response['Cache-Control'] = 'no-store'
        return response


class PageTrackingMiddleware:
    """
    Records every non-static, non-bot page hit to PageViewLog with timing and device.
    Must come after SessionMiddleware + AuthenticationMiddleware in MIDDLEWARE.
    """
    SKIP_PREFIXES = ('/static/', '/media/', '/favicon', '/robots', '/sitemap')
    SKIP_PATHS    = {'/analytics/live-feed/', '/analytics/pwa-install/', '/analytics/heartbeat/'}

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _detect_device(ua: str) -> str:
        ua = ua.lower()
        if any(b in ua for b in ('bot', 'crawler', 'spider', 'scraper', 'slurp', 'bingpreview', 'headless')):
            return 'bot'
        if 'tablet' in ua or 'ipad' in ua:
            return 'tablet'
        if any(m in ua for m in ('mobile', 'android', 'iphone', 'ipod', 'blackberry', 'windows phone')):
            return 'mobile'
        if ua:
            return 'desktop'
        return 'unknown'

    def __call__(self, request):
        path = request.path
        if (any(path.startswith(p) for p in self.SKIP_PREFIXES) or
                path in self.SKIP_PATHS):
            return self.get_response(request)

        t0 = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        try:
            # Capture everything from request/response synchronously — the
            # request object must not be touched from the background thread.
            ua  = request.META.get('HTTP_USER_AGENT', '')
            ip  = get_client_ip(request)
            user_id = request.user.pk if request.user.is_authenticated else None
            sk = ''
            try:
                if not request.session.session_key:
                    request.session.create()
                sk = request.session.session_key or ''
            except Exception:
                pass
            threading.Thread(
                target=self._write_logs,
                args=(
                    path[:500],
                    request.method[:10],
                    response.status_code,
                    elapsed_ms,
                    request.META.get('HTTP_REFERER', '')[:500],
                    self._detect_device(ua),
                    user_id,
                    sk,
                    ip,
                ),
                daemon=True,
            ).start()
        except Exception:
            pass

        return response

    @staticmethod
    def _write_logs(path, method, status_code, elapsed_ms, referrer,
                    device, user_id, sk, ip):
        """Runs in a background thread so DB writes never delay the response."""
        from django.db import connections
        try:
            from analytics.models import PageViewLog
            PageViewLog.objects.create(
                path=path,
                method=method,
                status_code=status_code,
                response_time_ms=elapsed_ms,
                referrer=referrer,
                device=device,
                user_id=user_id,
                session_key=sk,
                ip=ip or None,
            )
            # Upsert SessionLog so we can compute avg session duration
            if sk:
                from django.db.models import F as _F
                from django.utils import timezone as _tz
                from analytics.models import SessionLog
                now = _tz.now()
                upd_kw = {'last_seen_at': now, 'page_count': _F('page_count') + 1}
                if user_id:
                    upd_kw['user_id'] = user_id
                if not SessionLog.objects.filter(session_key=sk).update(**upd_kw):
                    from analytics.geo import get_location
                    country, region = get_location(ip or '')
                    SessionLog.objects.create(
                        session_key=sk, user_id=user_id,
                        ip=ip or None, device=device,
                        country=country, region=region,
                        last_seen_at=now,
                    )
        except Exception:
            pass
        finally:
            connections.close_all()


class HeavyEndpointRateLimitMiddleware:
    """
    IP-based rate limiting for the two heaviest endpoints:
      - /clusterpoints/          (calculator)  → 20 POSTs / 10 min
      - /clusterpoints/eligible/ (results)     → 30 GETs  / 10 min

    Uses the Django cache backend (works with local-mem or Redis).
    Returns HTTP 429 on breaches with a Retry-After header.
    """
    RULES = [
        ('/clusterpoints/', 'POST', 20, 600),
        ('/clusterpoints/eligible-courses/', 'GET', 30, 600),
        ('/career/', 'POST', 10, 600),
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)
        for path_prefix, method, limit, window in self.RULES:
            if request.method == method and request.path.startswith(path_prefix):
                key = f'rl:{method}:{path_prefix}:{ip}'
                count = cache.get(key, 0)
                if count >= limit:
                    log.warning("Rate limit hit: %s %s from %s", method, path_prefix, ip)
                    is_htmx = request.headers.get('HX-Request') == 'true'
                    if is_htmx or request.headers.get('Accept', '').startswith('application/json'):
                        resp = JsonResponse(
                            {'error': 'Too many requests. Please wait a moment and try again.'},
                            status=429,
                        )
                    else:
                        resp = render(request, '429.html', status=429)
                    resp['Retry-After'] = str(window)
                    return resp
                cache.set(key, count + 1, window)
                break

        return self.get_response(request)
