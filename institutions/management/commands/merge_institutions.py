"""
Merge duplicate institutions into one row: moves offerings, reviews, promotions,
mentors and analytics logs onto the kept institution, then deletes the duplicate.

When both rows offer the same course, the kept offering's cutoffs win per year and
missing years / programme code are filled from the duplicate.

Usage:
    python manage.py merge_institutions --dry-run
    python manage.py merge_institutions
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from analytics.models import DownloadLog, ViewLog
from courses.models import CourseOffering, Review
from institutions.models import Institution

# (kept institution name, duplicate name) — kept names follow the KUCCPS portal.
MERGES = [
    ('Kaiboi National Polytechnic', 'Kaiboi Technical Training Institute'),
    ('Mama Ngina University College', 'Kenyatta University - Mama Ngina University College'),
    ('Kirinyaga Central Technical and Vocational College', 'Kirinyaga Central Technical Vocational College'),
    ('Laikipia University Tvet Institute', ('public-tvet', 'Laikipia University')),
    ('Tharaka University Tvet Institute', ('public-tvet', 'Tharaka University')),
    ('KMTC Nairobi', 'Nairobi kmtc'),
]

FILL_FIELDS = ('description', 'website', 'email', 'phone', 'logo', 'pdf_file')


def lookup(ref):
    """Name, or (type slug, name) when the name is shared across types."""
    if isinstance(ref, tuple):
        return Institution.objects.filter(institution_type__slug=ref[0], name__iexact=ref[1]).first()
    return Institution.objects.filter(name__iexact=ref).first()


class Command(BaseCommand):
    help = 'Merge duplicate institution rows (see MERGES).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report without saving.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        with transaction.atomic():
            for keep_ref, drop_ref in MERGES:
                keep, drop = lookup(keep_ref), lookup(drop_ref)
                if not keep or not drop or keep.pk == drop.pk:
                    self.stdout.write(f'  skip {drop_ref} -> {keep_ref} (not found / already merged)')
                    continue
                self.merge(keep, drop)
            if dry:
                transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS('[DRY RUN] done' if dry else 'Done'))

    def merge(self, keep, drop):
        moved = combined = 0
        kept_offerings = {o.course_id: o for o in keep.offerings.all()}
        for off in list(drop.offerings.all()):
            existing = kept_offerings.get(off.course_id)
            if existing is None:
                off.institution = keep
                off.save(update_fields=['institution'])
                moved += 1
                continue
            cp = dict(off.cutoff_points or {})
            cp.update({y: v for y, v in (existing.cutoff_points or {}).items() if v is not None})
            existing.cutoff_points = cp or None
            existing.programme_code = existing.programme_code or off.programme_code
            existing.save(update_fields=['cutoff_points', 'programme_code'])
            off.delete()
            combined += 1

        reviewers = set(keep.reviews.values_list('user_id', flat=True))
        reviews = Review.objects.filter(institution=drop)
        reviews.filter(user_id__in=reviewers).delete()
        n_reviews = reviews.update(institution=keep)
        n_promos = drop.promotions.update(institution=keep)
        n_mentors = drop.mentors.update(institution=keep)
        n_logs = (ViewLog.objects.filter(content_type='institution', object_id=drop.pk).update(object_id=keep.pk)
                  + DownloadLog.objects.filter(content_type='institution_pdf', object_id=drop.pk).update(object_id=keep.pk))

        filled = [f for f in FILL_FIELDS if not getattr(keep, f) and getattr(drop, f)]
        for f in filled:
            setattr(keep, f, getattr(drop, f))
        if filled:
            keep.save(update_fields=filled)

        self.stdout.write(
            f'  {drop.name} (#{drop.pk}) -> {keep.name} (#{keep.pk}): '
            f'{moved} offerings moved, {combined} combined, {n_reviews} reviews, '
            f'{n_promos} promotions, {n_mentors} mentors, {n_logs} logs'
            + (f', filled {", ".join(filled)}' if filled else ''))
        drop.delete()
