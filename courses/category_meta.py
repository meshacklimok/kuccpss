"""
Presentation metadata for course categories (icon, colour, tagline, careers, order).

Keyed by category *name* so the same entry serves Degree and TVET categories.
`rank` puts tech and the most competitive fields first; unknown names sort last.
"""
import re
from collections import defaultdict

from django.core.cache import cache
from django.db.models import Count

from .models import Course, CourseOffering, LATEST_CUTOFF_YEAR
from .programmes import core_name, display_title

CATEGORY_META = {
    'Computing & ICT': {
        'rank': 1, 'icon': 'fa-solid fa-laptop-code', 'color': '#2563eb',
        'tagline': 'Software, data, AI and networks: the fastest-growing jobs in Kenya.',
        'careers': ['Software Engineer', 'Data Analyst', 'Cybersecurity Analyst'],
    },
    'Engineering & Technology': {
        'rank': 2, 'icon': 'fa-solid fa-gears', 'color': '#ea580c',
        'tagline': 'Design and build roads, power, machines and electronics.',
        'careers': ['Civil Engineer', 'Electrical Engineer', 'Mechatronics Engineer'],
    },
    'Health Sciences': {
        'rank': 3, 'icon': 'fa-solid fa-stethoscope', 'color': '#dc2626',
        'tagline': 'Medicine, nursing, pharmacy and clinical care. Some of the highest cutoffs.',
        'careers': ['Doctor', 'Pharmacist', 'Nurse'],
    },
    'General': {
        'rank': 4, 'icon': 'fa-solid fa-scale-balanced', 'color': '#7c3aed',
        'tagline': 'Law (LLB) and other standalone programmes.',
        'careers': ['Advocate', 'Legal Officer', 'Compliance Officer'],
    },
    'Built Environment': {
        'rank': 5, 'icon': 'fa-solid fa-city', 'color': '#0d9488',
        'tagline': 'Architecture, construction, real estate and planning.',
        'careers': ['Architect', 'Quantity Surveyor', 'Urban Planner'],
    },
    'Business & Commerce': {
        'rank': 6, 'icon': 'fa-solid fa-chart-line', 'color': '#d97706',
        'tagline': 'Finance, accounting, actuarial science and management.',
        'careers': ['Accountant', 'Actuary', 'Financial Analyst'],
    },
    'Natural Sciences': {
        'rank': 7, 'icon': 'fa-solid fa-flask', 'color': '#0891b2',
        'tagline': 'Maths, physics, chemistry, biology and statistics.',
        'careers': ['Statistician', 'Lab Scientist', 'Researcher'],
    },
    'Media & Communications': {
        'rank': 8, 'icon': 'fa-solid fa-bullhorn', 'color': '#db2777',
        'tagline': 'Journalism, PR, film and digital media.',
        'careers': ['Journalist', 'PR Officer', 'Content Producer'],
    },
    'Education': {
        'rank': 9, 'icon': 'fa-solid fa-chalkboard-user', 'color': '#16a34a',
        'tagline': 'Train as a secondary school teacher in arts or sciences.',
        'careers': ['Teacher', 'Curriculum Developer', 'Education Officer'],
    },
    'Agriculture & Food Sciences': {
        'rank': 10, 'icon': 'fa-solid fa-seedling', 'color': '#65a30d',
        'tagline': 'Farming, food science, animal health and agribusiness.',
        'careers': ['Agronomist', 'Food Technologist', 'Agribusiness Manager'],
    },
    'Agriculture': {
        'rank': 10, 'icon': 'fa-solid fa-seedling', 'color': '#65a30d',
        'tagline': 'Crop and animal production, agribusiness and extension.',
        'careers': ['Farm Manager', 'Extension Officer', 'Agribusiness Officer'],
    },
    'Social Sciences': {
        'rank': 11, 'icon': 'fa-solid fa-people-group', 'color': '#4f46e5',
        'tagline': 'Psychology, economics, community development and international relations.',
        'careers': ['Counsellor', 'Economist', 'Social Worker'],
    },
    'Arts & Humanities': {
        'rank': 12, 'icon': 'fa-solid fa-feather-pointed', 'color': '#9333ea',
        'tagline': 'Languages, history, theology, music and the arts.',
        'careers': ['Linguist', 'Historian', 'Creative Writer'],
    },
    'Hospitality & Tourism': {
        'rank': 12, 'icon': 'fa-solid fa-bell-concierge', 'color': '#c2410c',
        'tagline': 'Hotels, catering, travel and tour operations.',
        'careers': ['Chef', 'Hotel Manager', 'Tour Consultant'],
    },
    'Fashion & Design': {
        'rank': 13, 'icon': 'fa-solid fa-shirt', 'color': '#be185d',
        'tagline': 'Fashion, textiles, beauty and creative design.',
        'careers': ['Fashion Designer', 'Beauty Therapist', 'Textile Technologist'],
    },
    'Environment & Natural Resources': {
        'rank': 14, 'icon': 'fa-solid fa-leaf', 'color': '#15803d',
        'tagline': 'Environmental science, conservation and earth sciences.',
        'careers': ['Environmental Officer', 'Conservationist', 'Geologist'],
    },
    'Transport & Logistics': {
        'rank': 15, 'icon': 'fa-solid fa-ship', 'color': '#0369a1',
        'tagline': 'Maritime, aviation, supply chain and logistics.',
        'careers': ['Logistics Officer', 'Marine Officer', 'Supply Chain Analyst'],
    },
}

DEFAULT_META = {
    'rank': 99, 'icon': 'fa-solid fa-layer-group', 'color': '#64748b',
    'tagline': '', 'careers': [],
}

# A field counts as "highly competitive" when its top cutoff reaches this (max 48).
COMPETITIVE_CUTOFF = 40.0

_ACRONYM = re.compile(r'\b(Ict|It|Hiv|Gis)\b')


def _chip_label(name):
    core = core_name(name).split(' bachelor ')[0]
    if core in ('laws', 'laws ll b', 'laws llb', 'law'):
        return 'Law (LLB)'
    return _ACRONYM.sub(lambda m: m.group(1).upper(), display_title(core))


def _top_programmes(category, limit=3):
    """Most widely offered programmes in a category, deduped across name variants."""
    courses = (Course.objects.filter(category=category)
               .annotate(k=Count('offerings')).order_by('-k', 'name')[:15])
    seen, out = set(), []
    for c in courses:
        label = _chip_label(c.name)
        key = core_name(label)
        if key in seen or key == 'science':
            continue
        seen.add(key)
        out.append({'label': label, 'q': key})
        if len(out) == limit:
            break
    return out


def enrich_categories(course_type, categories):
    """
    Attach meta + live stats to each category and return them sorted by rank.
    Stats are cached for 15 minutes per course type.
    """
    cache_key = f'course_cat_stats:{course_type.pk}'
    stats = cache.get(cache_key)
    if stats is None:
        stats = defaultdict(dict)
        counts = (Course.objects.filter(course_type=course_type, category__isnull=False)
                  .values('category').annotate(n=Count('id')))
        for row in counts:
            stats[row['category']]['programmes'] = row['n']

        cutoffs = defaultdict(list)
        unis = defaultdict(set)
        for cat_id, inst_id, cp in (CourseOffering.objects
                                    .filter(course__course_type=course_type, course__category__isnull=False)
                                    .values_list('course__category', 'institution', 'cutoff_points')):
            unis[cat_id].add(inst_id)
            v = (cp or {}).get(LATEST_CUTOFF_YEAR)
            try:
                if v is not None:
                    cutoffs[cat_id].append(float(v))
            except (TypeError, ValueError):
                pass

        # Cover every category of the type so one cached entry serves all callers
        for cat in course_type.categories.all():
            s = stats[cat.pk]
            s.setdefault('programmes', 0)
            s['institutions'] = len(unis[cat.pk])
            cs = cutoffs[cat.pk]
            s['top_cutoff'] = round(max(cs), 1) if cs else None
            s['avg_cutoff'] = round(sum(cs) / len(cs), 1) if cs else None
            s['popular'] = _top_programmes(cat)
        stats = dict(stats)
        cache.set(cache_key, stats, 60 * 15)

    for cat in categories:
        cat.meta = CATEGORY_META.get(cat.name, DEFAULT_META)
        s = stats.get(cat.pk, {})
        cat.programmes = s.get('programmes', 0)
        cat.institutions = s.get('institutions', 0)
        cat.top_cutoff = s.get('top_cutoff')
        cat.avg_cutoff = s.get('avg_cutoff')
        cat.popular = s.get('popular', [])
        cat.is_competitive = bool(cat.top_cutoff and cat.top_cutoff >= COMPETITIVE_CUTOFF)
        # Meter width: average cutoff as a share of the 48-point maximum
        cat.cutoff_pct = round(cat.avg_cutoff / 48 * 100) if cat.avg_cutoff else 0

    return sorted(categories, key=lambda c: (c.meta['rank'], -c.programmes, c.name))
