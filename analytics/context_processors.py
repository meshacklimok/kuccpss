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
