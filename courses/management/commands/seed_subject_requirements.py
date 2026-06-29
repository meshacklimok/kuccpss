"""
Management command: seed_subject_requirements

Two-pass seeder for courses.Course.subject_requirements:

Pass 1 — CSV (per-programme, exact match):
  Reads clusters_map.csv and matches each programme name to a DB Course.
  Where requirements are parseable, they are set directly.

Pass 2 — PDF cluster fallback (per cluster code):
  For courses that still have null requirements after pass 1, looks up the
  course's KUCCPS sub-cluster code (extracted from cluster.name, e.g. "10C"
  from "Economics, Finance & Actuarial (10C)") and applies the cluster-level
  requirements derived from the official 2025 KUCCPS PDF document.

Usage:
    python manage.py seed_subject_requirements
    python manage.py seed_subject_requirements --dry-run
    python manage.py seed_subject_requirements --pass2-only
    python manage.py seed_subject_requirements --overwrite
"""
import csv
import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from courses.models import Course

CSV_PATH = os.path.join(settings.BASE_DIR, 'clusters_map.csv')

# ── Subject code normalisation ────────────────────────────────────────────────
_CODE_MAP = {
    'mat alternative a':   'mat',
    'mat alternative a/b': 'mat',
    'mat alternative b':   'mat',
    'mat a':               'mat',
    'mat b':               'mat',
    'math a':              'mat',
    'math':                'mat',
    'mat':                 'mat',
    'phy':                 'phy',
    'psc':                 'psc',
    'che':                 'che',
    'bio':                 'bio',
    'bsc':                 'bsc',
    'eng':                 'eng',
    'kis':                 'kis',
    'geo':                 'geo',
    'hag':                 'hst',
    'his':                 'hst',
    'hst':                 'hst',
    'agr':                 'agr',
    'agric':               'agr',
    'bst':                 'bst',
    'comp':                'cmp',
    'cmp':                 'cmp',
    'ard':                 'ard',
    'cre':                 'cre',
    'ire':                 'ire',
    'hre':                 'hre',
    'fre':                 'fre',
    'french':              'fre',
    'ger':                 'ger',
    'german':              'ger',
    'mus':                 'mus',
    'music':               'mus',
    'gsc':                 'gsc',
    'hsc':                 'hsc',
    'sse':                 'sse',
    'with comp':           'cmp',
}

def _norm_code(raw: str) -> str:
    raw = raw.strip().lower()
    for key in sorted(_CODE_MAP, key=len, reverse=True):
        if raw == key or raw.startswith(key + ' '):
            return _CODE_MAP[key]
    return _CODE_MAP.get(raw, raw)


def _parse_requirements(req_str: str):
    if not req_str or not req_str.strip() or req_str.strip() == '-':
        return []
    s = req_str.replace('–', '-').replace('—', '-')
    s = re.sub(r'\s*\(PLAIN\)', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*\(MINUS\)', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+', ' ', s).strip()

    slot_pat = re.compile(r'([A-Z][A-Z0-9 /]*?)\s*-\s*([A-E][+-]?)', re.IGNORECASE)
    slots = []
    slot_num = 0
    consumed_up_to = 0
    for m in slot_pat.finditer(s):
        if m.start() < consumed_up_to:
            continue
        raw_subjects = re.sub(r'^[^A-Za-z]+', '', m.group(1).strip()).strip()
        grade = m.group(2).strip().upper()
        if not raw_subjects:
            continue
        parts = re.split(r'\s*/\s*', raw_subjects)
        normalised = []
        for part in parts:
            code = _norm_code(part.strip())
            if code and code not in normalised:
                normalised.append(code)
        if normalised:
            slot_num += 1
            slots.append({'slot': slot_num, 'subjects_str': '/'.join(normalised), 'min_grade': grade})
        consumed_up_to = m.end()
    return slots


def _norm_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


# ── Authoritative cluster-level requirements from KUCCPS 2025 PDF ─────────────
# Derived from: DEGREE_CLUSTER_DOCUMENT_2025_03_copy.pdf
# Format: cluster sub-code → list of requirement slots
CLUSTER_CODE_REQUIREMENTS = {
    '1A':  [{'slot': 1, 'subjects_str': 'eng/kis', 'min_grade': 'B'}],

    '2A':  [{'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C'}],
    '2B':  [],  # no specific subject requirement

    '3A':  [{'slot': 1, 'subjects_str': 'eng/kis', 'min_grade': 'C+'}],
    '3B':  [{'slot': 1, 'subjects_str': 'eng', 'min_grade': 'C+'}],
    '3C':  [{'slot': 1, 'subjects_str': 'kis', 'min_grade': 'C+'}],
    '3D':  [],
    '3E':  [{'slot': 1, 'subjects_str': 'ard/cmp/eng/kis', 'min_grade': 'C+'}],

    '4A':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'phy', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'geo', 'min_grade': 'C'},
    ],
    '4B':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'phy', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'geo/che', 'min_grade': 'C'},
    ],

    '5A':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'phy', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'che', 'min_grade': 'C+'},
        {'slot': 4, 'subjects_str': 'eng/kis', 'min_grade': 'C+'},
    ],
    '5B':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'phy', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'che', 'min_grade': 'C+'},
    ],
    '5C':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'phy', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'che', 'min_grade': 'C'},
    ],
    '5D':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'phy', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'che', 'min_grade': 'C+'},
        {'slot': 4, 'subjects_str': 'bio', 'min_grade': 'C+'},
    ],
    '5E':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'phy', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'che', 'min_grade': 'C+'},
    ],
    '5F':  [
        {'slot': 1, 'subjects_str': 'phy', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'mat', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'che', 'min_grade': 'C+'},
    ],

    '6A':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'phy', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'eng/kis', 'min_grade': 'C+'},
    ],
    '6B':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'eng/kis', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'geo', 'min_grade': 'C'},
    ],
    '6C':  [{'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'}],

    '7A':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'phy', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'eng/kis', 'min_grade': 'C'},
    ],
    '7B':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'phy', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'eng/kis', 'min_grade': 'C'},
    ],
    '7C':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'eng/kis', 'min_grade': 'C'},
    ],

    '8A':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'bio/agr/bst', 'min_grade': 'C'},
    ],

    '9A':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'bio/che/phy', 'min_grade': 'C'},
    ],
    '9B':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'bio', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'che', 'min_grade': 'C'},
    ],
    '9C':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'phy', 'min_grade': 'C+'},
    ],
    '9D':  [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'che', 'min_grade': 'C+'},
    ],

    '10A': [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'eng/kis', 'min_grade': 'C+'},
    ],
    '10B': [
        {'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'eng/kis', 'min_grade': 'C'},
    ],
    '10C': [{'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'}],

    '11A': [{'slot': 1, 'subjects_str': 'che', 'min_grade': 'C'}],
    '12A': [{'slot': 1, 'subjects_str': 'bio/gsc', 'min_grade': 'C'}],

    '13A': [
        {'slot': 1, 'subjects_str': 'bio', 'min_grade': 'B'},
        {'slot': 2, 'subjects_str': 'che', 'min_grade': 'B'},
        {'slot': 3, 'subjects_str': 'mat/phy', 'min_grade': 'B'},
        {'slot': 4, 'subjects_str': 'eng/kis', 'min_grade': 'B'},
    ],
    '13B': [
        {'slot': 1, 'subjects_str': 'bio', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'che', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'mat/phy', 'min_grade': 'C+'},
        {'slot': 4, 'subjects_str': 'eng/kis', 'min_grade': 'C+'},
    ],
    '13C': [
        {'slot': 1, 'subjects_str': 'bio', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'che', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'mat/phy', 'min_grade': 'C'},
        {'slot': 4, 'subjects_str': 'eng/kis', 'min_grade': 'C'},
    ],
    '13D': [
        {'slot': 1, 'subjects_str': 'bio', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'che', 'min_grade': 'C+'},
        {'slot': 3, 'subjects_str': 'mat/phy/agr', 'min_grade': 'C+'},
    ],
    '13E': [
        {'slot': 1, 'subjects_str': 'bio', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'mat', 'min_grade': 'C+'},
    ],
    '13F': [
        {'slot': 1, 'subjects_str': 'bio', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'mat/phy', 'min_grade': 'C+'},
    ],
    '13G': [
        {'slot': 1, 'subjects_str': 'bio/bsc', 'min_grade': 'C-'},
        {'slot': 2, 'subjects_str': 'mat', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'eng/kis', 'min_grade': 'C+'},
        {'slot': 4, 'subjects_str': 'phy/che/psc', 'min_grade': 'C'},
    ],

    '14A': [{'slot': 1, 'subjects_str': 'hst', 'min_grade': 'C+'}],

    '15A': [
        {'slot': 1, 'subjects_str': 'bio', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'che/mat/phy', 'min_grade': 'C+'},
    ],
    '15B': [
        {'slot': 1, 'subjects_str': 'bio', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'mat/phy/che', 'min_grade': 'C+'},
    ],
    '15C': [
        {'slot': 1, 'subjects_str': 'bio', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'che', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'mat/phy/geo', 'min_grade': 'C'},
        {'slot': 4, 'subjects_str': 'eng/kis', 'min_grade': 'C'},
    ],
    '15D': [
        {'slot': 1, 'subjects_str': 'bio', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'che', 'min_grade': 'C'},
    ],
    '15E': [
        {'slot': 1, 'subjects_str': 'bio/agr/hsc', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'che', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'mat', 'min_grade': 'C'},
    ],
    '15F': [
        {'slot': 1, 'subjects_str': 'bio/agr', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'che/geo', 'min_grade': 'C+'},
    ],
    '15G': [
        {'slot': 1, 'subjects_str': 'bio/agr', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'che', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'mat/phy/geo', 'min_grade': 'C'},
    ],

    '16A': [{'slot': 1, 'subjects_str': 'geo', 'min_grade': 'C+'}],
    '17A': [{'slot': 1, 'subjects_str': 'fre/ger', 'min_grade': 'C+'}],
    '18A': [{'slot': 1, 'subjects_str': 'mus', 'min_grade': 'C+'}],

    '19A': [
        {'slot': 1, 'subjects_str': 'mat/phy/che/bio', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'mat/phy/che/bio', 'min_grade': 'C+'},
    ],
    '19B': [
        {'slot': 1, 'subjects_str': 'eng/kis/mat/hst/geo/cre/ire/hre/hsc/ard/cmp', 'min_grade': 'C+'},
    ],
    '19C': [{'slot': 1, 'subjects_str': 'mat/bst', 'min_grade': 'C+'}],
    '19D': [{'slot': 1, 'subjects_str': 'bio/gsc', 'min_grade': 'C+'}],
    '19E': [
        {'slot': 1, 'subjects_str': 'bio/gsc', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'mat/geo', 'min_grade': 'C+'},
    ],
    '19F': [{'slot': 1, 'subjects_str': 'fre', 'min_grade': 'C+'}],
    '19G': [{'slot': 1, 'subjects_str': 'mus', 'min_grade': 'C+'}],
    '19H': [{'slot': 1, 'subjects_str': 'ger', 'min_grade': 'C+'}],
    '19J': [{'slot': 1, 'subjects_str': 'mat', 'min_grade': 'C+'}],
    '19K': [
        {'slot': 1, 'subjects_str': 'bio', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'agr/bio', 'min_grade': 'C+'},
    ],

    '20A': [
        {'slot': 1, 'subjects_str': 'cre/ire/hre', 'min_grade': 'C+'},
        {'slot': 2, 'subjects_str': 'eng/kis', 'min_grade': 'C'},
    ],
}

_SUBCLUSTER_RE = re.compile(r'\((\d+[A-Z])\)$')

def _extract_subcluster(cluster_name: str) -> str | None:
    """Extract sub-cluster code from cluster name, e.g. 'Economics... (10C)' -> '10C'."""
    m = _SUBCLUSTER_RE.search(cluster_name.strip())
    return m.group(1) if m else None


class Command(BaseCommand):
    help = 'Seed subject_requirements from clusters_map.csv + 2025 KUCCPS PDF fallback'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--pass2-only', action='store_true',
                            help='Skip CSV pass, only apply PDF cluster fallback')
        parser.add_argument('--overwrite', action='store_true',
                            help='Overwrite existing requirements')

    def handle(self, *args, **options):
        dry_run   = options['dry_run']
        pass2_only = options['pass2_only']
        overwrite  = options['overwrite']

        degree_qs = Course.objects.filter(
            course_type__name__icontains='Degree'
        ).select_related('cluster')

        # ── Pass 1: CSV per-programme matching ────────────────────────────
        p1_updated = 0
        if not pass2_only:
            name_index: dict[str, list] = {}
            for c in degree_qs:
                key = _norm_name(c.name)
                name_index.setdefault(key, []).append(c)

            with open(CSV_PATH, newline='', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    csv_name    = (row.get('programme_name') or '').strip()
                    csv_req_raw = (row.get('requirements')   or '').strip()

                    slots = _parse_requirements(csv_req_raw)
                    if not slots:
                        continue

                    norm_csv = _norm_name(csv_name)
                    matches = name_index.get(norm_csv, [])
                    if not matches:
                        for key, courses in name_index.items():
                            if key.startswith(norm_csv[:30]) or norm_csv.startswith(key[:30]):
                                matches = courses
                                break

                    for course in matches:
                        if not overwrite and course.subject_requirements:
                            continue
                        if dry_run:
                            self.stdout.write(f'[P1] {course.name[:60]} => {slots}')
                        else:
                            course.subject_requirements = slots
                            course.save(update_fields=['subject_requirements'])
                        p1_updated += 1

            self.stdout.write(f'Pass 1 (CSV): updated {p1_updated} courses.')

        # ── Pass 2: PDF cluster fallback for courses still missing reqs ───
        p2_updated = 0
        p2_skipped = 0

        for course in degree_qs:
            if not overwrite and course.subject_requirements:
                continue  # already has requirements from pass 1 or previous run

            cluster = course.cluster
            if not cluster:
                p2_skipped += 1
                continue

            subcluster = _extract_subcluster(cluster.name)
            if not subcluster:
                p2_skipped += 1
                continue

            slots = CLUSTER_CODE_REQUIREMENTS.get(subcluster)
            if slots is None:
                p2_skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f'[P2] {course.name[:60]} '
                    f'(cluster {subcluster}) => {slots if slots else "[]"}'
                )
            else:
                course.subject_requirements = slots if slots else None
                course.save(update_fields=['subject_requirements'])
            p2_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Pass 2 (PDF fallback): updated {p2_updated}, '
            f'skipped (no cluster code) {p2_skipped}.'
        ))
