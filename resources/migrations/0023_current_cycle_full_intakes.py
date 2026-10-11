from django.db import migrations

PHASE = 'Intakes & Funding — KMTC, TVET, HELB'

TRANSFER = ('Phase 5 — Placement', 'fa-exchange-alt', 'purple', 'Estimated July – August 2027',
            'Inter-Institution Transfer Window',
            'Last cycle KUCCPS opened a 30-day window for inter-institution and inter-programme transfers. '
            'Both institutions must approve, and your cluster points must meet the programme cutoff.')

# (icon, color, date_label, title, description) — estimates for the current (KCSE 2026) cycle.
INTAKES = [
    ('fa-heartbeat', 'teal', 'Estimated January 2027', 'KMTC March 2027 Intake — Applications',
     'In the last cycle KUCCPS opened KMTC March-intake applications in early January, with a deadline in late January.'),
    ('fa-heartbeat', 'teal', 'Estimated February – March 2027', 'KMTC March 2027 Intake — Portal Reopened',
     'Last cycle the KMTC portal reopened for new applicants and those unsuccessful in round one, closing mid-March.'),
    ('fa-tools', 'amber', 'Estimated March 2027', 'TVET May 2027 Intake — Applications',
     'Last cycle TVET applications for the May intake opened in early March and closed on 18 March. Any KCSE grade can apply.'),
    ('fa-door-open', 'amber', 'Estimated from May 2027', 'TVET May 2027 Intake — Reporting',
     'TVET placement is continuous, so placed students can report to their colleges from May.'),
    ('fa-wallet', 'green', 'Estimated July 2027', 'HEF / HELB First-Time Loan & Scholarship Applications',
     'Opens after placement results. You need your admission letter. Apply at hef.co.ke at least a month before reporting.'),
    ('fa-heartbeat', 'teal', 'Estimated July – August 2027', 'KMTC September 2027 Intake — Applications',
     'Opens after university placement is complete. Pre-service programmes apply through the KUCCPS portal.'),
    ('fa-heartbeat', 'teal', 'Estimated late August 2027', 'KMTC September 2027 Intake — Vacancies Reopened',
     'Last cycle KUCCPS reopened applications for KMTC courses that still had vacancies.'),
    ('fa-hand-holding-usd', 'green', 'Estimated August – September 2027', 'HELB Loans for KMTC Certificate & Diploma Students',
     'A separate HELB window for students placed in KMTC certificate and diploma programmes.'),
]


def forwards(apps, schema_editor):
    Cycle = apps.get_model('resources', 'CalendarCycle')
    Event = apps.get_model('resources', 'CalendarEvent')
    cycle = Cycle.objects.filter(title='KCSE 2026 Cycle').first()
    if not cycle:
        return
    # Rebuild the intake group (and add the transfer window) in date order; core phases are kept as-is.
    keep = [e for e in cycle.events.order_by('order', 'id')
            if not (e.phase == PHASE or ('Intake' in e.title or 'HEF' in e.title or 'HELB' in e.title))]
    cycle.events.exclude(pk__in=[e.pk for e in keep]).delete()
    order = 0
    for e in keep:
        e.order = order
        e.save(update_fields=['order'])
        order += 1
        if e.title == 'Placement Results Announced':
            phase, icon, color, label, title, desc = TRANSFER
            Event.objects.create(cycle=cycle, order=order, phase='Phase 5 — Placement', icon=icon, color=color,
                                 status='tba', date_label=label, title=title, description=desc)
            order += 1
    for i, (icon, color, label, title, desc) in enumerate(INTAKES):
        Event.objects.create(cycle=cycle, order=order, phase=PHASE if i == 0 else '', icon=icon, color=color,
                             status='tba', date_label=label, title=title, description=desc)
        order += 1


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0022_calendar_intake_events"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=migrations.RunPython.noop),
    ]
