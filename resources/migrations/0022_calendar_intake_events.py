import datetime

from django.db import migrations

D = datetime.date
PHASE = 'Intakes & Funding — KMTC, TVET, HELB'

# 2025 KCSE cycle (2026 dates), status "auto" so they flip Done/Open/Upcoming from the dates; admin can override.
# (icon, color, date_label, start, end, title, description)
EVENTS_2025 = [
    ('fa-heartbeat', 'teal', '7 – 27 Jan 2026', D(2026, 1, 7), D(2026, 1, 27),
     'KMTC March 2026 Intake — Applications',
     'KUCCPS opened KMTC certificate and diploma applications for the March intake to 2025 KCSE candidates and earlier Form Four leavers.'),
    ('fa-heartbeat', 'teal', 'Feb – 13 Mar 2026', D(2026, 2, 1), D(2026, 3, 13),
     'KMTC March 2026 Intake — Portal Reopened',
     'The KMTC portal was reopened for new applicants and those unsuccessful in the first round, with a 13 March 2026 deadline. A further short window was reported for 28 March – 3 April.'),
    ('fa-tools', 'amber', '9 – 18 Mar 2026', D(2026, 3, 9), D(2026, 3, 18),
     'TVET May 2026 Intake — Applications',
     'KUCCPS opened TVET applications for the May intake with a 18 March 2026 deadline. Any KCSE grade can apply: C- and above for diploma (Level 6), D for craft certificate (Level 5), E for artisan (Level 4).'),
    ('fa-door-open', 'amber', 'From May 2026', D(2026, 5, 1), D(2026, 5, 31),
     'TVET May 2026 Intake — Reporting',
     'TVET placement is continuous, so placed students could report to their colleges from May 2026.'),
    ('fa-wallet', 'green', 'From 10 July 2026', D(2026, 7, 10), D(2026, 9, 30),
     'HEF / HELB First-Time Loan & Scholarship Applications',
     'First-year degree and TVET students apply at hef.co.ke with an admission letter, ideally a month before reporting. A 31 August deadline was reported but not officially confirmed, so check HELB.'),
    ('fa-heartbeat', 'teal', '~24 Jul – 11 Aug 2026', D(2026, 7, 24), D(2026, 8, 11),
     'KMTC September 2026 Intake — Applications',
     'KUCCPS opened pre-service KMTC applications for the September intake, closing 11 August 2026. In-service and upgrading programmes apply through the KMTC portal.'),
    ('fa-heartbeat', 'teal', 'From ~31 Aug 2026', D(2026, 8, 31), D(2026, 9, 30),
     'KMTC September 2026 Intake — Vacancies Reopened',
     'KUCCPS reopened applications for KMTC courses that still had vacancies. Closing date not confirmed — check the portal.'),
    ('fa-hand-holding-usd', 'green', '21 Aug – 30 Sep 2026', D(2026, 8, 21), D(2026, 9, 30),
     'HELB Loans for KMTC Certificate & Diploma Students',
     'A separate HELB window for students placed in KMTC certificate and diploma programmes.'),
]

# 2026 KCSE cycle (2027 dates): estimates only, TBA until KUCCPS announces.
EVENTS_2026 = [
    ('fa-heartbeat', 'teal', 'Estimated January 2027',
     'KMTC March 2027 Intake — Applications',
     'In the last cycle KUCCPS opened KMTC March-intake applications in early January, then reopened the portal in February–March.'),
    ('fa-tools', 'amber', 'Estimated March 2027',
     'TVET May 2027 Intake — Applications',
     'Last cycle TVET applications for the May intake opened in early March and closed on 18 March. TVET placement is continuous.'),
    ('fa-wallet', 'green', 'Estimated July 2027',
     'HEF / HELB First-Time Loan & Scholarship Applications',
     'Opens after placement results. You need your admission letter. Apply at hef.co.ke.'),
    ('fa-heartbeat', 'teal', 'Estimated July – August 2027',
     'KMTC September 2027 Intake — Applications',
     'Opens after university placement is complete. Pre-service programmes apply through the KUCCPS portal.'),
]


def forwards(apps, schema_editor):
    Cycle = apps.get_model('resources', 'CalendarCycle')
    Event = apps.get_model('resources', 'CalendarEvent')
    for title, rows, is_2025 in (('KCSE 2025 Cycle', EVENTS_2025, True), ('KCSE 2026 Cycle', EVENTS_2026, False)):
        cycle = Cycle.objects.filter(title=title).first()
        if not cycle or cycle.events.filter(phase=PHASE).exists():
            continue
        base = (cycle.events.order_by('-order').values_list('order', flat=True).first() or 0) + 1
        for i, row in enumerate(rows):
            if is_2025:
                icon, color, label, start, end, name, desc = row
                extra = dict(status='auto', start_date=start, end_date=end)
            else:
                icon, color, label, name, desc = row
                extra = dict(status='tba')
            Event.objects.create(cycle=cycle, order=base + i, phase=PHASE if i == 0 else '', icon=icon,
                                 color=color, date_label=label, title=name, description=desc, **extra)


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0021_kcse_2025_cycle_actual_dates"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=migrations.RunPython.noop),
    ]
