"""
Helpers for generating Google Calendar links and iCal (.ics) files
for mentorship session reminders.

No external libraries needed — iCal format is plain text.
"""
from datetime import datetime, timedelta, timezone as dt_tz
from urllib.parse import quote

from django.utils import timezone


def _slot_utc_datetimes(session):
    """Return (start_dt_utc, end_dt_utc) for the session's slot."""
    slot = session.slot
    naive = datetime.combine(slot.date, slot.start_time)
    # Localise to Africa/Nairobi then convert to UTC
    local_dt = timezone.make_aware(naive)          # uses Django's TIME_ZONE setting
    start_utc = timezone.localtime(local_dt, timezone=dt_tz.utc)
    end_utc = start_utc + timedelta(minutes=15)
    return start_utc, end_utc


def _fmt(dt):
    """Format datetime as iCal UTC stamp: 20260620T060000Z"""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def google_calendar_url(session):
    """
    Returns a Google Calendar 'add event' URL pre-filled with session details.
    Both mentor and mentee can open this link to add the event to their calendar.
    """
    start_utc, end_utc = _slot_utc_datetimes(session)
    mentor_name = session.mentor.display_name
    mentee_name = session.mentee_display

    title = f"CareerNext Mentorship — {mentor_name}"
    details = (
        f"15-minute mentorship session.\n\n"
        f"Mentor : {mentor_name}\n"
        f"Student: {mentee_name}\n"
        f"Topic  : {session.mentee_question}\n\n"
        f"Coordinate with your mentor via WhatsApp ({session.mentor.whatsapp}) "
        f"to agree on how you'll connect (Google Meet, WhatsApp Video, or call).\n\n"
        f"Session details: https://www.careernext.co.ke/mentorship/session/{session.token}/"
    )

    params = (
        f"action=TEMPLATE"
        f"&text={quote(title)}"
        f"&dates={_fmt(start_utc)}/{_fmt(end_utc)}"
        f"&details={quote(details)}"
        f"&location={quote('Coordinate via WhatsApp')}"
    )
    return f"https://calendar.google.com/calendar/render?{params}"


def generate_ics(session):
    """
    Returns iCal (.ics) file content as a string for a confirmed session.
    Includes two VALARM reminders: 1 hour before and 15 minutes before.
    Compatible with Google Calendar, Outlook, and Apple Calendar.
    """
    start_utc, end_utc = _slot_utc_datetimes(session)
    now_utc = timezone.now().astimezone(dt_tz.utc)
    mentor_name = session.mentor.display_name
    mentee_name = session.mentee_display
    uid = f"{session.token}@careernext.co.ke"

    summary = f"CareerNext Mentorship — {mentor_name}"
    description = (
        f"15-minute mentorship session.\\n"
        f"Mentor: {mentor_name} | WhatsApp: {session.mentor.whatsapp}\\n"
        f"Topic: {session.mentee_question}\\n"
        f"Coordinate via WhatsApp to agree on how you'll connect (Google Meet, WhatsApp Video, or call).\\n"
        f"Session link: https://www.careernext.co.ke/mentorship/session/{session.token}/"
    )

    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//CareerNext//Mentorship//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:REQUEST\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{_fmt(now_utc)}\r\n"
        f"DTSTART:{_fmt(start_utc)}\r\n"
        f"DTEND:{_fmt(end_utc)}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{description}\r\n"
        "LOCATION:Coordinate via WhatsApp\r\n"
        "STATUS:CONFIRMED\r\n"
        # 1-hour reminder
        "BEGIN:VALARM\r\n"
        "TRIGGER:-PT1H\r\n"
        "ACTION:DISPLAY\r\n"
        "DESCRIPTION:Your mentorship session starts in 1 hour\r\n"
        "END:VALARM\r\n"
        # 15-minute reminder
        "BEGIN:VALARM\r\n"
        "TRIGGER:-PT15M\r\n"
        "ACTION:DISPLAY\r\n"
        "DESCRIPTION:Your mentorship session starts in 15 minutes\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    return ics
