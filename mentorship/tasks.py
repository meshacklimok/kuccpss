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
                f"Your {session.duration_minutes}-minute mentorship call with {mentor_name} is starting in about 1 hour.",
                f"WhatsApp {mentor_name} now to confirm how you'll connect: {session.mentor.whatsapp}",
            ],
            table_rows=[
                {"label": "Mentor",    "value": mentor_name},
                {"label": "Starts at", "value": slot_str},
                {"label": "Topic",     "value": f'"{session.mentee_question}"'},
            ],
            note=f"Be on time — it's only {session.duration_minutes} minutes. Good luck!",
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
        _push(session.mentee, f"Your session with {mentor_name} starts in ~1 hour",
              f"WhatsApp {mentor_name} on {session.mentor.whatsapp} to confirm how you'll connect.",
              session.get_absolute_url())
        _push(session.mentor.user, f"Session with {mentee_name} starts in ~1 hour",
              f"{slot_str} — topic: {session.mentee_question[:80]}", "/mentorship/dashboard/")
        sent += 1

    if sent:
        logger.info("send_session_reminders: reminded %d sessions", sent)
    return sent


COMPLETE_GRACE_MINUTES = 15


def complete_expired_sessions() -> int:
    """Mark confirmed sessions as completed once they ended 15+ min ago
    (session length varies per mentor, so the end time is checked per session)."""
    from mentorship.models import MentorshipSession
    from mentorship.views import send_rating_request

    cutoff = timezone.localtime(timezone.now() - timedelta(minutes=COMPLETE_GRACE_MINUTES))
    candidates = MentorshipSession.objects.filter(
        slot__date__lte=cutoff.date(),
        status="confirmed",
    ).select_related("mentor", "mentor__user", "mentee", "slot")

    completed = 0
    for session in candidates:
        start = timezone.make_aware(datetime.combine(session.slot.date, session.slot.start_time))
        if start + timedelta(minutes=session.duration_minutes) > cutoff:
            continue
        if MentorshipSession.objects.filter(pk=session.pk, status="confirmed").update(status="completed"):
            session.mentor.refresh_stats()
            send_rating_request(session)
            completed += 1

    if completed:
        logger.info("complete_expired_sessions: auto-completed %d sessions", completed)
    return completed


ABANDONED_CHECKOUT_MINUTES = 30


def release_abandoned_bookings() -> int:
    """
    Free slots held by bookings that never got paid. Booking claims the slot before
    payment, so without this a student who closes the checkout page locks that slot
    forever. Sessions the student submitted an M-Pesa code for (pending manual
    verification) wait for an admin and are left alone.
    """
    from django.db import transaction
    from mentorship.models import MentorshipSession, TimeSlot
    from mentorship.views import _confirm_session_after_payment
    from payments.models import Payment
    from payments.services import fetch_intasend_status

    cutoff = timezone.now() - timedelta(minutes=ABANDONED_CHECKOUT_MINUTES)
    stale = MentorshipSession.objects.filter(
        status="pending_payment", created_at__lt=cutoff,
    ).select_related("mentor", "mentor__user", "mentee", "slot")

    released = 0
    for session in stale:
        if session.payment_ref:
            state = fetch_intasend_status(session.payment_ref)
            # The STK push may have succeeded with the webhook lost — confirm, don't drop
            if state == "COMPLETE":
                _confirm_session_after_payment(session, source="mentorship:release_abandoned_bookings")
                continue
            # Still processing (or IntaSend unreachable) — look again next run, up to 2h
            if state in ("PENDING", "PROCESSING", None) and session.created_at > timezone.now() - timedelta(hours=2):
                continue
        with transaction.atomic():
            if not MentorshipSession.objects.filter(pk=session.pk, status="pending_payment").update(status="cancelled"):
                continue
            TimeSlot.objects.filter(pk=session.slot_id).update(is_booked=False)
            Payment.objects.filter(mentorship_session=session, status="pending").update(
                status="failed", updated_at=timezone.now()
            )
        released += 1

    if released:
        logger.info("release_abandoned_bookings: freed %d slots", released)
    return released


def _push(user, title, body, url):
    try:
        from accounts.views import _send_push_to_user
        _send_push_to_user(user, title=title, body=body, url=url)
    except Exception:
        logger.exception("Mentorship push notification failed for user %s", user.pk)
