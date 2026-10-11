"""Dashboard KUCCPS portal countdown, driven by the current CalendarCycle (admin-editable)."""
from django.utils import timezone

from .models import CalendarCycle


def _fmt(d):
    return f"{d.day} {d:%b %Y}"


def get_portal_timeline():
    """Return the template context for the dashboard "KUCCPS Portal" card."""
    cycle = (
        CalendarCycle.objects.filter(is_active=True, portal_opens__isnull=False, portal_closes__isnull=False)
        .order_by('-is_current', 'order', '-id')
        .first()
    )
    if cycle is None:
        return {
            'timeline_phase': 'unset', 'timeline_days': 0, 'timeline_year': '',
            'timeline_label': '', 'timeline_date': 'Dates not yet announced',
            'timeline_open_text': 'TBA', 'timeline_close_text': 'TBA', 'timeline_placement_text': 'TBA',
        }

    today = timezone.localdate()
    est = 'Est. ' if cycle.dates_estimated else ''
    open_text = f"{est}{_fmt(cycle.portal_opens)}"
    close_text = f"{est}{_fmt(cycle.portal_closes)}"
    days_to_open = (cycle.portal_opens - today).days
    days_to_close = (cycle.portal_closes - today).days
    year = cycle.portal_year or str(cycle.portal_opens.year)

    if days_to_open > 0:
        phase, days, label, date = 'before_open', days_to_open, 'Days until portal opens', open_text
    elif days_to_close >= 0:
        phase, days, label, date = 'open', days_to_close, 'Days left to apply', f"Closes {close_text}"
    else:
        phase, days, label = 'closed', 0, f"Portal closed for {year}"
        date = cycle.next_cycle_hint or 'Check students.kuccps.net for the next cycle dates'

    return {
        'timeline_phase': phase, 'timeline_days': days, 'timeline_label': label,
        'timeline_date': date, 'timeline_year': year,
        'timeline_open_text': open_text, 'timeline_close_text': close_text,
        'timeline_placement_text': f"{est}{cycle.placement_label}" if cycle.placement_label else 'TBA',
    }
