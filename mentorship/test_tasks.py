"""
Tests for the periodic mentorship jobs (mentorship/tasks.py) and the in-process
scheduler that runs them (kuccpss/scheduler.py).
"""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from kuccpss import scheduler
from mentorship.models import MentorProfile, MentorshipSession, TimeSlot
from mentorship.tasks import complete_expired_sessions, send_session_reminders

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MentorshipTaskTests(TestCase):
    def setUp(self):
        mentor_user = User.objects.create_user(email="mentor@example.com", password="pass1234")
        self.mentor = MentorProfile.objects.create(
            user=mentor_user, bio="Mentor", whatsapp="+254712345678", is_approved=True,
        )
        self.mentee = User.objects.create_user(email="mentee@example.com", password="pass1234")

    def _session(self, starts_at, status="confirmed"):
        local = timezone.localtime(starts_at).replace(second=0, microsecond=0)
        slot = TimeSlot.objects.create(
            mentor=self.mentor, date=local.date(), start_time=local.time(), is_booked=True,
        )
        return MentorshipSession.objects.create(
            token=uuid.uuid4(), mentor=self.mentor, mentee=self.mentee, slot=slot,
            mentee_question="Q", amount=100, mentor_payout=70, status=status,
        )

    def test_reminder_sent_once_to_mentee_and_mentor(self):
        session = self._session(timezone.now() + timedelta(minutes=90))
        self.assertEqual(send_session_reminders(), 1)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["mentee@example.com", "mentor@example.com"])
        session.refresh_from_db()
        self.assertTrue(session.reminder_sent)

        # The scheduler runs every 10 min, so the session stays in the window — no resend
        self.assertEqual(send_session_reminders(), 0)
        self.assertEqual(len(mail.outbox), 2)

    def test_no_reminder_outside_window_or_unconfirmed(self):
        self._session(timezone.now() + timedelta(minutes=30))
        self._session(timezone.now() + timedelta(hours=5))
        self._session(timezone.now() + timedelta(minutes=90), status="pending_payment")
        self.assertEqual(send_session_reminders(), 0)
        self.assertEqual(mail.outbox, [])

    def test_reminder_window_crossing_midnight(self):
        # 23:00 local: the window is 00:00–01:00 the next day
        eleven_pm = timezone.localtime().replace(hour=23, minute=0, second=0, microsecond=0)
        session = self._session(eleven_pm + timedelta(minutes=90))
        with patch("django.utils.timezone.now", return_value=eleven_pm):
            self.assertEqual(send_session_reminders(), 1)
        session.refresh_from_db()
        self.assertTrue(session.reminder_sent)

    def test_expired_sessions_completed(self):
        old = self._session(timezone.now() - timedelta(hours=2))
        yesterday = self._session(timezone.now() - timedelta(days=1))
        recent = self._session(timezone.now() - timedelta(minutes=10))
        upcoming = self._session(timezone.now() + timedelta(hours=3))

        self.assertEqual(complete_expired_sessions(), 2)
        statuses = {s.pk: s.status for s in MentorshipSession.objects.all()}
        self.assertEqual(statuses[old.pk], "completed")
        self.assertEqual(statuses[yesterday.pk], "completed")
        self.assertEqual(statuses[recent.pk], "confirmed")
        self.assertEqual(statuses[upcoming.pk], "confirmed")
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.total_sessions, 2)

        self.assertEqual(complete_expired_sessions(), 0)


class SchedulerTests(TestCase):
    def test_run_jobs_once_survives_failing_job(self):
        calls = []

        def boom():
            calls.append("boom")
            raise RuntimeError("fail")

        def ok():
            calls.append("ok")

        with patch.object(scheduler, "_jobs", return_value=[boom, ok]), \
                patch("django.db.connection.close"), \
                self.assertLogs("kuccpss.scheduler", "ERROR") as logs:
            self.assertTrue(scheduler.run_jobs_once())
        self.assertEqual(calls, ["boom", "ok"])
        self.assertIn("boom failed", logs.output[0])

    def test_run_jobs_once_skips_when_locked(self):
        job = patch.object(scheduler, "_jobs").start()
        self.addCleanup(patch.stopall)
        with patch.object(scheduler, "_try_lock", return_value=False), \
                patch("django.db.connection.close"):
            self.assertFalse(scheduler.run_jobs_once())
        job.assert_not_called()

    @override_settings(BACKGROUND_JOBS_ENABLED=False)
    def test_start_scheduler_disabled(self):
        with patch("threading.Thread") as thread:
            scheduler.start_scheduler()
        thread.assert_not_called()

    @override_settings(BACKGROUND_JOBS_ENABLED=True)
    def test_start_scheduler_starts_once(self):
        with patch.object(scheduler, "_started", False), patch("threading.Thread") as thread:
            scheduler.start_scheduler()
            scheduler.start_scheduler()
        thread.assert_called_once()
        self.assertTrue(thread.call_args.kwargs["daemon"])

    @override_settings(KEEPALIVE_URL="https://example.onrender.com/")
    def test_keep_awake_pings_health(self):
        with patch("urllib.request.urlopen") as urlopen:
            scheduler.keep_awake()
        self.assertEqual(urlopen.call_args.args[0], "https://example.onrender.com/health/")

    @override_settings(KEEPALIVE_URL="https://example.onrender.com")
    def test_keep_awake_swallows_network_errors(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            scheduler.keep_awake()  # must not raise

    @override_settings(KEEPALIVE_URL="")
    def test_keep_awake_disabled_without_url(self):
        with patch("urllib.request.urlopen") as urlopen:
            scheduler.keep_awake()
        urlopen.assert_not_called()

    def test_gunicorn_starts_threads_in_each_worker(self):
        # preload_app runs ready() in the master; threads must start post-fork
        import runpy
        from django.conf import settings as dj_settings
        conf = runpy.run_path(str(dj_settings.BASE_DIR / "gunicorn.conf.py"))
        self.assertTrue(conf["preload_app"])
        with patch("accounts.apps.start_web_threads") as start:
            conf["post_worker_init"](worker=None)
        start.assert_called_once()

    def test_ready_does_not_start_threads_under_gunicorn(self):
        from django.apps import apps
        with patch("sys.argv", ["/usr/bin/gunicorn", "kuccpss.wsgi:application"]), \
                patch("accounts.apps.start_web_threads") as start:
            apps.get_app_config("accounts").ready()
        start.assert_not_called()

    def test_web_threads_start_warmer_and_scheduler(self):
        from accounts.apps import start_web_threads
        with patch("accounts.tasks.start_homepage_cache_warmer") as warmer, \
                patch("kuccpss.scheduler.start_scheduler") as sched:
            start_web_threads()
        warmer.assert_called_once()
        sched.assert_called_once()
