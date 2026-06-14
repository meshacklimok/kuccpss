"""
Management command: fix_tvet_flat_types

Short Course, Trade Test, Proficiency, and Professional are national-level
qualifications that do not need category drill-down in the browse UI.

This command:
  1. Sets category=None on every Course under the four flat types.
  2. Deletes all CourseCategory rows for those types.

After running this, course_type_detail shows a flat alphabetical list for
these four types — no extra category click required.

Usage:
    conda run python manage.py fix_tvet_flat_types
    conda run python manage.py fix_tvet_flat_types --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, CourseCategory, CourseType


FLAT_TYPE_NAMES = [
    'TVET Short Course',
    'TVET Trade Test',
    'TVET Proficiency',
    'TVET Professional',
]


class Command(BaseCommand):
    help = 'Remove course categories from flat TVET types.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry = options['dry_run']
        self.stdout.write('-' * 60)
        self.stdout.write('fix_tvet_flat_types' + (' [DRY RUN]' if dry else ''))
        self.stdout.write('-' * 60)

        for type_name in FLAT_TYPE_NAMES:
            ct = CourseType.objects.filter(name=type_name).first()
            if not ct:
                self.stdout.write(self.style.WARNING(f'  "{type_name}" not found — skipping'))
                continue

            linked = Course.objects.filter(course_type=ct).exclude(category=None).count()
            cats   = CourseCategory.objects.filter(course_type=ct).count()

            if dry:
                self.stdout.write(f'  {type_name}: {cats} categories, {linked} linked courses')
                continue

            with transaction.atomic():
                Course.objects.filter(course_type=ct).update(category=None)
                deleted, _ = CourseCategory.objects.filter(course_type=ct).delete()

            self.stdout.write(self.style.SUCCESS(
                f'  {type_name}: removed {deleted} categories, un-linked {linked} courses'
            ))

        if not dry:
            self.stdout.write(self.style.SUCCESS('\nDone.'))
        else:
            self.stdout.write('\n[dry-run] no changes made')
