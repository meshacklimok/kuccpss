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
    Tries each career_outcome term against the keyword lookup; returns first hit.
    """
    if not course or not getattr(course, 'career_outcomes', None):
        return None
    lookup = _build_lookup()
    outcomes = [o.strip().lower() for o in course.career_outcomes.split(',') if o.strip()]
    # exact keyword match first
    for outcome in outcomes:
        if outcome in lookup:
            return lookup[outcome]
    # partial match fallback
    for outcome in outcomes:
        for kw, jmd in lookup.items():
            if kw in outcome or outcome in kw:
                return jmd
    return None


def get_jmd_lookup():
    """Expose the lookup dict for bulk use in career results view."""
    return _build_lookup()
