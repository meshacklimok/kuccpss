"""
Create KUCCPS clusters from a cluster-programme CSV and link Course records.

Usage:
    # Step 1 — generate the CSV from the PDF first:
    python scripts/extract_cluster_programmes.py data/DEGREE_CLUSTER_DOCUMENT_2025.pdf data/clusters_map.csv

    # Step 2 — seed clusters and link courses:
    python manage.py link_clusters data/clusters_map.csv

What this does:
    - Creates a Cluster record for each unique cluster code (e.g. 1A, 2A, 3B)
    - For each programme name in the CSV, finds the matching Course(s) by name
      (case-insensitive exact match first, then partial match as fallback)
    - Sets Course.cluster to the matched cluster
    - Reports unmatched programmes at the end
"""

import csv
from django.core.management.base import BaseCommand
from clusters.models import Cluster
from courses.models import Course


CLUSTER_LABELS = {
    '1':  'Law, Commerce & Business',
    '2':  'Business, Management & Information',
    '3':  'Communication, Media & Social Sciences',
    '4':  'Geospatial & Earth Sciences',
    '5':  'Engineering & Applied Sciences',
    '6':  'Architecture, Real Estate & ICT',
    '7':  'Computer Science & IT',
    '8':  'Agricultural Economics',
    '9':  'Pure Sciences',
    '10': 'Economics, Finance & Actuarial',
    '11': 'Fashion & Textile',
    '12': 'Sports & Health Promotion',
    '13': 'Medicine, Health & Allied',
    '14': 'History & Archaeology',
    '15': 'Agriculture, Veterinary & Environment',
    '16': 'Geography & Land Management',
    '17': 'French & German',
    '18': 'Music',
    '19': 'Education',
    '20': 'Religious Studies & Theology',
}


def cluster_name(code):
    """Return a human-readable name for a sub-cluster code like '5A'."""
    num = ''.join(c for c in code if c.isdigit())
    suffix = ''.join(c for c in code if c.isalpha())
    label = CLUSTER_LABELS.get(num, f'Cluster {num}')
    return f'{label} ({code})'


class Command(BaseCommand):
    help = 'Create KUCCPS clusters and link courses from a cluster-programme CSV'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)

    def handle(self, *args, **options):
        path = options['csv_file']

        with open(path, encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))

        if not rows or 'cluster_code' not in rows[0]:
            self.stderr.write(self.style.ERROR("CSV must have 'cluster_code' and 'programme_name' columns"))
            return

        # Build requirements map: first non-empty requirements per code
        requirements_by_code = {}
        has_requirements_col = 'requirements' in (rows[0] if rows else {})
        if has_requirements_col:
            for r in rows:
                code = r['cluster_code'].strip()
                req = r.get('requirements', '').strip()
                if code and req and code not in requirements_by_code:
                    requirements_by_code[code] = req

        # --- Build cluster objects ---
        codes = sorted({r['cluster_code'].strip() for r in rows if r['cluster_code'].strip()})
        self.stdout.write(f'Creating/updating {len(codes)} clusters...')
        cluster_map = {}
        for code in codes:
            name = cluster_name(code)
            req = requirements_by_code.get(code, '')
            obj, created = Cluster.objects.get_or_create(
                name=name,
                defaults={'description': req or f'KUCCPS sub-cluster {code}'},
            )
            if not created and req and obj.description in ('', f'KUCCPS sub-cluster {code}'):
                obj.description = req
                obj.save(update_fields=['description'])
            cluster_map[code] = obj
            status = 'created' if created else 'updated'
            self.stdout.write(f'  {status} {code}: {req[:60] if req else "(no requirements)"}' )

        # --- Build a lookup of courses by normalised name ---
        all_courses = {c.name.upper(): c for c in Course.objects.all()}

        linked = 0
        skipped = 0
        unmatched = []

        for row in rows:
            code = row['cluster_code'].strip()
            prog = ' '.join(row['programme_name'].split())  # normalise whitespace
            cluster_obj = cluster_map.get(code)
            if not cluster_obj or not prog:
                skipped += 1
                continue

            course = all_courses.get(prog.upper())
            if course:
                if course.cluster_id != cluster_obj.pk:
                    course.cluster = cluster_obj
                    course.save(update_fields=['cluster'])
                    linked += 1
            else:
                unmatched.append((code, prog))

        self.stdout.write(self.style.SUCCESS(
            f'\nDone — linked: {linked}, skipped: {skipped}, unmatched: {len(unmatched)}'
        ))

        if unmatched:
            self.stdout.write(f'\nUnmatched programmes ({len(unmatched)}) — no Course found:')
            for code, prog in unmatched[:30]:
                self.stdout.write(f'  [{code}] {prog}')
            if len(unmatched) > 30:
                self.stdout.write(f'  ... and {len(unmatched) - 30} more')
