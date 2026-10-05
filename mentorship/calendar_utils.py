"""
Helpers for generating Google Calendar links and iCal (.ics) files
for mentorship session reminders.

No external libraries needed — iCal format is plain text.

Reminder caveat: Apple Calendar and Outlook honour the VALARMs below, but Google
Calendar ignores alarms in imported/invited .ics files (and its "add event" URL has
no reminder parameter) — Google users get their own default notifications. The
1-hour email reminder in tasks.py covers everyone regardless.
"""
from datetime import datetime, timedelta, timezone as dt_tz
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone

SITE = "https://www.careernext.co.ke"


def _slot_utc_datetimes(session):
    """Return (start_dt_utc, end_dt_utc) for the session's slot."""
    slot = session.slot
    naive = datetime.combine(slot.date, slot.start_time)
    # Localise to Africa/Nairobi then convert to UTC
    local_dt = timezone.make_aware(naive)          # uses Django's TIME_ZONE setting
    start_utc = timezone.localtime(local_dt, timezone=dt_tz.utc)
    end_utc = start_utc + timedelta(minutes=session.duration_minutes)
    return start_utc, end_utc


def _fmt(dt):
    """Format datetime as iCal UTC stamp: 20260620T060000Z"""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _escape(text):
    """Escape a TEXT value (RFC 5545 §3.3.11) so user input can't add properties."""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line):
    """Fold a content line at 75 octets (RFC 5545 §3.1), never splitting a UTF-8 char."""
    out, current, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        limit = 75 if not out else 74  # continuation lines start with a space
        if size + n > limit:
            out.append(current)
            current, size = "", 0
        current += ch
        size += n
    out.append(current)
    return "\r\n ".join(out)


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
        f"{session.duration_minutes}-minute mentorship session.\n\n"
        f"Mentor : {mentor_name}\n"
        f"Student: {mentee_name}\n"
        f"Topic  : {session.mentee_question}\n\n"
        f"Coordinate with your mentor via WhatsApp ({session.mentor.whatsapp}) "
        f"to agree on how you'll connect (Google Meet, WhatsApp Video, or call).\n\n"
        f"Session details: {SITE}/mentorship/session/{session.token}/"
    )

    params = (
        f"action=TEMPLATE"
        f"&text={quote(title)}"
        f"&dates={_fmt(start_utc)}/{_fmt(end_utc)}"
        f"&ctz={quote(settings.TIME_ZONE)}"
        f"&details={quote(details)}"
        f"&location={quote('Coordinate via WhatsApp')}"
    )
    return f"https://calendar.google.com/calendar/render?{params}"


def generate_ics(session, method="PUBLISH", attendee_email=None):
    """
    Returns iCal (.ics) file content as a string for a session.

    method:
      PUBLISH — plain calendar file (the download button).
      REQUEST — email invite; Gmail/Outlook show an "add to calendar" card and
                auto-add it. Pass attendee_email (the recipient).
      CANCEL  — removes the event previously sent with the same UID.

    Includes two VALARM reminders: 1 hour and 15 minutes before.
    """
    start_utc, end_utc = _slot_utc_datetimes(session)
    now_utc = timezone.now().astimezone(dt_tz.utc)
    mentor_name = session.mentor.display_name
    cancelled = method == "CANCEL"

    summary = f"CareerNext Mentorship — {mentor_name}"
    if cancelled:
        summary = f"CANCELLED: {summary}"
    description = (
        f"{session.duration_minutes}-minute mentorship session.\n"
        f"Mentor: {mentor_name} | WhatsApp: {session.mentor.whatsapp}\n"
        f"Student: {session.mentee_display}\n"
        f"Topic: {session.mentee_question}\n"
        f"Coordinate via WhatsApp to agree on how you'll connect (Google Meet, WhatsApp Video, or call).\n"
        f"Session link: {SITE}/mentorship/session/{session.token}/"
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CareerNext//Mentorship//EN",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method}",
        "BEGIN:VEVENT",
        f"UID:{session.token}@careernext.co.ke",
        # Bumped on cancel so calendars treat it as an update to the same event
        f"SEQUENCE:{1 if cancelled else 0}",
        f"DTSTAMP:{_fmt(now_utc)}",
        f"DTSTART:{_fmt(start_utc)}",
        f"DTEND:{_fmt(end_utc)}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        "LOCATION:Coordinate via WhatsApp",
        f"URL:{SITE}/mentorship/session/{session.token}/",
        f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}",
    ]
    if method in ("REQUEST", "CANCEL"):
        # iTIP (RFC 5546) requires an organizer and attendee for invites/cancels
        organizer = settings.DEFAULT_FROM_EMAIL.rsplit("<", 1)[-1].rstrip(">").strip()
        lines.append(f"ORGANIZER;CN=CareerNext:mailto:{organizer}")
        if attendee_email:
            lines.append(f"ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;RSVP=FALSE:mailto:{attendee_email}")
    if not cancelled:
        lines += [
            "BEGIN:VALARM",
            "TRIGGER:-PT1H",
            "ACTION:DISPLAY",
            "DESCRIPTION:Your mentorship session starts in 1 hour",
            "END:VALARM",
            "BEGIN:VALARM",
            "TRIGGER:-PT15M",
            "ACTION:DISPLAY",
            "DESCRIPTION:Your mentorship session starts in 15 minutes",
            "END:VALARM",
        ]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "".join(_fold(line) + "\r\n" for line in lines)
