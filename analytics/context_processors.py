from django.conf import settings


def posthog_keys(request):
    return {
        'POSTHOG_API_KEY': getattr(settings, 'POSTHOG_API_KEY', ''),
        'POSTHOG_HOST':    getattr(settings, 'POSTHOG_HOST', 'https://eu.i.posthog.com'),
    }


def sentry_context(request):
    return {
        'SENTRY_DSN':         getattr(settings, '_SENTRY_DSN', '') or '',
        'SENTRY_RELEASE':     getattr(settings, 'SENTRY_RELEASE', '') or '',
        'SENTRY_ENVIRONMENT': getattr(settings, 'SENTRY_ENVIRONMENT', 'development'),
    }


def ga_context(request):
    return {
        'GA_MEASUREMENT_ID': getattr(settings, 'GA_MEASUREMENT_ID', ''),
    }


def data_version(request):
    """Expose KUCCPS data version/cycle to every template."""
    from courses.models import LATEST_CUTOFF_YEAR
    return {
        'LATEST_CUTOFF_YEAR': LATEST_CUTOFF_YEAR,
        'DATA_VERSION': getattr(settings, 'DATA_VERSION', '2025'),
        'DATA_CYCLE':   getattr(settings, 'DATA_CYCLE', '2026/2027'),
        'DATA_UPDATED': getattr(settings, 'DATA_UPDATED', 'September 2026'),
    }
