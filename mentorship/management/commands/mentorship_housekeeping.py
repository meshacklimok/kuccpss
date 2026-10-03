"""
Single command that handles both:
  1. Sending reminder emails for sessions in the next 1–2 hours
  2. Auto-completing sessions whose slot time has passed by > 30 minutes

Runs automatically every few minutes via kuccpss/scheduler.py; this command is
for running it by hand:
  python manage.py mentorship_housekeeping
"""
from django.core.management.base import BaseCommand

from mentorship.tasks import complete_expired_sessions, send_session_reminders


class Command(BaseCommand):
    help = "Send session reminders and auto-complete expired confirmed sessions"

    def handle(self, *args, **options):
        sent = send_session_reminders()
        self.stdout.write(self.style.SUCCESS(f"Reminders sent: {sent}"))
        completed = complete_expired_sessions()
        self.stdout.write(self.style.SUCCESS(f"Auto-completed: {completed} expired sessions"))
