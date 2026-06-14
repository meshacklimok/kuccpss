"""
Keyword-based auto-assignment of unlinked courses to KUCCPS clusters.

Usage:
    python manage.py assign_clusters           # dry run (no saves)
    python manage.py assign_clusters --commit  # actually save

Each unlinked course is matched against priority-ordered keyword rules.
First match wins. Courses are assigned to the primary ('A') sub-cluster
of the matched group, unless a more specific rule provides a code.
"""
import re
from django.core.management.base import BaseCommand
from clusters.models import Cluster
from courses.models import Course


# (primary_cluster_num, sub_cluster_code, [lowercase keywords/phrases])
# Rules are checked IN ORDER — put most specific first to avoid wrong early matches.
# For ties (same cluster_num), the first matching rule's code is used.
RULES = [
    # ── 1 Law ─────────────────────────────────────────────────────────────────
    (1, '1A', ['law', 'llb', 'legal']),

    # ── 13 Medicine, Health & Veterinary ────────────────────────────────────
    (13, '13A', ['medicine and bachelor of surgery', 'mbchb', 'mb.ch.b',
                 'bachelor of medicine']),
    (13, '13B', ['bachelor of pharmacy', 'pharmacy']),
    (13, '13B', ['nursing', 'nurse']),
    (13, '13B', ['physiotherapy', 'occupational therapy']),
    (13, '13B', ['radiography']),
    (13, '13B', ['midwifery']),
    (13, '13B', ['dental technology', 'oral health', 'dentistry']),
    (13, '13C', ['clinical medicine', 'clinical']),
    (13, '13D', ['medical laboratory', 'laboratory science', 'laboratory technology']),
    (13, '13D', ['medical biotechnology']),
    (13, '13D', ['biomedical science', 'biomedical']),
    (13, '13E', ['veterinary']),
    (13, '13F', ['public health', 'environmental health', 'community health',
                 'global health', 'epidemiology', 'health systems', 'health promotion',
                 'paramedic', 'emergency management']),
    (13, '13G', ['health records', 'health information', 'medical social work',
                 'medical microbiology', 'medical engineering']),

    # ── 19 Education ─────────────────────────────────────────────────────────
    (19, '19A', ['bachelor of education (science', 'bachelor of education science',
                 'education (science', 'education science']),
    (19, '19B', ['bachelor of education (arts', 'bachelor of education(arts',
                 'education (arts']),
    (19, '19C', ['education (major accounting', 'education(major accounting',
                 'education (arts - business', 'education - business']),
    (19, '19J', ['education technology', 'education in technology',
                 'technical education']),
    (19, '19K', ['education in physical education', 'physical education']),
    (19, '19A', ['education in special', 'special needs education', 'special education']),
    (19, '19A', ['education (early childhood', 'early childhood', 'education(early']),
    (19, '19A', ['education (library', 'education (home science',
                 'education with guidance', 'education with special',
                 'education (guidance']),
    (19, '19A', ['education']),  # catch-all for education

    # ── 20 Religious & Theology ───────────────────────────────────────────────
    (20, '20A', ['theology', 'divinity', 'religious studies', 'religious',
                 'chaplain', 'inter-cultural', 'biblical', 'pastoral',
                 'church educational', 'islamic', 'religion', 'christian education',
                 'ba in biblical', 'ba in church']),

    # ── 18 Music ──────────────────────────────────────────────────────────────
    (18, '18A', ['music production', 'music theory', 'music']),

    # ── 17 French & German ────────────────────────────────────────────────────
    (17, '17A', ['french', 'german']),

    # ── 5 Engineering & Technology ────────────────────────────────────────────
    (5, '5A', ['aeronautical engineering', 'aerospace engineering',
               'chemical and process engineering', 'civil and structural engineering',
               'civil engineering', 'structural engineering']),
    (5, '5A', ['chemical engineering']),
    (5, '5B', ['electrical and electronic engineering', 'electrical and electronics engineering',
               'electrical & electronic engineering',
               'electrical and telecommunication engineering', 'electronics engineering',
               'energy engineering', 'electrical engineering',
               'electrical & electronic', 'science in electronics',
               'renewable energy technology', 'renewable energy',
               'technology in electrical',
               'mechanical ventilation and air conditioning']),
    (5, '5C', ['computer systems engineering', 'computer and electronic systems',
               'electronics and computer engineering']),
    (5, '5D', ['mechanical and production engineering', 'mechanical engineering',
               'manufacturing engineering', 'industrial engineering',
               'mechatronic engineering', 'mechatronics',
               'automotive technology']),
    (5, '5D', ['materials and metallurgical engineering', 'mining and mineral processing']),
    (5, '5E', ['telecommunications engineering', 'telecommunication engineering']),
    (5, '5F', ['marine engineering', 'maritime', 'water, irrigation',
               'water, sanitation', 'biosystems engineering',
               'geospatial engineering', 'geomatics engineering',
               'instrumentation and control engineering',
               'instrumentation & control engineering',
               'instrumentation & control']),
    (5, '5A', ['engineering physics', 'bachelor of engineering']),

    # ── 7 Computing & IT ─────────────────────────────────────────────────────
    (7, '7A', ['computer science and applied physics', 'computer science and mathematics',
               'science in computer science', 'computer science',
               'information communication technology management',
               'information communication technology',
               'information and communication technology']),
    (7, '7A', ['software development', 'software engineering']),
    (7, '7B', ['information systems', 'business information technology',
               'business information systems', 'information science and knowledge',
               'information sciences', 'information systems and knowledge']),
    (7, '7B', ['applied computing', 'computing and information systems']),
    (7, '7C', ['cyber security', 'information security', 'digital forensics',
               'cloud computing', 'networks and communication systems',
               'data science and analytics', 'data science', 'applied statistics and data']),
    (7, '7A', ['information technology', 'computing']),

    # ── 11 Fashion, Interior & Textile ───────────────────────────────────────
    (11, '11A', ['fashion', 'textile', 'interior design', 'cosmetology', 'beauty science']),

    # ── 12 Sport Science ─────────────────────────────────────────────────────
    (12, '12A', ['sports science', 'sport science', 'exercise physiology',
                 'exercise and sport', 'sport and', 'recreation management',
                 'leisure management']),

    # ── 16 Geography & Related ────────────────────────────────────────────────
    (16, '16A', ['geography and economics', 'geography and gis',
                 'geography', 'geographic information', 'geospatial information science',
                 'geoinformatics', 'geoinformation technology',
                 'urban and regional planning', 'urban planning',
                 'environmental planning', 'spatial planning',
                 'land use management', 'land management', 'regional planning',
                 'real estate management',
                 'environment, lands and sustainable']),

    # ── 4 Geosciences ─────────────────────────────────────────────────────────
    (4, '4A', ['geomatic engineering', 'geomatics and geospatial',
               'geospatial information science and remote sensing',
               'geoinformatics', 'science in geomatics']),
    (4, '4B', ['geology', 'geophysics', 'earth science', 'mineralogy', 'meteorology',
               'hydrology', 'oceanography', 'geoscience', 'mining physics',
               'astronomy', 'astrophysics']),

    # ── 14 History & Archaeology ──────────────────────────────────────────────
    (14, '14A', ['history and archaeology', 'history and economics',
                 'history', 'archaeology']),

    # ── 15 Agriculture & Environment ─────────────────────────────────────────
    (15, '15A', ['bachelor of veterinary medicine']),
    (15, '15B', ['food science and technology', 'food security', 'food, nutrition',
                 'foods, nutrition', 'nutrition and dietetics', 'food operations']),
    (15, '15C', ['agriculture and extension', 'agricultural extension',
                 'agriculture education', 'science in agriculture']),
    (15, '15D', ['animal science', 'animal health', 'animal production',
                 'livestock', 'dairy technology', 'poultry']),
    (15, '15E', ['aquaculture', 'fisheries', 'marine science', 'oceanography']),
    (15, '15F', ['environmental management and conservation',
                 'environmental resource management',
                 'environmental science', 'environmental studies',
                 'environmental economics', 'environmental chemistry',
                 'environmental education', 'environmental technology',
                 'climate change', 'energy and environmental',
                 'sustainable energy', 'bio-resources', 'bioresources']),
    (15, '15G', ['rangeland', 'dryland', 'dry land', 'agroforestry', 'forestry',
                 'horticulture', 'agronomy', 'soil', 'soils', 'crop protection',
                 'crop improvement', 'wildlife management', 'wildlife enterprise',
                 'natural resources', 'land degradation', 'dryland resource',
                 'plant science', 'botany', 'community nutrition', 'nutrition',
                 'leather technology', 'sugar and agro processing',
                 'water resource management', 'water resources and environment',
                 'water and environmental engineering', 'community development and environment']),
    (15, '15A', ['agriculture']),  # catch-all for agriculture

    # ── 9 General & Physical Sciences ────────────────────────────────────────
    (9, '9A', ['biological sciences', 'biology', 'botany', 'zoology',
               'science in biology', 'bio-chemistry', 'biochemistry',
               'science (biochemistry']),
    (9, '9B', ['analytical chemistry', 'applied chemistry', 'polymer chemistry',
               'environmental chemistry', 'chemistry ( inorganic',
               'chemistry']),
    (9, '9C', ['applied physics', 'applied optics', 'optics and lasers',
               'physics with appropriate', 'physics, biology', 'physics',
               'mining physics']),
    (9, '9D', ['genomic', 'microbiology', 'molecular', 'cell biology',
               'immunology', 'laboratory sciences in', 'science (bsc.)',
               'biomedical sciences & technology', 'biosafety',
               'medical microbiology', 'forensic science', 'science in ethnobotany',
               'bsc (science)']),

    # ── 10 Math, Economics, Stats & Related ──────────────────────────────────
    (10, '10A', ['actuarial science', 'actuarial']),
    (10, '10A', ['financial economics', 'economics and mathematics',
                 'mathematics and economics', 'arts in mathematics and economics',
                 'economics']),
    (10, '10B', ['statistics and information technology', 'applied statistics',
                 'statistics and economics', 'science in finance and statistics',
                 'science in statistics', 'statistics']),
    (10, '10C', ['pure mathematics', 'applied mathematics', 'mathematics and modelling',
                 'mathematics and statistics', 'mathematics with computing',
                 'mathematics with it', 'mathematics and computer science',
                 'science in mathematics', 'mathematics ( pure', 'mathematics']),

    # ── 8 Agribusiness ────────────────────────────────────────────────────────
    (8, '8A', ['agribusiness', 'agricultural economics']),

    # ── 6 Architecture & Building ─────────────────────────────────────────────
    (6, '6A', ['architecture']),
    (6, '6B', ['quantity surveying', 'construction management', 'building construction',
               'construction technology', 'building technology', 'civil technology',
               'construction management']),
    (6, '6C', ['property management and real estate', 'real estate',
               'land economics', 'surveying technology']),

    # ── 3 Social Sciences, Media, Arts ───────────────────────────────────────
    (3, '3A', ['journalism', 'mass communication', 'broadcast journalism',
               'communication and public relations', 'communication & public relations',
               'corporate communication', 'science in mass communication',
               'arts in mass media', 'arts in communication', 'media and digital',
               'digital journalism', 'social communication', 'applied communication',
               'communication and journalism', 'communication and media']),
    (3, '3B', ['english and linguistics', 'english and communication', 'arts in english',
               'language and communication', 'arts in language', 'english']),
    (3, '3C', ['kiswahili and geography', 'kiswahili and media', 'kiswahili and communication',
               'arts in kiswahili', 'kiswahili']),
    (3, '3D', ['sociology', 'psychology', 'social work', 'counsell', 'counseling',
               'criminology', 'security studies', 'peace', 'conflict',
               'disaster', 'community development', 'development studies',
               'gender', 'philosophy', 'anthropology', 'political science',
               'political', 'public administration', 'public policy',
               'arts (public administration',
               'human rights', 'governance', 'leadership', 'international relations',
               'diplomacy', 'child care', 'child and youth', 'childcare',
               'social sciences', 'humanitarian', 'justice and peace',
               'conflict resolution', 'refugee', 'social development',
               'arabic language', 'arts in arabic']),
    (3, '3E', ['fine art', 'fine arts', 'graphic', 'animation', 'film',
               'theater', 'theatre', 'performing arts', 'drama', 'cinema',
               'creative arts', 'arts interior design']),
    (3, '3A', ['communication', 'media']),  # generic communication/media fallback
    (3, '3D', ['arts in', 'arts (', 'bachelor of arts']),  # generic arts fallback

    # ── 2 Business, Hospitality & Related ────────────────────────────────────
    (2, '2A', ['business administration', 'business and office management',
               'business management', 'business management and information',
               'business management and it', 'commerce', 'accounting',
               'human resource management', 'human resources management',
               'procurement', 'purchasing', 'supply chain', 'logistics',
               'business information technology', 'business information systems',
               'library and information science', 'library and knowledge',
               'library science', 'information science',
               'entrepreneurship', 'co-operative', 'cooperative',
               'co-operatives', 'project management', 'project planning',
               'secretarial management', 'office administration',
               'management science', 'strategic management',
               'international business', 'marketing', 'financial management',
               'accounting and finance', 'finance']),
    (2, '2B', ['hospitality and tourism', 'hospitality management',
               'hotel management', 'hotel & hospitality', 'hotel and hospitality',
               'catering and hospitality', 'catering & hotel',
               'ecotourism', 'eco-tourism', 'tourism management',
               'travel and tourism', 'tourism and travel', 'tours management',
               'sustainable tourism', 'food service and hospitality',
               'institutional catering', 'hospitality']),
    (2, '2A', ['business', 'management', 'leadership']),  # generic fallback
]


def get_cluster_for_course(name):
    """Return the sub-cluster code for a course name, or None if no match."""
    lower = name.lower()
    for _num, code, keywords in RULES:
        for kw in keywords:
            if kw in lower:
                return code
    return None


class Command(BaseCommand):
    help = 'Keyword-match unlinked courses to KUCCPS sub-clusters'

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            help='Actually save changes (default is dry-run)',
        )

    def handle(self, *args, **options):
        commit = options['commit']
        if not commit:
            self.stdout.write(self.style.WARNING(
                'DRY RUN — pass --commit to save\n'
            ))

        # Build cluster lookup: code -> Cluster object
        cluster_map = {}
        for c in Cluster.objects.all():
            m = re.search(r'\((\d+[A-K])\)', c.name)
            if m:
                cluster_map[m.group(1)] = c

        unlinked = Course.objects.filter(cluster__isnull=True).order_by('name')
        total = unlinked.count()
        self.stdout.write(f'Unlinked courses: {total}\n')

        assigned = []
        unmatched = []

        for course in unlinked:
            code = get_cluster_for_course(course.name)
            if code and code in cluster_map:
                assigned.append((course, cluster_map[code]))
            else:
                unmatched.append(course)

        self.stdout.write(f'Matched: {len(assigned)}  |  Unmatched: {len(unmatched)}\n')

        if commit:
            for course, cluster in assigned:
                course.cluster = cluster
                course.save(update_fields=['cluster'])
            self.stdout.write(self.style.SUCCESS(f'Saved {len(assigned)} assignments.'))
        else:
            # Show sample of what would be assigned
            self.stdout.write('\nSample assignments (first 40):')
            for course, cluster in assigned[:40]:
                m = re.search(r'\((\d+[A-K])\)', cluster.name)
                code = m.group(1) if m else cluster.name
                self.stdout.write(f'  [{code}] {course.name}')

        if unmatched:
            self.stdout.write(f'\nStill unmatched ({len(unmatched)}):')
            for c in unmatched:
                self.stdout.write(f'  {c.name}')
