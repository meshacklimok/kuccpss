import datetime

from django.db import migrations

D = datetime.date
PHASE = 'Intakes & Funding — KMTC, TVET, HELB'


def _append(Event, cycle, rows, status_fn):
    base = (cycle.events.order_by('-order').values_list('order', flat=True).first() or 0) + 1
    for i, (icon, color, label, start, end, title, desc) in enumerate(rows):
        Event.objects.create(cycle=cycle, order=base + i, phase=PHASE if i == 0 else '', icon=icon, color=color,
                             date_label=label, start_date=start, end_date=end, title=title, description=desc,
                             **status_fn())


# KCSE 2024 cycle (2025 dates). Status "auto" so they show Done from their dates.
ROWS_2024 = [
    ('fa-heartbeat', 'teal', '24 Jan – 14 Feb 2025', D(2025, 1, 24), D(2025, 2, 14),
     'KMTC March 2025 Intake — Applications',
     'For the first time KUCCPS ran a phased process, opening KMTC applications first. The portal stayed open 21 days, closing 14 February 2025.'),
    ('fa-tools', 'amber', '24 Jan – 14 Feb 2025', D(2025, 1, 24), D(2025, 2, 14),
     'TVET May 2025 Intake — Applications',
     'TVET applications for the May intake opened alongside KMTC, with the same 14 February 2025 deadline.'),
    ('fa-heartbeat', 'teal', '23 Jun – 7 Jul 2025', D(2025, 6, 23), D(2025, 7, 7),
     'KMTC September 2025 Intake — Applications',
     'KUCCPS opened pre-service KMTC applications for the September intake.'),
    ('fa-tools', 'amber', '8 – 28 Aug 2025', D(2025, 8, 8), D(2025, 8, 28),
     'TVET September 2025 Intake — Applications',
     'TVET applications for the September intake ran from 8 August, first to 22 August and then extended to 28 August 2025.'),
]

# KCSE 2025 cycle (2026 dates).
ROWS_2025 = [
    ('fa-tools', 'amber', 'Up to ~5 Aug 2026', D(2026, 7, 20), D(2026, 8, 5),
     'TVET September 2026 Intake — Applications',
     'KUCCPS opened TVET applications for the September intake alongside KMTC. A deadline of about 5 August 2026 was reported; check the portal for later reopenings.'),
]

# KCSE 2026 cycle (2027 dates): estimates.
ROWS_2026 = [
    ('fa-tools', 'amber', 'Estimated July – August 2027',
     'TVET September 2027 Intake — Applications',
     'Last cycle TVET September-intake applications ran through July and early August. TVET placement is continuous.'),
]


def forwards(apps, schema_editor):
    Cycle = apps.get_model('resources', 'CalendarCycle')
    Event = apps.get_model('resources', 'CalendarEvent')

    c = Cycle.objects.filter(title='KCSE 2024 Cycle').first()
    if c and not c.events.filter(title__startswith='KMTC March').exists():
        _append(Event, c, ROWS_2024, lambda: dict(status='auto'))

    c = Cycle.objects.filter(title='KCSE 2025 Cycle').first()
    if c and not c.events.filter(title__startswith='TVET September').exists():
        base = (c.events.order_by('-order').values_list('order', flat=True).first() or 0) + 1
        for i, (icon, color, label, start, end, title, desc) in enumerate(ROWS_2025):
            Event.objects.create(cycle=c, order=base + i, icon=icon, color=color, date_label=label,
                                 start_date=start, end_date=end, title=title, description=desc, status='auto')

    c = Cycle.objects.filter(title='KCSE 2026 Cycle').first()
    if c and not c.events.filter(title__startswith='TVET September').exists():
        base = (c.events.order_by('-order').values_list('order', flat=True).first() or 0) + 1
        for i, (icon, color, label, title, desc) in enumerate(ROWS_2026):
            Event.objects.create(cycle=c, order=base + i, icon=icon, color=color, date_label=label,
                                 title=title, description=desc, status='tba')


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0023_current_cycle_full_intakes"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=migrations.RunPython.noop),
    ]
