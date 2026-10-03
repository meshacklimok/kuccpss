"""
In-process periodic jobs.

Render/Railway run only the web process — no qcluster worker and no cron — so the
django-q Schedules never fire. This daemon thread runs the jobs that can't wait for
the next deploy (build.sh already handles the daily-ish cleanups):

  - payments.tasks.check_pending_payments  — recover payments whose webhook was lost
  - mentorship.tasks.send_session_reminders / complete_expired_sessions

A Postgres advisory lock makes sure only one process runs a cycle at a time, however
many gunicorn workers or instances call start_scheduler(). Every job is also safe to
re-run on its own. Disable with BACKGROUND_JOBS_ENABLED=False (e.g. if a real cron
takes over); it is off by default when DEBUG is on.

Each cycle also requests KEEPALIVE_URL/health/ (Render sets RENDER_EXTERNAL_URL, the
default). Render's free tier sleeps after 15 min without inbound traffic, and a
request through the public URL counts — so the jobs keep running overnight.
"""
import logging
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

INTERVAL_SECONDS = 600
STARTUP_DELAY_SECONDS = 60      # let the app finish booting first
_LOCK_KEY = 0x6B75636370        # arbitrary app-wide advisory-lock id ("kuccp")

_started = False
_start_lock = threading.Lock()


def _jobs():
    from mentorship.tasks import complete_expired_sessions, send_session_reminders
    from payments.tasks import check_pending_payments
    return [check_pending_payments, send_session_reminders, complete_expired_sessions]


def _try_lock(connection) -> bool:
    if connection.vendor != 'postgresql':
        return True  # local SQLite dev: single process
    with connection.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", [_LOCK_KEY])
        return cur.fetchone()[0]


def _unlock(connection) -> None:
    if connection.vendor == 'postgresql':
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", [_LOCK_KEY])


def run_jobs_once() -> bool:
    """Run every job once unless another process holds the lock. Returns True if it ran."""
    from django.db import connection

    try:
        if not _try_lock(connection):
            return False
        try:
            for job in _jobs():
                try:
                    job()
                except Exception:
                    log.exception("Scheduled job %s failed", job.__name__)
        finally:
            _unlock(connection)
        return True
    finally:
        # Don't hold a connection open for the 10 min between cycles
        connection.close()


def keep_awake() -> None:
    """Request our own public URL so the host doesn't put the service to sleep."""
    from django.conf import settings

    base = getattr(settings, 'KEEPALIVE_URL', '')
    if not base:
        return
    try:
        urllib.request.urlopen(base.rstrip('/') + '/health/', timeout=15).close()
    except (urllib.error.URLError, OSError):
        # A 503 (DB down) still counted as traffic; anything else, try next cycle
        log.info("Keep-awake ping failed", exc_info=True)


def _loop():
    time.sleep(STARTUP_DELAY_SECONDS)
    while True:
        keep_awake()
        try:
            run_jobs_once()
        except Exception:
            # DB unreachable (e.g. Neon waking up) — try again next cycle
            log.warning("Scheduled jobs cycle failed; will retry", exc_info=True)
        time.sleep(INTERVAL_SECONDS)


def start_scheduler() -> None:
    from django.conf import settings

    global _started
    if not getattr(settings, 'BACKGROUND_JOBS_ENABLED', False):
        return
    with _start_lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, name="background-jobs", daemon=True).start()
