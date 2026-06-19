"""
Single command that handles both:
  1. Sending reminder emails for sessions in the next 2 hours
  2. Auto-completing sessions whose slot time has passed by > 30 minutes

Run via cron / Render scheduled job:
  python manage.py mentorship_housekeeping
"""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone


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
            send_mail(
                subject=f"⏰ Reminder: Your session with {mentor_name} is in ~1 hour",
                message=(
                    f"Hi {mentee_name},\n\n"
                    f"Your 15-minute mentorship call with {mentor_name} starts at {slot_str}.\n\n"
                    f"WhatsApp {mentor_name} now to confirm: {session.mentor.whatsapp}\n\n"
                    f"Your topic: \"{session.mentee_question}\"\n\n"
                    f"CareerNext Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[session.mentee.email],
                fail_silently=True,
            )
            # Mentor reminder
            send_mail(
                subject=f"⏰ Reminder: Session with {mentee_name} in ~1 hour",
                message=(
                    f"Hi {mentor_name},\n\n"
                    f"Your mentorship session with {mentee_name} starts at {slot_str}.\n\n"
                    f"They should WhatsApp you shortly to confirm.\n\n"
                    f"Their topic: \"{session.mentee_question}\"\n\n"
                    f"After the session, mark it complete:\n"
                    f"https://www.careernext.co.ke/mentorship/dashboard/\n\n"
                    f"CareerNext Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[session.mentor.user.email],
                fail_silently=True,
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
