"""
Management command: seed_tvet_all_offerings

Creates CourseOffering rows linking TVET courses to TVET institutions for
the six course types that currently have zero institution links:

  Level 5 Certificate    → all Public TVET institutions
  Level 4 Artisan        → all Public TVET institutions
  Level 3 Craft          → all Public TVET institutions
  Short Course           → all Public + Private TVET institutions (open entry)
  Trade Test             → all Public TVET institutions
  Proficiency            → all Public TVET institutions
  Professional           → skipped (KASNEB/IHRM national exams, not tied to a campus)

The TVET Diploma (Level 6) is also skipped — it already has 3,273
KUCCPS-sourced offerings from seed_tvet.py.

Usage:
    conda run python manage.py seed_tvet_all_offerings
    conda run python manage.py seed_tvet_all_offerings --clear
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, CourseOffering, CourseType
from institutions.models import Institution, InstitutionType


PLAN = [
    # (course_type_name, use_private_too)
    ('TVET Certificate (Level 5)',        False),
    ('TVET Artisan Certificate (Level 4)', False),
    ('TVET Craft Certificate (Level 3)',   False),
    ('TVET Short Course',                  True),   # open entry — public + private
    ('TVET Trade Test',                    False),
    ('TVET Proficiency',                   False),
    # TVET Professional — national body qualifications, no campus link
]

SKIP_TYPES = {'TVET Diploma (Level 6)', 'TVET Professional'}


class Command(BaseCommand):
    help = 'Seed CourseOfferings for TVET Levels 3–5, Short Course, Trade Test, Proficiency.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete existing offerings for these types before re-seeding.'
        )

    def handle(self, *args, **options):
        self.stdout.write('-' * 60)
        self.stdout.write('seed_tvet_all_offerings — starting')
        self.stdout.write('-' * 60)

        pub_type  = InstitutionType.objects.filter(name='Public TVET').first()
        priv_type = InstitutionType.objects.filter(name='Private TVET').first()

        if not pub_type:
            self.stdout.write(self.style.ERROR(
                'InstitutionType "Public TVET" not found. Run seed_tvet first.'
            ))
            return

        pub_institutions  = list(Institution.objects.filter(institution_type=pub_type))
        priv_institutions = list(Institution.objects.filter(institution_type=priv_type)) if priv_type else []

        self.stdout.write(
            f'  Public TVET institutions : {len(pub_institutions)}'
        )
        self.stdout.write(
            f'  Private TVET institutions: {len(priv_institutions)}'
        )

        grand_total = 0

        for type_name, include_private in PLAN:
            ct = CourseType.objects.filter(name=type_name).first()
            if not ct:
                self.stdout.write(self.style.WARNING(
                    f'  CourseType "{type_name}" not found — skipping'
                ))
                continue

            courses = list(Course.objects.filter(course_type=ct))
            if not courses:
                self.stdout.write(self.style.WARNING(
                    f'  {type_name}: no courses found — skipping'
                ))
                continue

            institutions = pub_institutions[:]
            if include_private:
                institutions += priv_institutions

            if options['clear']:
                n = CourseOffering.objects.filter(course__course_type=ct).delete()[0]
                self.stdout.write(f'  Cleared {n} existing offerings for {type_name}')

            created = self._bulk_seed(courses, institutions)
            grand_total += created
            self.stdout.write(self.style.SUCCESS(
                f'  {type_name}: {len(courses)} courses × {len(institutions)} institutions'
                f' → {created} new offerings'
            ))

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. {grand_total} CourseOffering rows created.'
        ))

    def _bulk_seed(self, courses, institutions):
        existing = set(
            CourseOffering.objects.filter(
                course__in=courses
            ).values_list('course_id', 'institution_id')
        )

        to_create = []
        for course in courses:
            for inst in institutions:
                if (course.pk, inst.pk) not in existing:
                    to_create.append(CourseOffering(course=course, institution=inst))

        if to_create:
            with transaction.atomic():
                CourseOffering.objects.bulk_create(to_create, batch_size=500, ignore_conflicts=True)

        return len(to_create)
