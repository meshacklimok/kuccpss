"""
Utility to match a course to its JobMarketData record via career_outcomes keywords.
"""
from __future__ import annotations
import re
from functools import lru_cache


def _normalise(text: str) -> str:
    """
    Lowercase, '&' → 'and', punctuation → spaces, collapse whitespace.
    "LL.B." → "ll b", "Bio-Systems" → "bio systems", "Food & Beverage" → "food and beverage".
    """
    text = (text or '').lower().replace('&', ' and ')
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', text).split())


@lru_cache(maxsize=1)
def _build_lookup():
    """
    Returns {normalised_keyword: JobMarketData} built once per process lifetime.
    Process restart (or cache clear) refreshes it.
    """
    from career.models import JobMarketData
    lookup = {}
    for jmd in JobMarketData.objects.all():
        for kw in jmd.keywords_list():
            kw = _normalise(kw)
            if kw:
                lookup.setdefault(kw, jmd)
    return lookup


@lru_cache(maxsize=1)
def _keywords_longest_first():
    return sorted(_build_lookup().items(), key=lambda x: -len(x[0]))


@lru_cache(maxsize=1)
def _by_career_name():
    return {jmd.career_name: jmd for jmd in _build_lookup().values()}


# A diploma/certificate graduate enters the field at technician level, so a
# non-degree course that matches a degree-level career shows the technician
# equivalent's salary instead (e.g. Diploma in Electrical Engineering →
# Electrical Technician, not Electrical Engineer).
NON_DEGREE_EQUIVALENT = {
    'Electrical Engineer':  'Electrical Technician',
    'Mechanical Engineer':  'Mechanical Technician',
    'Civil Engineer':       'Civil Engineering Technician',
    'Chemical Engineer':    'Science Laboratory Technologist',
    'Architect':            'Building Technician',
    'Quantity Surveyor':    'Building Technician',
    'Pharmacist':           'Pharmacy Technician',
    'Lawyer / Advocate':    'Paralegal',
    'Medical Doctor':       'Clinical Officer',
    'Data Scientist':       'ICT Technician',
    'Hotel Manager':        'Catering Technician',
}
# Certificate-level only (diploma holders are hired as junior developers).
CERTIFICATE_EQUIVALENT = {
    'Software Developer': 'ICT Technician',
    'Network Engineer':   'ICT Technician',
}
_CERT_PREFIXES = ('certificate', 'artisan', 'craft', 'grade')


def _level_adjust(course, jmd):
    try:
        type_name = (course.course_type.name or '').lower()
    except Exception:
        return jmd
    if not type_name or type_name == 'degree':
        return jmd
    name = (getattr(course, 'name', '') or '').lower().strip()
    is_cert = 'certificate' in type_name or name.startswith(_CERT_PREFIXES)
    target = NON_DEGREE_EQUIVALENT.get(jmd.career_name)
    if not target and is_cert:
        target = CERTIFICATE_EQUIVALENT.get(jmd.career_name)
    return _by_career_name().get(target, jmd) if target else jmd


def get_jmd_for_course(course) -> 'JobMarketData | None':
    """
    Matches a courses.models.Course to a JobMarketData record.
    Priority: career_outcomes terms (exact) → longest keyword found as whole
    words in the course name. Whole-word matching stops false hits such as
    "vet" in "TVET", "ict" in "conflict" or "mechanic" in "mechanical"; the
    longest-first order lets "clinical medicine" beat "medicine" and
    "primary teacher education" beat "teacher education".
    """
    if not course:
        return None
    lookup = _build_lookup()

    # 1. Exact match on career_outcomes comma terms (highest confidence)
    outcomes_raw = getattr(course, 'career_outcomes', None) or ''
    for term in outcomes_raw.split(','):
        term = _normalise(term)
        if term in lookup:
            return _level_adjust(course, lookup[term])

    # 2. Longest keyword appearing as whole words in the course name.
    name = f" {_normalise(getattr(course, 'name', ''))} "
    for kw, jmd in _keywords_longest_first():
        if f' {kw} ' in name:
            return _level_adjust(course, jmd)

    return None


def get_jmd_lookup():
    """Expose the lookup dict for bulk use in career results view."""
    return _build_lookup()
