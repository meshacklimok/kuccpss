from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    name = 'analytics'

    def ready(self):
        import analytics.signals  # noqa: F401
