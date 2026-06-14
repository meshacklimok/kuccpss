"""
Management command: seed_tvet_craft_artisan

Seeds canonical KNEC Craft Certificate and Artisan Certificate programmes.
Source: tveta.go.ke/tvet-courses (KNEC-examined programmes only)

Level mapping (our DB naming vs KNEC naming):
  KNEC "Craft Certificate"  → CourseType "TVET Artisan Certificate (Level 4)"  (min D)
  KNEC "Artisan Certificate" → CourseType "TVET Craft Certificate (Level 3)"   (min D-)

Usage:
    conda run python manage.py seed_tvet_craft_artisan
    conda run python manage.py seed_tvet_craft_artisan --clear
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from courses.models import Course, CourseType, CourseCategory


# ─────────────────────────────────────────────────────────────────────────────
# KNEC Craft Certificate programmes  →  "TVET Artisan Certificate (Level 4)"
# Format: ('Course Name', 'Sector/Category')
# ─────────────────────────────────────────────────────────────────────────────
CRAFT_PROGRAMMES = [
    # Business & Commerce
    ('Craft Certificate in Accountancy',                          'Business & Commerce'),
    ('Craft Certificate in Banking and Finance',                  'Business & Commerce'),
    ('Craft Certificate in Business Administration',              'Business & Commerce'),
    ('Craft Certificate in Business Management',                  'Business & Commerce'),
    ('Craft Certificate in Clerical Operations',                  'Business & Commerce'),
    ('Craft Certificate in Co-operative Management',              'Business & Commerce'),
    ('Craft Certificate in Human Resource Management',            'Business & Commerce'),
    ('Craft Certificate in Investment Management',                'Business & Commerce'),
    ('Craft Certificate in Marketing',                            'Business & Commerce'),
    ('Craft Certificate in Personnel Management',                 'Business & Commerce'),
    ('Craft Certificate in Project Management',                   'Business & Commerce'),
    ('Craft Certificate in Sales and Marketing',                  'Business & Commerce'),
    ('Craft Certificate in Secretarial Studies',                  'Business & Commerce'),
    ('Craft Certificate in Social Development',                   'Business & Commerce'),
    ('Craft Certificate in Supplies Management',                  'Business & Commerce'),
    ('Craft Certificate in Supply Chain Management',              'Business & Commerce'),
    # Computing & ICT
    ('Craft Certificate in Information Communication Technology', 'Computing & ICT'),
    ('Craft Certificate in Information Technology',               'Computing & ICT'),
    ('Craft Certificate in Information Studies',                  'Computing & ICT'),
    # Engineering & Technology
    ('Craft Certificate in Agricultural Engineering',             'Engineering & Technology'),
    ('Craft Certificate in Agricultural Mechanics',               'Engineering & Technology'),
    ('Craft Certificate in Automotive Engineering',               'Engineering & Technology'),
    ('Craft Certificate in Building Technology',                  'Engineering & Technology'),
    ('Craft Certificate in Carpentry and Joinery',                'Engineering & Technology'),
    ('Craft Certificate in Construction Plant Technology',        'Engineering & Technology'),
    ('Craft Certificate in Electrical and Electronics Technology','Engineering & Technology'),
    ('Craft Certificate in Electrical and Electronics Technology (Power)',        'Engineering & Technology'),
    ('Craft Certificate in Electrical and Electronics Technology (Telecommunication)', 'Engineering & Technology'),
    ('Craft Certificate in Electrical Installation',              'Engineering & Technology'),
    ('Craft Certificate in Masonry',                              'Engineering & Technology'),
    ('Craft Certificate in Mechanical Engineering',               'Engineering & Technology'),
    ('Craft Certificate in Mechanical Engineering (Construction)','Engineering & Technology'),
    ('Craft Certificate in Mechanical Engineering (Plant)',       'Engineering & Technology'),
    ('Craft Certificate in Mechanical Engineering (Production)',  'Engineering & Technology'),
    ('Craft Certificate in Motor Vehicle Mechanics',              'Engineering & Technology'),
    ('Craft Certificate in Motor Vehicle Technology',             'Engineering & Technology'),
    ('Craft Certificate in Plumbing',                             'Engineering & Technology'),
    ('Craft Certificate in Printing Technology',                  'Engineering & Technology'),
    ('Craft Certificate in Radio Servicing',                      'Engineering & Technology'),
    ('Craft Certificate in Road Construction',                    'Engineering & Technology'),
    ('Craft Certificate in Water Engineering',                    'Engineering & Technology'),
    ('Craft Certificate in Water Technology',                     'Engineering & Technology'),
    ('Craft Certificate in Welding and Fabrication',              'Engineering & Technology'),
    # Agriculture
    ('Craft Certificate in Fisheries Science and Technology',     'Agriculture'),
    ('Craft Certificate in General Agriculture',                  'Agriculture'),
    # Health Sciences
    ('Craft Certificate in Medical Laboratory Technology',        'Health Sciences'),
    ('Craft Certificate in Nutrition and Dietetics',              'Health Sciences'),
    ('Craft Certificate in Science Laboratory Technology',        'Health Sciences'),
    # Hospitality & Tourism
    ('Craft Certificate in Baking Technology',                    'Hospitality & Tourism'),
    ('Craft Certificate in Catering and Accommodation Operations','Hospitality & Tourism'),
    ('Craft Certificate in Food and Beverage Production and Service', 'Hospitality & Tourism'),
    ('Craft Certificate in Food Processing and Preservation',     'Hospitality & Tourism'),
    ('Craft Certificate in Food Processing Technology',           'Hospitality & Tourism'),
    ('Craft Certificate in Housekeeping and Laundry',             'Hospitality & Tourism'),
    ('Craft Certificate in Tour Guiding and Travel Operations',   'Hospitality & Tourism'),
    ('Craft Certificate in Tour Guiding Operations',              'Hospitality & Tourism'),
    # Fashion & Design
    ('Craft Certificate in Fashion Design and Garment Making',    'Fashion & Design'),
    ('Craft Certificate in Tannery and Leatherwork',              'Fashion & Design'),
    # Built Environment
    ('Craft Certificate in Cartography',                          'Built Environment'),
    ('Craft Certificate in Land Surveying',                       'Built Environment'),
    ('Craft Certificate in Photogrammetry',                       'Built Environment'),
    # Transport & Logistics
    ('Craft Certificate in Marine Engineering',                   'Transport & Logistics'),
    ('Craft Certificate in Maritime Transport Logistics',         'Transport & Logistics'),
    ('Craft Certificate in Maritime Transport Operations',        'Transport & Logistics'),
    ('Craft Certificate in Nautical Science',                     'Transport & Logistics'),
    ('Craft Certificate in Road Transport Management',            'Transport & Logistics'),
    ('Craft Certificate in Transport Management',                 'Transport & Logistics'),
    # Media & Communications
    ('Craft Certificate in Library, Archives and Information Studies', 'Media & Communications'),
    # Social Sciences
    ('Craft Certificate in Child Care and Protection',            'Social Sciences'),
    ('Craft Certificate in Social Work and Community Development','Social Sciences'),
    # Environment & Natural Resources
    ('Craft Certificate in Petroleum Geosciences',                'Environment & Natural Resources'),
]


# ─────────────────────────────────────────────────────────────────────────────
# KNEC Artisan Certificate programmes  →  "TVET Craft Certificate (Level 3)"
# Format: ('Course Name', 'Sector/Category')
# ─────────────────────────────────────────────────────────────────────────────
ARTISAN_PROGRAMMES = [
    # Engineering & Technology
    ('Artisan Certificate in Appropriate Carpentry and Joinery',  'Engineering & Technology'),
    ('Artisan Certificate in Building Technology',                'Engineering & Technology'),
    ('Artisan Certificate in Electrical and Electronics Technology', 'Engineering & Technology'),
    ('Artisan Certificate in Electrical Installation',            'Engineering & Technology'),
    ('Artisan Certificate in General Fitter',                     'Engineering & Technology'),
    ('Artisan Certificate in Masonry',                            'Engineering & Technology'),
    ('Artisan Certificate in Mechanical Engineering (Plant)',     'Engineering & Technology'),
    ('Artisan Certificate in Metal Processing Technology',        'Engineering & Technology'),
    ('Artisan Certificate in Motor Vehicle Mechanics',            'Engineering & Technology'),
    ('Artisan Certificate in Motor Vehicle Technology',           'Engineering & Technology'),
    ('Artisan Certificate in Painting and Decoration',            'Engineering & Technology'),
    ('Artisan Certificate in Plumbing',                           'Engineering & Technology'),
    ('Artisan Certificate in Refrigeration and Air Conditioning', 'Engineering & Technology'),
    ('Artisan Certificate in Welding and Fabrication',            'Engineering & Technology'),
    # Agriculture
    ('Artisan Certificate in Agricultural Mechanics',             'Agriculture'),
    ('Artisan Certificate in General Agriculture',                'Agriculture'),
    # Hospitality & Tourism
    ('Artisan Certificate in Food and Beverage',                  'Hospitality & Tourism'),
    ('Artisan Certificate in Food Processing Technology',         'Hospitality & Tourism'),
    # Fashion & Design
    ('Artisan Certificate in Fashion Design and Garment Making',  'Fashion & Design'),
    ('Artisan Certificate in Hairdressing and Beauty Therapy',    'Fashion & Design'),
    ('Artisan Certificate in Leather Work',                       'Fashion & Design'),
    # Business & Commerce
    ('Artisan Certificate in Clerk-Typist',                       'Business & Commerce'),
    ('Artisan Certificate in Salesmanship',                       'Business & Commerce'),
    ('Artisan Certificate in Storekeeping',                       'Business & Commerce'),
    # Computing & ICT
    ('Artisan Certificate in Information Communication Technology', 'Computing & ICT'),
    # Transport & Logistics
    ('Artisan Certificate in Seafarers',                          'Transport & Logistics'),
]


class Command(BaseCommand):
    help = 'Seed KNEC Craft and Artisan Certificate courses from TVETA/tveta.go.ke/tvet-courses.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete existing Craft/Artisan courses before re-seeding.'
        )

    def handle(self, *args, **options):
        self.stdout.write('-' * 60)
        self.stdout.write('seed_tvet_craft_artisan — starting')
        self.stdout.write('-' * 60)

        with transaction.atomic():
            artisan_ct = CourseType.objects.filter(name='TVET Artisan Certificate (Level 4)').first()
            craft_ct   = CourseType.objects.filter(name='TVET Craft Certificate (Level 3)').first()

            if not artisan_ct or not craft_ct:
                self.stdout.write(self.style.ERROR(
                    'TVET course types not found. Run seed_tvet first.'
                ))
                return

            if options['clear']:
                n1, _ = Course.objects.filter(course_type=artisan_ct).delete()
                n2, _ = Course.objects.filter(course_type=craft_ct).delete()
                CourseCategory.objects.filter(course_type__in=[artisan_ct, craft_ct]).delete()
                self.stdout.write(f'  Cleared {n1} Artisan (L4) and {n2} Craft (L3) courses')

            craft_created   = self._seed_programmes(CRAFT_PROGRAMMES,   artisan_ct, min_grade='D')
            artisan_created = self._seed_programmes(ARTISAN_PROGRAMMES,  craft_ct,   min_grade='D-')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Craft Certificate (L4): {craft_created} | Artisan Certificate (L3): {artisan_created}'
        ))

    def _seed_programmes(self, programmes, course_type, min_grade):
        # Build a short prefix so category slugs don't clash across course types
        # e.g. "TVET Artisan Certificate (Level 4)" → "a4"
        #      "TVET Craft Certificate (Level 3)"   → "c3"
        if 'Level 4' in course_type.name:
            cat_prefix = 'a4'
        elif 'Level 3' in course_type.name:
            cat_prefix = 'c3'
        elif 'Level 5' in course_type.name:
            cat_prefix = 'c5'
        elif 'Level 6' in course_type.name:
            cat_prefix = 'd6'
        else:
            cat_prefix = slugify(course_type.name)[:6]

        cat_cache = {}
        created = 0

        for name, sector in programmes:
            if sector not in cat_cache:
                cat_slug = f"{cat_prefix}-{slugify(sector)}"
                try:
                    cat = CourseCategory.objects.get(slug=cat_slug)
                except CourseCategory.DoesNotExist:
                    cat = CourseCategory.objects.create(
                        name=sector,
                        slug=cat_slug,
                        course_type=course_type,
                        description=f'{course_type.name} — {sector}',
                    )
                cat_cache[sector] = cat

            _, was_created = Course.objects.get_or_create(
                name=name,
                course_type=course_type,
                defaults={
                    'category': cat_cache[sector],
                    'minimum_mean_grade': min_grade,
                    'description': (
                        f'{course_type.name} — {cat_cache[sector].name}. '
                        f'Minimum KCSE mean grade: {min_grade}.'
                    ),
                }
            )
            if was_created:
                created += 1

        return created
