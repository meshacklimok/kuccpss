import datetime

from django.db import migrations

# Actual KCSE 2025 → 2026 placement cycle, per KNEC / KUCCPS (kuccps.net) announcements and press reports.
# (phase, icon, color, status, date_label, start, end, title, description)
D = datetime.date
EVENTS_2025 = [
    ('Phase 1 — Examinations', 'fa-pen', 'gray', 'done', '21 Oct – Nov 2025', D(2025, 10, 21), D(2025, 11, 21),
     'KCSE 2025 Written Examinations',
     'KNEC began the KCSE on 21 October 2025 with practicals, followed by theory papers from 3 November. About 993,000 candidates sat the exam.'),
    ('Phase 2 — Results', 'fa-star', 'gray', 'done', '9 January 2026', D(2026, 1, 9), D(2026, 1, 9),
     'KCSE 2025 Results Released',
     'Education CS Julius Ogamba released the results in Eldoret. Candidates checked at results.knec.ac.ke with their index number and name (no SMS service this year).'),
    ('Phase 3 — Applications', 'fa-globe', 'gray', 'done', '7 April 2026', D(2026, 4, 7), D(2026, 4, 7),
     'KUCCPS Portal Opens for Applications',
     'Applications opened at students.kuccps.net for the 2025 KCSE class and earlier Form Four leavers: degree (minimum C+), TVET (any grade A–E), and the Open University of Kenya.'),
    ('Phase 3 — Applications', 'fa-list-ol', 'gray', 'done', '7 April – 6 May 2026', D(2026, 4, 7), D(2026, 5, 6),
     'Course Selection Window',
     'Main window to select and rank programme choices. The portal closed at midnight on 6 May 2026 with about 212,500 applicants; over 61,000 who missed it were allowed back in for the revision windows.'),
    ('Phase 4 — Revision Windows', 'fa-edit', 'gray', 'done', '16 – 22 May 2026', D(2026, 5, 16), D(2026, 5, 22),
     '1st Revision Window',
     'Portal reopened for applicants to change choices and for those who missed the first deadline to apply. Applicants who had already paid were not charged again.'),
    ('Phase 4 — Revision Windows', 'fa-redo', 'gray', 'done', '27 May – 1 June 2026', D(2026, 5, 27), D(2026, 6, 1),
     '2nd & Final Degree Revision Window',
     'Final window to revise degree choices, closing on 1 June 2026. TVET applications stayed open until 8 June 2026.'),
    ('Phase 5 — Placement', 'fa-award', 'gray', 'done', '8 July 2026', D(2026, 7, 8), D(2026, 7, 8),
     'Placement Results Announced',
     'CS Julius Ogamba announced placements in Nairobi: 293,869 students placed, including 202,133 to degree programmes and 28,246 to KMTC. About 270,500 candidates scored C+ and above.'),
    ('Phase 5 — Placement', 'fa-exchange-alt', 'gray', 'done', 'July – 14 August 2026', D(2026, 7, 15), D(2026, 8, 14),
     'Inter-Institution Transfer Window',
     'A 30-day window for inter-institution and inter-programme transfers. Transfers needed approval from both institutions and cluster points at or above the programme cutoff.'),
    ('Phase 5 — Placement', 'fa-university', 'gray', 'done', 'Late August – September 2026', D(2026, 8, 24), D(2026, 9, 30),
     'Reporting to Institutions',
     'Degree students joined universities from late August to September 2026; dates varied by institution. TVET placement is continuous. Admission letters and joining instructions were posted on institution websites and are needed for the HEF/HELB funding application.'),
]

EVENTS_2026 = [
    ('Phase 1 — Examinations', 'fa-pen', 'gray', 'Oct – Nov 2026',
     'KCSE 2026 Written Examinations',
     'National examinations administered by KNEC at secondary schools countrywide.'),
    ('Phase 2 — Results', 'fa-star', 'blue', 'Estimated January 2027',
     'KCSE 2026 Results Released',
     'KNEC released the previous two years of results in early January. Expect the same; the official date is announced by the Ministry of Education.'),
    ('Phase 3 — Applications', 'fa-globe', 'green', 'Estimated April 2027',
     'KUCCPS Portal Opens for Applications',
     'In the last cycle the portal opened in early April. Students log in at students.kuccps.net with their KCSE index number.'),
    ('Phase 3 — Applications', 'fa-list-ol', 'green', 'Estimated April – May 2027',
     'Course Selection Window',
     'Main window to select and rank degree, diploma, KMTC, TVET, and TTC programme choices. Submit before the deadline.'),
    ('Phase 4 — Revision Windows', 'fa-edit', 'amber', 'Estimated May – June 2027',
     'Revision Windows',
     'Portal reopens for students to change choices and for late applicants. Last cycle had two windows; KUCCPS sets the dates each year.'),
    ('Phase 5 — Placement', 'fa-award', 'purple', 'Estimated July 2027',
     'Placement Results Announced',
     'KUCCPS publishes placement results. Confirm your placement on the student portal and download admission letters.'),
    ('Phase 5 — Placement', 'fa-university', 'teal', 'Estimated August – September 2027',
     'Reporting to Institutions',
     'Students report to their placed institutions. Bring your admission letter, KCSE certificate, national ID and passport photos.'),
]


def forwards(apps, schema_editor):
    Cycle = apps.get_model('resources', 'CalendarCycle')
    Event = apps.get_model('resources', 'CalendarEvent')

    c25 = Cycle.objects.filter(title='KCSE 2025 Cycle').first()
    if c25:
        c25.events.all().delete()
        c25.portal_year = '2026'
        c25.portal_opens, c25.portal_closes = D(2026, 4, 7), D(2026, 6, 1)
        c25.dates_estimated = False
        c25.placement_label = '8 Jul 2026'
        c25.next_cycle_hint = 'Check students.kuccps.net for 2027 dates'
        c25.save()
        for i, (phase, icon, color, status, label, start, end, title, desc) in enumerate(EVENTS_2025):
            Event.objects.create(cycle=c25, order=i, phase=phase, icon=icon, color=color, status=status,
                                 date_label=label, start_date=start, end_date=end, title=title, description=desc)

    c26 = Cycle.objects.filter(title='KCSE 2026 Cycle').first()
    if c26:
        c26.events.all().delete()
        c26.portal_opens, c26.portal_closes = D(2027, 4, 7), D(2027, 6, 1)
        c26.dates_estimated = True
        c26.placement_label = 'Jul 2027'
        c26.save()
        for i, (phase, icon, color, label, title, desc) in enumerate(EVENTS_2026):
            Event.objects.create(cycle=c26, order=i, phase=phase, icon=icon, color=color, status='tba',
                                 date_label=label, title=title, description=desc)


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0020_successstory_is_pinned"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=migrations.RunPython.noop),
    ]
