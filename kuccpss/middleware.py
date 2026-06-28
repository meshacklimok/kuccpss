import logging
import time

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render

log = logging.getLogger(__name__)


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
            from analytics.models import PageViewLog
            ua  = request.META.get('HTTP_USER_AGENT', '')
            xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
            ip  = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')
            user = request.user if request.user.is_authenticated else None
            sk = ''
            try:
                if not request.session.session_key:
                    request.session.create()
                sk = request.session.session_key or ''
            except Exception:
                pass
            device = self._detect_device(ua)
            PageViewLog.objects.create(
                path=path[:500],
                method=request.method[:10],
                status_code=response.status_code,
                response_time_ms=elapsed_ms,
                referrer=request.META.get('HTTP_REFERER', '')[:500],
                device=device,
                user=user,
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
                if user:
                    upd_kw['user'] = user
                if not SessionLog.objects.filter(session_key=sk).update(**upd_kw):
                    from analytics.geo import get_location
                    country, region = get_location(ip or '')
                    SessionLog.objects.create(
                        session_key=sk, user=user,
                        ip=ip or None, device=device,
                        country=country, region=region,
                        last_seen_at=now,
                    )
        except Exception:
            pass

        return response


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

    @staticmethod
    def _get_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        # Use the last IP in the chain — set by Render's trusted edge, not the client
        return xff.split(',')[-1].strip() if xff else request.META.get('REMOTE_ADDR', '')

    def __call__(self, request):
        ip = self._get_ip(request)
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
