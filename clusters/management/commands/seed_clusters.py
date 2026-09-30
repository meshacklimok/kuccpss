"""
Management command: seed_clusters

Replaces all Subject records with the official 31 KCSE subjects (Groups I–V)
and creates/updates the 18 KUCCPS clusters (rows 101–118), each with exactly
4 SubjectGroup slots used by the cluster-points formula.

Cluster names come from clusters/constants.py and the slots from the KUCCPS
portal's "Minimum Entry Requirements" (data/kuccps_portal_degrees.json) — the
same source import_kuccps_portal uses, so the two can never disagree.

Usage:
    py -3.13 manage.py seed_clusters
"""
import json

from django.core.management.base import BaseCommand
from django.db import transaction

from clusters.models import Subject
from courses.management.commands.import_kuccps_portal import (
    DATA_PATH, Command as PortalImport, cluster_patterns,
)


# ──────────────────────────────────────────────────────────────
# Official KCSE subjects by KUCCPS group
# ──────────────────────────────────────────────────────────────

SUBJECTS_BY_GROUP = {
    'I': [
        'English',
        'Kiswahili',
        'Mathematics',
    ],
    'II': [
        'Biology',
        'Physics',
        'Chemistry',
    ],
    'III': [
        'History and Government',
        'Geography',
        'Christian Religious Education',
        'Islamic Religious Education',
        'Hindu Religious Education',
    ],
    'IV': [
        'Home Science',
        'Art and Design',
        'Agriculture',
        'Woodwork',
        'Metalwork',
        'Building Construction',
        'Power Mechanics',
        'Electricity',
        'Drawing and Design',
        'Aviation Technology',
        'Computer Studies',
    ],
    'V': [
        'French',
        'German',
        'Arabic',
        'Kenyan Sign Language',
        'Music',
        'Business Studies',
    ],
}


class Command(BaseCommand):
    help = (
        'Replace Subject records with the official 31 KCSE subjects and '
        'create/update the 18 KUCCPS clusters from the portal data.'
    )

    def handle(self, *args, **options):
        self.stdout.write('-' * 60)
        self.stdout.write('KUCCPS seed_clusters - starting')
        self.stdout.write('-' * 60)

        with transaction.atomic():
            self._seed_subjects()
            self._seed_clusters()

        self.stdout.write(self.style.SUCCESS('\nDone.'))

    # ──────────────────────────────────────────────────
    def _seed_subjects(self):
        self.stdout.write('\n[1/2] Subjects')

        # Remove all existing subjects (clears SubjectGroup M2M automatically)
        deleted, _ = Subject.objects.all().delete()
        self.stdout.write(f'  Deleted {deleted} old subject records')

        created = 0
        for group_code, names in SUBJECTS_BY_GROUP.items():
            for name in names:
                Subject.objects.create(name=name, group=group_code)
                created += 1

        self.stdout.write(f'  Created {created} subjects across 5 groups')

    # ──────────────────────────────────────────────────
    def _seed_clusters(self):
        self.stdout.write('\n[2/2] KUCCPS clusters')
        with open(DATA_PATH, encoding='utf-8') as f:
            patterns = cluster_patterns(json.load(f))
        importer = PortalImport(stdout=self.stdout)
        importer.log = []
        importer.restructure_clusters(patterns, {s.name: s for s in Subject.objects.all()})
