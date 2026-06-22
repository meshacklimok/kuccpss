"""
Copies cluster FK from courses.Course → career.Course by matching on course name.
Matching is case-insensitive and strips whitespace.

Usage:
    python manage.py sync_career_clusters          # dry-run (preview only)
    python manage.py sync_career_clusters --apply  # write to DB
"""
from django.core.management.base import BaseCommand
from django.db.models import F
from career.models import Course as CareerCourse
from courses.models import Course as NewCourse


class Command(BaseCommand):
    help = "Sync cluster FK from courses.Course to career.Course by name match"

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually write changes; without this flag the command is a dry-run.',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        # Build lookup: normalised name → (cluster, original name)
        new_courses = NewCourse.objects.filter(cluster__isnull=False).select_related('cluster')
        name_to_cluster = {c.name.strip().lower(): c.cluster for c in new_courses}

        career_courses = CareerCourse.objects.filter(category__name='Degree').select_related('cluster')

        matched = []
        unmatched = []

        for cc in career_courses:
            cluster = name_to_cluster.get(cc.name.strip().lower())
            if cluster:
                matched.append((cc, cluster))
            else:
                unmatched.append(cc)

        self.stdout.write(f"\nMatched:   {len(matched)}")
        self.stdout.write(f"Unmatched: {len(unmatched)}\n")

        if matched:
            self.stdout.write("\n-- MATCHED --")
            for cc, cluster in matched:
                status = "  [would set]" if not apply else "  [set]"
                self.stdout.write(f"{status}  {cc.name!r}  →  Cluster {cluster.number}: {cluster.name}")
                if apply:
                    cc.cluster = cluster
                    cc.save(update_fields=['cluster'])

        if unmatched:
            self.stdout.write("\n-- NO MATCH IN courses.Course --")
            for cc in unmatched:
                self.stdout.write(f"  {cc.name!r}")

        if apply:
            self.stdout.write(self.style.SUCCESS(f"\nDone — {len(matched)} career courses updated."))
        else:
            self.stdout.write(self.style.WARNING("\nDry-run complete. Re-run with --apply to save changes."))
