"""
Utility to match a course to its JobMarketData record via career_outcomes keywords.
"""
from __future__ import annotations
from functools import lru_cache


@lru_cache(maxsize=1)
def _build_lookup():
    """
    Returns {keyword_lower: JobMarketData} built once per process lifetime.
    Process restart (or cache clear) refreshes it.
    """
    from career.models import JobMarketData
    lookup = {}
    for jmd in JobMarketData.objects.all():
        for kw in jmd.keywords_list():
            lookup.setdefault(kw, jmd)
    return lookup


def get_jmd_for_course(course) -> 'JobMarketData | None':
    """
    Matches a courses.models.Course to a JobMarketData record.
    Priority: career_outcomes keywords → course name → category name.
    """
    if not course:
        return None
    lookup = _build_lookup()

    outcomes_raw = getattr(course, 'career_outcomes', None) or ''
    name_lower = (getattr(course, 'name', '') or '').lower()

    try:
        cat_name = (course.category.name or '').lower()
    except Exception:
        cat_name = ''

    # 1. Exact match on career_outcomes comma terms (highest confidence)
    if outcomes_raw:
        for term in (o.strip().lower() for o in outcomes_raw.split(',') if o.strip()):
            if term in lookup:
                return lookup[term]

    # 2. Exact match on individual words of the course name
    for word in name_lower.split():
        if word in lookup:
            return lookup[word]

    # 3. Partial match: keyword found inside the full course name or category.
    # Strip punctuation so "LL.B." → "llb", "bio-systems" → "biosystems".
    import re as _re
    search_text = _re.sub(r'[^a-z0-9 ]', '', name_lower + ' ' + cat_name)
    for kw, jmd in sorted(lookup.items(), key=lambda x: -len(x[0])):
        if len(kw) >= 3 and kw in search_text:
            return jmd

    return None


def get_jmd_lookup():
    """Expose the lookup dict for bulk use in career results view."""
    return _build_lookup()
