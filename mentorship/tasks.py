"""
Periodic mentorship housekeeping, run by kuccpss/scheduler.py every few minutes
and by `python manage.py mentorship_housekeeping`. Both jobs are safe to re-run:
each session is claimed with a conditional UPDATE before acting on it.
"""
import logging
from datetime import datetime, timedelta

from django.utils import timezone

from kuccpss.email_utils import send_branded_email

logger = logging.getLogger(__name__)


def send_session_reminders() -> int:
    """Email mentee + mentor once for each confirmed session starting in 60–120 min."""
    from mentorship.models import MentorshipSession

    now = timezone.now()
    window_start = timezone.localtime(now + timedelta(minutes=60))
    window_end = timezone.localtime(now + timedelta(minutes=120))

    sessions = MentorshipSession.objects.filter(
        status="confirmed",
        reminder_sent=False,
        # The window can straddle midnight
        slot__date__range=(window_start.date(), window_end.date()),
    ).select_related("mentor", "mentor__user", "mentee", "slot")

    sent = 0
    for session in sessions:
        slot_dt = timezone.make_aware(datetime.combine(session.slot.date, session.slot.start_time))
        if not (window_start <= slot_dt <= window_end):
            continue
        # Claim before sending so overlapping runs can't double-send
        if not MentorshipSession.objects.filter(pk=session.pk, reminder_sent=False).update(reminder_sent=True):
            continue

        slot_str = session.slot.datetime_display
        mentor_name = session.mentor.display_name
        mentee_name = session.mentee_display

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

    if sent:
        logger.info("send_session_reminders: reminded %d sessions", sent)
    return sent


def complete_expired_sessions() -> int:
    """Mark confirmed sessions as completed once their start time is 30+ min past."""
    from django.db.models import Q
    from mentorship.models import MentorshipSession

    cutoff = timezone.localtime(timezone.now() - timedelta(minutes=30))
    expired = MentorshipSession.objects.filter(
        Q(slot__date__lt=cutoff.date())
        | Q(slot__date=cutoff.date(), slot__start_time__lte=cutoff.time()),
        status="confirmed",
    ).select_related("mentor")

    completed = 0
    for session in expired:
        if MentorshipSession.objects.filter(pk=session.pk, status="confirmed").update(status="completed"):
            session.mentor.refresh_stats()
            completed += 1

    if completed:
        logger.info("complete_expired_sessions: auto-completed %d sessions", completed)
    return completed
