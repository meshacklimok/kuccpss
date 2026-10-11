import datetime

from django.db import migrations

# (phase, icon, color, date_label, title, description) — all estimates, admin edits them once KUCCPS confirms.
EVENTS_2026 = [
    ('Phase 1 — Examinations', 'fa-pen', 'gray', 'Oct – Nov 2026',
     'KCSE 2026 Written Examinations',
     'National examinations administered by KNEC at secondary schools countrywide.'),
    ('Phase 2 — Results', 'fa-star', 'blue', 'February – March 2027',
     'KCSE 2026 Results Released',
     'KNEC releases national results. Individual results available via SMS (22252) and school portals.'),
    ('Phase 2 — Results', 'fa-file-alt', 'blue', 'March 2027',
     'KUCCPS Cluster Points Released',
     'KUCCPS publishes computed cluster points for each student. Verify yours using the KUCCPS portal or the CareerNext calculator.'),
    ('Phase 3 — Applications', 'fa-globe', 'green', 'Estimated July 2027',
     'KUCCPS Portal Opens for Applications',
     'Students log in at kuccps.net using their index number and KCSE year, then select and rank programme choices.'),
    ('Phase 3 — Applications', 'fa-list-ol', 'green', 'July – August 2027',
     'Course Selection Window (Applications Open)',
     'Main window to select and rank degree, diploma, KMTC, TVET, and TTC programme choices. Submit before the deadline.'),
    ('Phase 4 — Revision Windows', 'fa-edit', 'amber', 'Estimated August 2027',
     'Revision Window',
     'Portal re-opens for students to change programme choices. Dates and number of windows are set by KUCCPS each year.'),
    ('Phase 5 — Placement', 'fa-award', 'purple', 'Estimated September 2027',
     'Placement Results Announced',
     'KUCCPS publishes placement results. Students receive SMS notifications and can view placement on kuccps.net.'),
    ('Phase 5 — Placement', 'fa-university', 'teal', 'Estimated September – October 2027',
     'Reporting to Institutions',
     'Students report to their placed institutions for registration. Bring your placement letter, KCSE certificate, national ID and passport photos.'),
]


def forwards(apps, schema_editor):
    Cycle = apps.get_model('resources', 'CalendarCycle')
    Event = apps.get_model('resources', 'CalendarEvent')

    # Previous cycle: record its real portal dates (these were hard-coded on the dashboard) and retire it.
    Cycle.objects.filter(title='KCSE 2025 Cycle').update(
        portal_year='2026', portal_opens=datetime.date(2026, 7, 3), portal_closes=datetime.date(2026, 8, 21),
        placement_label='Sep 2026', is_current=False, is_completed=True, order=1,
        tab_label='KCSE 2025 Cycle (2026) — Completed',
    )
    Cycle.objects.filter(title='KCSE 2024 Cycle').update(order=2)

    if Cycle.objects.filter(title='KCSE 2026 Cycle').exists():
        return
    cycle = Cycle.objects.create(
        title='KCSE 2026 Cycle', tab_label='KCSE 2026 Cycle (2027)',
        subtitle='For students who sat KCSE in October–November 2026',
        is_current=True, is_completed=False, is_active=True, order=0,
        portal_year='2027', portal_opens=datetime.date(2027, 7, 3), portal_closes=datetime.date(2027, 8, 21),
        dates_estimated=True, placement_label='Sep 2027',
        next_cycle_hint='Check students.kuccps.net for 2028 dates',
    )
    for i, (phase, icon, color, date_label, title, desc) in enumerate(EVENTS_2026):
        Event.objects.create(cycle=cycle, order=i, phase=phase, icon=icon, color=color, status='tba',
                             date_label=date_label, title=title, description=desc)

    SiteSetting = apps.get_model('resources', 'SiteSetting')
    SiteSetting.objects.filter(key='calendar_intro', value__contains='KCSE 2025 placement').update(
        value='All key dates for KCSE 2026 placement — from results day to university reporting. '
              'Bookmark this page so you never miss a deadline.')


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0018_calendar_portal_dates"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=migrations.RunPython.noop),
    ]
