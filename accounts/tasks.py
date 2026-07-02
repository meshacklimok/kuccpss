"""
Homepage cache warming.

The public homepage context is cached (static content 5 min, trends up to
1 hr) but the default LocMemCache is per-process and empty after every
restart — so without warming, the first visitor after a deploy/cold-start
pays the full recompute (~2-5s). `start_homepage_cache_warmer()` runs a
daemon thread per web process that keeps both cache entries populated:
calling the context functions is a no-op while their entries are live and
recomputes them shortly after they expire.

Enqueue the one-shot variant with: async_task('accounts.tasks.warm_homepage_cache')
(only useful when a shared cache backend like Redis is configured).
"""
import logging
import threading
import time

log = logging.getLogger(__name__)

_WARM_INTERVAL_SECONDS = 240  # below the 300s static-context TTL
_warmer_started = False
_warmer_lock = threading.Lock()


def warm_homepage_cache():
    """Populate (or refresh, if expired) the homepage cache entries."""
    from django.contrib.auth.models import AnonymousUser
    from django.template.loader import render_to_string
    from django.test import RequestFactory

    from accounts.views import _get_home_static_context
    from courses.trends import get_trends_context
    from payments.services import price_for_feature

    ctx = dict(_get_home_static_context())
    ctx.update(get_trends_context())
    ctx["calculator_price"] = price_for_feature('view_cluster_points')
    ctx["engine_price"] = price_for_feature('premium_career_report')
    # A full render compiles the whole template tree (extends/includes) into
    # the cached loader — another ~1s one-time cost per process otherwise
    # paid by the first visitor. A synthetic request lets context processors
    # (csrf, auth, …) run as they would for a real visitor; the host must be
    # one that passes ALLOWED_HOSTS since the template builds absolute URIs.
    from django.conf import settings
    host = next(
        (h for h in settings.ALLOWED_HOSTS if h and not h.startswith(('*', '.'))),
        'localhost',
    )
    request = RequestFactory().get('/', HTTP_HOST=host)
    request.user = AnonymousUser()
    render_to_string('accounts/home.html', ctx, request=request)


def _warm_loop():
    while True:
        try:
            warm_homepage_cache()
        except Exception:
            # DB may not be ready right at startup, or a query may fail —
            # never let the warmer kill anything, just retry next cycle.
            log.warning("Homepage cache warm failed; will retry", exc_info=True)
        time.sleep(_WARM_INTERVAL_SECONDS)


def start_homepage_cache_warmer():
    global _warmer_started
    with _warmer_lock:
        if _warmer_started:
            return
        _warmer_started = True
    threading.Thread(
        target=_warm_loop, name="homepage-cache-warmer", daemon=True
    ).start()
