"""
Management command: seed_tvet_remaining

Seeds the five remaining TVET course types:
  - TVET Certificate (Level 5)   — 2-year programmes, min grade D+
  - TVET Short Course            — skills courses < 3 months, open entry
  - TVET Trade Test              — NITA occupational tests, no mean grade
  - TVET Proficiency             — KNEC/KASNEB proficiency certs, min D-
  - TVET Professional            — KASNEB/IHRM/KISM professional quals, min C

Sources:
  Level 5 — tveta.go.ke/tvet-courses (Level 5 entries from national polytechnics)
  Trade Test — NITA Kenya standard trade subjects
  Professional — KASNEB Kenya qualifications register

Usage:
    conda run python manage.py seed_tvet_remaining
    conda run python manage.py seed_tvet_remaining --clear
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from courses.models import Course, CourseType, CourseCategory


# ─── slug prefix per CourseType  ─────────────────────────────────────────────
SLUG_PREFIX = {
    'TVET Certificate (Level 5)': 'c5',
    'TVET Short Course':          'sc',
    'TVET Trade Test':            'tt',
    'TVET Proficiency':           'pf',
    'TVET Professional':          'pl',
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. TVET CERTIFICATE (LEVEL 5)
#    Source: tveta.go.ke/tvet-courses Level 5 listings across national polys
#    Format: ('Course Name', 'Sector')
# ─────────────────────────────────────────────────────────────────────────────
CERTIFICATE_L5 = [
    # Business & Commerce
    ('Certificate in Business Management (Level 5)',               'Business & Commerce'),
    ('Certificate in Human Resource Management (Level 5)',         'Business & Commerce'),
    ('Certificate in Office Administration (Level 5)',             'Business & Commerce'),
    ('Certificate in Co-operative Management (Level 5)',           'Business & Commerce'),
    ('Certificate in Records and Archives Management (Level 5)',   'Business & Commerce'),
    ('Certificate in Front Office Operations (Level 5)',           'Business & Commerce'),
    # Computing & ICT
    ('Certificate in Information Communication Technology (Level 5)', 'Computing & ICT'),
    ('Certificate in Data Communication and Network Technology (Level 5)', 'Computing & ICT'),
    # Engineering & Technology
    ('Certificate in Electrical and Electronics Engineering Technology (Level 5)', 'Engineering & Technology'),
    ('Certificate in Automotive Technology (Level 5)',             'Engineering & Technology'),
    ('Certificate in Mechanical Engineering Technology (Level 5)', 'Engineering & Technology'),
    ('Certificate in Plumbing Technology (Level 5)',               'Engineering & Technology'),
    ('Certificate in Welding and Fabrication Technology (Level 5)','Engineering & Technology'),
    ('Certificate in Road Construction Technology (Level 5)',      'Engineering & Technology'),
    ('Certificate in Science Laboratory Technology (Level 5)',     'Engineering & Technology'),
    ('Certificate in Instrumentation and Control Technology (Level 5)', 'Engineering & Technology'),
    ('Certificate in Solar Photovoltaic Technology (Level 5)',     'Engineering & Technology'),
    ('Certificate in Automotive Mechatronics Technology (Level 5)','Engineering & Technology'),
    ('Certificate in Fire Fighting Technology (Level 5)',          'Engineering & Technology'),
    ('Certificate in Marine Welding and Fabrication (Level 5)',    'Engineering & Technology'),
    # Agriculture
    ('Certificate in General Agriculture (Level 5)',               'Agriculture'),
    ('Certificate in Agricultural Extension Technology (Level 5)', 'Agriculture'),
    ('Certificate in Horticulture Production (Level 5)',           'Agriculture'),
    ('Certificate in Fisheries Technology (Level 5)',              'Agriculture'),
    ('Certificate in Aquaculture Technology (Level 5)',            'Agriculture'),
    ('Certificate in Dairy Processing Technology (Level 5)',       'Agriculture'),
    ('Certificate in Food Processing Technology (Level 5)',        'Agriculture'),
    ('Certificate in Animal Health and Production (Level 5)',      'Agriculture'),
    # Health Sciences
    ('Certificate in Community Health (Level 5)',                  'Health Sciences'),
    ('Certificate in Medical Engineering Technology (Level 5)',    'Health Sciences'),
    ('Certificate in Mortuary Science (Level 5)',                  'Health Sciences'),
    # Hospitality & Tourism
    ('Certificate in Food and Beverage Production (Level 5)',      'Hospitality & Tourism'),
    ('Certificate in Tourism Management (Level 5)',                'Hospitality & Tourism'),
    ('Certificate in Cosmetology (Level 5)',                       'Hospitality & Tourism'),
    ('Certificate in Hair Dressing Technology (Level 5)',          'Hospitality & Tourism'),
    # Fashion & Design
    ('Certificate in Fashion and Apparel Design (Level 5)',        'Fashion & Design'),
    # Built Environment
    ('Certificate in Building and Civil Engineering Technology (Level 5)', 'Built Environment'),
    ('Certificate in Masonry Technology (Level 5)',                'Built Environment'),
    # Social Sciences
    ('Certificate in Social Work and Community Development (Level 5)', 'Social Sciences'),
    ('Certificate in Criminology and Criminal Justice (Level 5)',  'Social Sciences'),
    ('Certificate in Sports Coaching (Level 5)',                   'Social Sciences'),
    # Environment & Natural Resources
    ('Certificate in Paramilitary and Wildlife Law Enforcement (Level 5)', 'Environment & Natural Resources'),
]


# ─────────────────────────────────────────────────────────────────────────────
# 2. TVET SHORT COURSES
#    Skills-based courses, typically 1–12 weeks, open entry (no mean grade)
# ─────────────────────────────────────────────────────────────────────────────
SHORT_COURSES = [
    # Computing & ICT
    ('Computer Application Skills',            'Computing & ICT'),
    ('Digital Marketing and Social Media',     'Computing & ICT'),
    ('Graphic Design',                         'Computing & ICT'),
    ('Mobile Phone Repair',                    'Computing & ICT'),
    ('Photography and Videography',            'Computing & ICT'),
    ('Web Design Basics',                      'Computing & ICT'),
    # Engineering & Technology
    ('Basic Electrical Wiring',                'Engineering & Technology'),
    ('Solar PV Installation',                  'Engineering & Technology'),
    ('Refrigeration and Air Conditioning Basics', 'Engineering & Technology'),
    ('Basic Plumbing',                         'Engineering & Technology'),
    ('CNC Machine Operations',                 'Engineering & Technology'),
    # Hospitality & Tourism
    ('Basic Catering and Food Preparation',    'Hospitality & Tourism'),
    ('Pastry and Bakery',                      'Hospitality & Tourism'),
    ('Barista and Mixology Skills',            'Hospitality & Tourism'),
    ('Food Hygiene and Safety',                'Hospitality & Tourism'),
    ('Housekeeping and Laundry Basics',        'Hospitality & Tourism'),
    # Fashion & Design
    ('Basic Tailoring and Dress Making',       'Fashion & Design'),
    ('Beauty Therapy Basics',                  'Fashion & Design'),
    ('Nail Technology',                        'Fashion & Design'),
    ('Hair Styling',                           'Fashion & Design'),
    ('Interior Decoration Basics',             'Fashion & Design'),
    # Agriculture
    ('Kitchen Gardening and Urban Farming',    'Agriculture'),
    ('Poultry Production',                     'Agriculture'),
    ('Beekeeping and Apiculture',              'Agriculture'),
    ('Dairy Farming Basics',                   'Agriculture'),
    ('Mushroom Farming',                       'Agriculture'),
    # Health
    ('First Aid and Emergency Response',       'Health Sciences'),
    ('Home-Based Care',                        'Health Sciences'),
    # Business
    ('Entrepreneurship Development',           'Business & Commerce'),
    ('Customer Service Skills',                'Business & Commerce'),
    ('Sign Language (Basic)',                  'Social Sciences'),
]


# ─────────────────────────────────────────────────────────────────────────────
# 3. TVET TRADE TESTS
#    NITA Kenya — occupational competency assessment, no formal entry grade
# ─────────────────────────────────────────────────────────────────────────────
TRADE_TESTS = [
    # Construction Trades
    ('Masonry Trade Test',                         'Construction Trades'),
    ('Carpentry and Joinery Trade Test',           'Construction Trades'),
    ('Plumbing Trade Test',                        'Construction Trades'),
    ('Painting and Decoration Trade Test',         'Construction Trades'),
    ('Electrical Installation Trade Test',         'Electrical & Electronics'),
    # Automotive
    ('Motor Vehicle Mechanics Trade Test',         'Automotive'),
    ('Motor Vehicle Body Repair Trade Test',       'Automotive'),
    ('Motorcycle Mechanics Trade Test',            'Automotive'),
    # Engineering & Manufacturing
    ('Welding and Fabrication Trade Test',         'Engineering & Manufacturing'),
    ('General Fitter Trade Test',                  'Engineering & Manufacturing'),
    ('Refrigeration and Air Conditioning Trade Test', 'Engineering & Manufacturing'),
    ('Lathe Machine Operations Trade Test',        'Engineering & Manufacturing'),
    ('CNC Lathe Operations Trade Test',            'Engineering & Manufacturing'),
    # Service Trades
    ('Tailoring and Garment Making Trade Test',    'Service Trades'),
    ('Hairdressing and Beauty Therapy Trade Test', 'Service Trades'),
    ('Food Production Trade Test',                 'Service Trades'),
    # Agriculture
    ('Agricultural Mechanics Trade Test',          'Agriculture'),
    ('Dairy Processing Trade Test',                'Agriculture'),
]


# ─────────────────────────────────────────────────────────────────────────────
# 4. TVET PROFICIENCY
#    KNEC, KASNEB foundation level, and vocational proficiency certificates
# ─────────────────────────────────────────────────────────────────────────────
PROFICIENCY = [
    # Business & Commerce
    ('Business Accounting Proficiency',        'Business & Commerce'),
    ('Bookkeeping Proficiency',                'Business & Commerce'),
    ('Typewriting and Office Practice Proficiency', 'Business & Commerce'),
    ('Stores and Purchasing Proficiency',      'Business & Commerce'),
    ('Secretarial Proficiency',                'Business & Commerce'),
    # Computing & ICT
    ('ICT Proficiency Certificate',            'Computing & ICT'),
    ('Computer Applications Proficiency',      'Computing & ICT'),
    # Engineering & Technology
    ('Electrical Installation Proficiency',    'Engineering & Technology'),
    ('Plumbing and Sanitation Proficiency',    'Engineering & Technology'),
    # Agriculture
    ('Agribusiness Proficiency',               'Agriculture'),
    ('Farm Management Proficiency',            'Agriculture'),
    # Health
    ('Community Health Proficiency',           'Health Sciences'),
    ('First Aid Proficiency',                  'Health Sciences'),
    # Social
    ('Child Care Proficiency',                 'Social Sciences'),
    ('Kenya Sign Language Interpretation Proficiency', 'Social Sciences'),
]


# ─────────────────────────────────────────────────────────────────────────────
# 5. TVET PROFESSIONAL
#    KASNEB, IHRM Kenya, KISM, ICPAK — professional body qualifications
# ─────────────────────────────────────────────────────────────────────────────
PROFESSIONAL = [
    # KASNEB — Accountancy & Finance
    ('Certified Public Accountant Kenya (CPA-K)',               'Accountancy & Finance'),
    ('Accounting Technicians Diploma (ATD)',                    'Accountancy & Finance'),
    ('Certified Investment and Financial Analysts (CIFA)',      'Accountancy & Finance'),
    ('Certified Credit Professional (CCP)',                     'Accountancy & Finance'),
    ('Certified Management Accountant Kenya (CMAK)',            'Accountancy & Finance'),
    # KASNEB — Governance & Secretarial
    ('Certified Secretary Kenya (CS)',                         'Governance & Secretarial'),
    ('Certified Public Secretary Kenya (CPS-K)',               'Governance & Secretarial'),
    # Human Resource
    ('Certified Human Resource Professional (CHRP)',           'Human Resource Management'),
    # Procurement & Supply
    ('Certified Procurement and Supply Professional Kenya (CPSP-K)', 'Procurement & Supply'),
    ('Chartered Institute of Procurement and Supply (CIPS)',   'Procurement & Supply'),
    # ICT & Audit
    ('Certified Information Systems Auditor (CISA)',           'Computing & ICT'),
    ('Certified KASNEB ICT Professional',                      'Computing & ICT'),
    # Engineering
    ('Engineering Technician Registration (IEK)',              'Engineering & Technology'),
    # Health
    ('Pharmacy Technologist Professional Certification',       'Health Sciences'),
]


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND
# ─────────────────────────────────────────────────────────────────────────────
SEEDING_PLAN = [
    ('TVET Certificate (Level 5)', CERTIFICATE_L5, 'D+'),
    ('TVET Short Course',          SHORT_COURSES,  ''),
    ('TVET Trade Test',            TRADE_TESTS,    ''),
    ('TVET Proficiency',           PROFICIENCY,    'D-'),
    ('TVET Professional',          PROFESSIONAL,   'C'),
]


class Command(BaseCommand):
    help = 'Seed Level 5, Short Course, Trade Test, Proficiency, and Professional TVET courses.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete existing courses for these types before re-seeding.'
        )

    def handle(self, *args, **options):
        self.stdout.write('-' * 60)
        self.stdout.write('seed_tvet_remaining — starting')
        self.stdout.write('-' * 60)

        with transaction.atomic():
            for type_name, programmes, min_grade in SEEDING_PLAN:
                ct = CourseType.objects.filter(name=type_name).first()
                if not ct:
                    self.stdout.write(self.style.WARNING(
                        f'  CourseType "{type_name}" not found — skipping (run seed_tvet first)'
                    ))
                    continue

                if options['clear']:
                    n, _ = Course.objects.filter(course_type=ct).delete()
                    CourseCategory.objects.filter(course_type=ct).delete()
                    self.stdout.write(f'  Cleared {n} courses under {type_name}')

                created = self._seed(programmes, ct, min_grade)
                self.stdout.write(self.style.SUCCESS(
                    f'  {type_name}: {created} courses created'
                ))

        self.stdout.write(self.style.SUCCESS('\nDone.'))

    def _seed(self, programmes, course_type, min_grade):
        prefix = SLUG_PREFIX.get(course_type.name, slugify(course_type.name)[:4])
        cat_cache = {}
        created = 0

        for name, sector in programmes:
            if sector not in cat_cache:
                cat_slug = f"{prefix}-{slugify(sector)}"
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
                        f'{course_type.name} — {cat_cache[sector].name}.'
                        + (f' Minimum KCSE mean grade: {min_grade}.' if min_grade else '')
                    ),
                }
            )
            if was_created:
                created += 1

        return created
