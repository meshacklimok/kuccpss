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
        # Gunicorn starts them per worker from post_worker_init (gunicorn.conf.py):
        # with preload_app this runs in the master, and threads don't survive fork.
        # Under runserver's autoreloader, only start them in the serving child.
        if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') == 'true':
            start_web_threads()


def start_web_threads():
    """Start the per-process background threads of a web server process."""
    from accounts.tasks import start_homepage_cache_warmer
    from kuccpss.scheduler import start_scheduler
    start_homepage_cache_warmer()
    start_scheduler()