"""
Management command: fix_category_types

Repoints courses whose category belongs to a different CourseType than the course
itself (e.g. an Artisan course filed under a Craft category). The course type is
the reliable side, so the category is swapped for the same-named one under the
course's own type, created if it doesn't exist yet.

Usage:
    python manage.py fix_category_types --dry-run
    python manage.py fix_category_types
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils.text import slugify

from courses.models import Course, CourseCategory


class Command(BaseCommand):
    help = "Repoint courses whose category belongs to a different course type."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report only; change nothing.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        mismatched = (
            Course.objects.exclude(category__isnull=True)
            .exclude(category__course_type=F("course_type"))
            .select_related("course_type", "category")
        )
        fixed = created = 0
        with transaction.atomic():
            for course in mismatched:
                target = CourseCategory.objects.filter(
                    course_type=course.course_type, name=course.category.name
                ).first()
                if target is None:
                    created += 1
                    if not dry:
                        slug = slugify(course.category.name)
                        if CourseCategory.objects.filter(slug=slug).exists():
                            slug = f"{slug}-{course.course_type.slug}"[:120]
                        target = CourseCategory.objects.create(
                            name=course.category.name, course_type=course.course_type, slug=slug
                        )
                fixed += 1
                if not dry:
                    Course.objects.filter(pk=course.pk).update(category=target)
            if dry:
                transaction.set_rollback(True)
        verb = "Would fix" if dry else "Fixed"
        self.stdout.write(f"{verb} {fixed} course(s); {created} categor{'y' if created == 1 else 'ies'} "
                          f"{'would be ' if dry else ''}created.")
