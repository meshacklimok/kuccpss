from django.db import migrations

# Mirrors the content that was previously hard-coded in templates/resources/calendar.html.
# Each event: (phase, icon, color, status, date_label, title, description)
CYCLES = [
    {
        'title': 'KCSE 2025 Cycle', 'tab_label': 'KCSE 2025 Cycle (2026)',
        'subtitle': 'For students who sat KCSE in October–November 2025',
        'is_current': True, 'is_completed': False, 'order': 0,
        'events': [
            ('Phase 1 — Examinations', 'fa-pen', 'gray', 'done', 'Oct – Nov 2025',
             'KCSE 2025 Written Examinations',
             'National examinations administered by KNEC at secondary schools countrywide.'),
            ('Phase 2 — Results', 'fa-star', 'blue', 'expected', 'February – March 2026',
             'KCSE 2025 Results Released',
             'KNEC releases national results. Individual results available via SMS (22252) and school portals. Mean grade and subject scores published.'),
            ('Phase 2 — Results', 'fa-file-alt', 'blue', 'expected', 'March 2026',
             'KUCCPS Cluster Points Released',
             'KUCCPS publishes computed cluster points for each student. Verify yours using the KUCCPS portal or CareerNext calculator.'),
            ('Phase 3 — Applications', 'fa-globe', 'green', 'upcoming', 'April 2026',
             'KUCCPS Portal Opens for Applications',
             'Students log in at kuccps.net using their index number and KCSE year. Select up to 6 degree programme choices and 3 TVET/KMTC choices.'),
            ('Phase 3 — Applications', 'fa-list-ol', 'green', 'upcoming', 'April – May 2026',
             'Course Selection Window (Applications Open)',
             'Main window to select and rank degree, diploma, KMTC, TVET, and TTC programme choices. Submit before the deadline — late submissions are not accepted.'),
            ('Phase 4 — Revision Windows', 'fa-edit', 'amber', 'tba', 'May – June 2026',
             '1st Revision Window',
             'Portal re-opens for students to change programme choices. Highly competitive — only one revision per window allowed. New cutoffs may apply based on first-round demand.'),
            ('Phase 4 — Revision Windows', 'fa-redo', 'amber', 'tba', 'June – July 2026',
             '2nd Revision Window',
             'Final opportunity to update programme choices before placement. Changes in this window are binding — choose carefully.'),
            ('Phase 5 — Placement', 'fa-award', 'purple', 'tba', 'August 2026',
             'Placement Results Announced',
             'KUCCPS publishes placement results. Students receive SMS notifications. View your placement on kuccps.net using index number.'),
            ('Phase 5 — Placement', 'fa-university', 'teal', 'tba', 'August – September 2026',
             'Reporting to Institutions',
             'Students report to their placed universities, KMTCs, TVETs, or TTCs for registration. Bring: placement letter, KCSE certificate, national ID, passport photos, and any required fees.'),
        ],
    },
    {
        'title': 'KCSE 2024 Cycle', 'tab_label': 'KCSE 2024 Cycle (2025) — Completed',
        'subtitle': 'For students who sat KCSE in October–November 2024',
        'is_current': False, 'is_completed': True, 'order': 1,
        'events': [
            ('', 'fa-check', 'gray', 'done', 'Oct – Nov 2024', 'KCSE 2024 Examinations',
             'National written examinations conducted by KNEC.'),
            ('', 'fa-check', 'gray', 'done', 'Feb – Mar 2025', 'KCSE 2024 Results Released',
             'Results published by KNEC. Mean grade, subject grades, and cluster points made available.'),
            ('', 'fa-check', 'gray', 'done', 'April – May 2025', 'Applications & Course Selection',
             'KUCCPS portal opened; students submitted degree, TVET, and KMTC programme choices.'),
            ('', 'fa-check', 'gray', 'done', 'May – June 2025', '1st Revision Window',
             'Students updated programme choices in the first revision round.'),
            ('', 'fa-check', 'gray', 'done', 'June – July 2025', '2nd Revision Window',
             'Final programme choice revisions before placement computation.'),
            ('', 'fa-check', 'gray', 'done', 'August 2025', 'Placement Results',
             'KUCCPS announced placements. Students notified via SMS and kuccps.net portal.'),
            ('', 'fa-check', 'gray', 'done', 'Aug – Sep 2025', 'Reporting to Institutions',
             'Placed students reported to their institutions for registration and orientation.'),
        ],
    },
]

SETTINGS = [
    ('calendar_intro', 'Calendar Page Intro', 'textarea',
     'All key dates for KCSE 2025 placement — from results day to university reporting. '
     'Bookmark this page so you never miss a deadline.',
     'Intro text in the KUCCPS Calendar page hero.'),
    ('calendar_notice', 'Calendar Page Notice', 'textarea',
     'Dates are estimates based on historical KUCCPS patterns. KNEC and KUCCPS set official dates each year. '
     'Always verify on the KUCCPS portal (kuccps.net) and KNEC website before acting.',
     'Blue notice box above the timeline. Leave blank to hide it.'),
]


def seed(apps, schema_editor):
    CalendarCycle = apps.get_model('resources', 'CalendarCycle')
    CalendarEvent = apps.get_model('resources', 'CalendarEvent')
    SiteSetting = apps.get_model('resources', 'SiteSetting')

    if not CalendarCycle.objects.exists():
        for c in CYCLES:
            data = {k: v for k, v in c.items() if k != 'events'}
            cycle = CalendarCycle.objects.create(**data)
            for i, (phase, icon, color, status, date_label, title, desc) in enumerate(c['events']):
                CalendarEvent.objects.create(
                    cycle=cycle, order=i, phase=phase, icon=icon, color=color, status=status,
                    date_label=date_label, title=title, description=desc,
                )

    for key, label, stype, value, note in SETTINGS:
        SiteSetting.objects.get_or_create(key=key, defaults={
            'label': label, 'value': value, 'setting_type': stype,
            'group': 'calendar', 'help_note': note,
        })


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0013_calendar"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=migrations.RunPython.noop),
    ]
