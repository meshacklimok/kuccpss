"""
Single command that handles both:
  1. Sending reminder emails for sessions in the next 2 hours
  2. Auto-completing sessions whose slot time has passed by > 30 minutes

Run via cron / Render scheduled job:
  python manage.py mentorship_housekeeping
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from kuccpss.email_utils import send_branded_email


class Command(BaseCommand):
    help = "Send session reminders and auto-complete expired confirmed sessions"

    def handle(self, *args, **options):
        self._send_reminders()
        self._complete_expired()

    def _send_reminders(self):
        from mentorship.models import MentorshipSession

        now = timezone.now()
        window_start = now + timedelta(minutes=60)
        window_end   = now + timedelta(minutes=120)

        sessions = MentorshipSession.objects.filter(
            status="confirmed",
            slot__date=window_start.date(),
        ).select_related("mentor", "mentor__user", "mentee", "slot")

        sent = 0
        for session in sessions:
            slot_dt = timezone.make_aware(
                timezone.datetime.combine(session.slot.date, session.slot.start_time)
            )
            if not (window_start <= slot_dt <= window_end):
                continue

            slot_str = session.slot.datetime_display
            mentor_name = session.mentor.display_name
            mentee_name = session.mentee_display

            # Mentee reminder
            send_branded_email(
                to=session.mentee.email,
                subject=f"Reminder: Your session with {mentor_name} starts in ~1 hour",
                heading="Your Session Starts Soon!",
                banner_label="⏰ 1-Hour Reminder",
                banner_color="amber",
                greeting=f"Hi {mentee_name},",
                body_lines=[
                    f"Your 15-minute mentorship call with {mentor_name} is starting in about 1 hour.",
                    f"WhatsApp {mentor_name} now to confirm how you'll connect: {session.mentor.whatsapp}",
                ],
                table_rows=[
                    {"label": "Mentor",    "value": mentor_name},
                    {"label": "Starts at", "value": slot_str},
                    {"label": "Topic",     "value": f'"{session.mentee_question}"'},
                ],
                note="Be on time — it's only 15 minutes. Good luck!",
                user_email=session.mentee.email,
            )
            # Mentor reminder
            send_branded_email(
                to=session.mentor.user.email,
                subject=f"Reminder: Session with {mentee_name} starts in ~1 hour",
                heading="Session Starting Soon!",
                banner_label="⏰ 1-Hour Reminder",
                banner_color="amber",
                greeting=f"Hi {mentor_name},",
                body_lines=[
                    f"Your mentorship session with {mentee_name} starts in about 1 hour.",
                    "They should WhatsApp you shortly to confirm how you'll connect.",
                ],
                table_rows=[
                    {"label": "Student",   "value": mentee_name},
                    {"label": "Starts at", "value": slot_str},
                    {"label": "Topic",     "value": f'"{session.mentee_question}"'},
                ],
                cta_url="https://www.careernext.co.ke/mentorship/dashboard/",
                cta_label="Go to Dashboard →",
                note="After the session, remember to mark it as complete from your dashboard.",
                user_email=session.mentor.user.email,
            )
            sent += 1

        self.stdout.write(self.style.SUCCESS(f"Reminders sent: {sent}"))

    def _complete_expired(self):
        from mentorship.models import MentorshipSession

        cutoff = timezone.now() - timedelta(minutes=30)
        expired = MentorshipSession.objects.filter(
            status="confirmed",
            slot__date__lt=cutoff.date(),
        ).select_related("mentor", "slot")

        # Also catch same-day sessions where start_time + 30 min has passed
        today_expired = MentorshipSession.objects.filter(
            status="confirmed",
            slot__date=cutoff.date(),
            slot__start_time__lte=cutoff.time(),
        ).select_related("mentor", "slot")

        completed = 0
        for session in list(expired) + list(today_expired):
            session.status = "completed"
            session.save(update_fields=["status"])
            session.mentor.refresh_stats()
            completed += 1

        self.stdout.write(self.style.SUCCESS(f"Auto-completed: {completed} expired sessions"))
