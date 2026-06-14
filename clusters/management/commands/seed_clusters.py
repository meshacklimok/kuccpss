"""
Management command: seed_clusters

Replaces all Subject records with the official 31 KCSE subjects (Groups I–V)
and creates/updates the 20 KUCCPS master calculation clusters, each with
exactly 4 SubjectGroup slots used by the cluster-points formula.

Does NOT touch the existing 61 programme sub-clusters (1A, 1B, … 20F) that
are used for course matching / requirements display.

Usage:
    py -3.13 manage.py seed_clusters
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from clusters.models import Subject, Cluster, SubjectGroup


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

# Handy aliases used in slot definitions below
G1      = SUBJECTS_BY_GROUP['I']
G2      = SUBJECTS_BY_GROUP['II']
G3      = SUBJECTS_BY_GROUP['III']
G4      = SUBJECTS_BY_GROUP['IV']
G5      = SUBJECTS_BY_GROUP['V']
G1_LANG = ['English', 'Kiswahili']
G1_MATH = ['Mathematics']
G2_G3   = G2 + G3
G2_G5   = G2 + G3 + G4 + G5   # "any Group II–V"
ALL     = G1 + G2 + G3 + G4 + G5


# ──────────────────────────────────────────────────────────────
# 20 master calculation clusters
# Each cluster has exactly 4 slots.
# Slot = (slot_name, [valid_subjects])
# The calculator picks the BEST subject from each slot in
# priority order (1→4), never repeating a subject already used.
# ──────────────────────────────────────────────────────────────

CLUSTERS_DATA = [
    {
        'number': 101,
        'name': 'Law',
        'description': 'Law, paralegal and related programmes.',
        'slots': [
            ('Language (ENG/KIS)',           G1_LANG),
            ('Mathematics or Sciences',      G1_MATH + G2),
            ('Humanities',                   G3),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 102,
        'name': 'Business, Hospitality, Tourism & Related',
        'description': 'Business, hospitality, tourism and commerce programmes.',
        'slots': [
            ('Language (ENG/KIS)',           G1_LANG),
            ('Mathematics',                  G1_MATH),
            ('Sciences or Humanities',       G2_G3),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 103,
        'name': 'Communication, Media, Languages & Social Sciences',
        'description': 'Communication, journalism, social sciences and language programmes.',
        'slots': [
            ('Language (ENG/KIS)',           G1_LANG),
            ('Mathematics or Sciences',      G1_MATH + G2),
            ('Humanities',                   G3),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 104,
        'name': 'Geosciences & Related',
        'description': 'Geology, earth sciences, surveying and related programmes.',
        'slots': [
            ('Mathematics Alt A',            ['Mathematics']),
            ('Physics',                      ['Physics']),
            ('Biology, Chemistry or Geog.',  ['Biology', 'Chemistry', 'Geography']),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 105,
        'name': 'Engineering, Technology & Energy',
        'description': 'All engineering, technology and energy programmes.',
        'slots': [
            ('Mathematics Alt A',            ['Mathematics']),
            ('Physics',                      ['Physics']),
            ('Chemistry',                    ['Chemistry']),
            ('Biology or Grp III/IV/V',      ['Biology'] + G3 + G4 + G5),
        ],
    },
    {
        'number': 106,
        'name': 'Architecture, Quantity Survey, Building & Planning',
        'description': 'Architecture, building technology, quantity survey and urban planning programmes.',
        'slots': [
            ('Mathematics Alt A',            ['Mathematics']),
            ('Physics',                      ['Physics']),
            ('Humanities',                   G3),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 107,
        'name': 'Computer Science, IT & Related',
        'description': 'Computer science, IT, software engineering and related programmes.',
        'slots': [
            ('Mathematics Alt A',            ['Mathematics']),
            ('Physics',                      ['Physics']),
            ('Sciences or Humanities',       G2_G3),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 108,
        'name': 'Agricultural Economics & Agribusiness',
        'description': 'Agricultural economics, agribusiness and related programmes.',
        'slots': [
            ('Mathematics Alt A',            ['Mathematics']),
            ('Biology',                      ['Biology']),
            ('Physics or Chemistry',         ['Physics', 'Chemistry']),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 109,
        'name': 'General Sciences (Biology, Physics, Chemistry) & Related',
        'description': 'General science programmes including biology, physics, chemistry combinations.',
        'slots': [
            ('Mathematics Alt A',            ['Mathematics']),
            ('Best Science (Grp II)',         G2),
            ('2nd Best Science (Grp II)',     G2),       # algorithm skips already-used subject
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 110,
        'name': 'Actuarial Science, Mathematics, Economics & Statistics',
        'description': 'Actuarial science, pure mathematics, statistics, economics and quantitative programmes.',
        'slots': [
            ('Mathematics Alt A',            ['Mathematics']),
            ('Sciences (Grp II)',             G2),
            ('Humanities (Grp III)',          G3),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 111,
        'name': 'Interior Design, Fashion, Textile & Related',
        'description': 'Interior design, fashion design, textile technology and related creative programmes.',
        'slots': [
            ('Chemistry',                    ['Chemistry']),
            ('Mathematics or Physics',       G1_MATH + ['Physics']),
            ('Biology or Home Science',      ['Biology', 'Home Science']),
            ('Language or Grp III/IV/V',     G1_LANG + G3 + G4 + G5),
        ],
    },
    {
        'number': 112,
        'name': 'Sports Science & Related',
        'description': 'Sports science, physical education and related programmes.',
        'slots': [
            ('Biology',                       ['Biology']),
            ('Mathematics',                  G1_MATH),
            ('Sciences or Humanities',       G2_G3),
            ('Language or Best Elective',    G1_LANG + G2_G5),
        ],
    },
    {
        'number': 113,
        'name': 'Medicine, Nursing, Dentistry, Pharmacy & Health Sciences',
        'description': 'All medical, health sciences and clinical programmes.',
        'slots': [
            ('Biology',                      ['Biology']),
            ('Chemistry',                    ['Chemistry']),
            ('Mathematics Alt A or Physics', ['Mathematics', 'Physics']),
            ('Language or Best Elective',    G1_LANG + G2_G5),
        ],
    },
    {
        'number': 114,
        'name': 'History, Archaeology & Related',
        'description': 'History, archaeology, anthropology and cultural studies programmes.',
        'slots': [
            ('History and Government',       ['History and Government']),
            ('Language (ENG/KIS)',           G1_LANG),
            ('Mathematics or Sciences',      G1_MATH + G2),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 115,
        'name': 'Agriculture, Animal Health, Food Science & Environment',
        'description': 'Agriculture, food science, animal health, environmental science and natural resources programmes.',
        'slots': [
            ('Biology',                      ['Biology']),
            ('Chemistry',                    ['Chemistry']),
            ('Maths, Physics or Geography',  G1_MATH + ['Physics', 'Geography']),
            ('Language or Best Elective',    G1_LANG + G2_G5),
        ],
    },
    {
        'number': 116,
        'name': 'Geography & Related',
        'description': 'Geography, geomatics, environmental planning and related programmes.',
        'slots': [
            ('Geography',                    ['Geography']),
            ('Language (ENG/KIS)',           G1_LANG),
            ('Maths, Sciences or Hum.',      G1_MATH + G2_G3),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 117,
        'name': 'French & German',
        'description': 'French language, German language and related linguistics programmes.',
        'slots': [
            ('French or German',             ['French', 'German']),
            ('Language (ENG/KIS)',           G1_LANG),
            ('Maths, Sciences or Hum.',      G1_MATH + G2_G3),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 118,
        'name': 'Music & Related',
        'description': 'Music performance, composition, music education and related arts programmes.',
        'slots': [
            ('Music',                        ['Music']),
            ('Language (ENG/KIS)',           G1_LANG),
            ('Maths, Sciences or Hum.',      G1_MATH + G2_G3),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
    {
        'number': 119,
        'name': 'Education & Related',
        'description': 'Teacher training and education programmes (two teaching subjects required at C+ or above).',
        'slots': [
            ('English',                      ['English']),
            ('Mathematics',                  G1_MATH),
            ('Best Teaching Subject',        ALL),
            ('2nd Best Teaching Subject',    ALL),
        ],
    },
    {
        'number': 120,
        'name': 'Religious Studies, Theology & Islamic Studies',
        'description': 'Religious studies, theology, divinity and Islamic studies programmes.',
        'slots': [
            ('Religious Subject',            ['Christian Religious Education',
                                              'Islamic Religious Education',
                                              'Hindu Religious Education']),
            ('Language (ENG/KIS)',           G1_LANG),
            ('Mathematics or Sciences',      G1_MATH + G2),
            ('Best Elective (Grp II–V)',     G2_G5),
        ],
    },
]


class Command(BaseCommand):
    help = (
        'Replace Subject records with the official 31 KCSE subjects and '
        'create/update the 20 KUCCPS master calculation clusters.'
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
        self.stdout.write('\n[2/2] Master calculation clusters')

        # Build a lookup from subject name → Subject object
        subject_map = {s.name: s for s in Subject.objects.all()}

        created_count = updated_count = 0

        for cd in CLUSTERS_DATA:
            cluster, created = Cluster.objects.get_or_create(
                name=cd['name'],
                defaults={
                    'description': cd['description'],
                    'number': cd['number'],
                }
            )

            if not created:
                # Update description if it changed
                cluster.description = cd['description']
                # Only set number if it hasn't been set or matches our range
                if cluster.number is None or cluster.number >= 100:
                    cluster.number = cd['number']
                cluster.save(update_fields=['description', 'number'])
                updated_count += 1
            else:
                created_count += 1

            # Remove old SubjectGroups for this cluster and rebuild
            cluster.subject_groups.all().delete()

            for priority, (slot_name, subject_names) in enumerate(cd['slots'], start=1):
                sg = SubjectGroup.objects.create(
                    cluster=cluster,
                    name=slot_name,
                    required=True,
                    priority=priority,
                )
                subjects_for_slot = [
                    subject_map[n] for n in subject_names if n in subject_map
                ]
                sg.subjects.set(subjects_for_slot)

            status = 'created' if created else 'updated'
            self.stdout.write(f'  [{status}] {cluster.name}')

        self.stdout.write(
            f'\n  {created_count} clusters created, {updated_count} updated'
        )
