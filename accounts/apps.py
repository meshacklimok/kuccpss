import os
import sys

from django.apps import AppConfig

# Processes that serve no web traffic — warming their per-process cache is
# pointless (and during migrate/test the tables may not even exist yet).
_NON_SERVING_COMMANDS = {
    'migrate', 'makemigrations', 'shell', 'test', 'collectstatic',
    'createsuperuser', 'loaddata', 'dumpdata', 'qcluster', 'check',
}


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        import accounts.signals

        if _NON_SERVING_COMMANDS.intersection(sys.argv):
            return
        # Under runserver's autoreloader, only warm in the serving child.
        if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
            return
        from accounts.tasks import start_homepage_cache_warmer
        start_homepage_cache_warmer()