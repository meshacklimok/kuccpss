"""
Process-wide, read-only cache of CourseOffering rows for the career engine.

Every results page used to load ~2,000-4,500 offerings (with course, institution,
cluster, category and type) and then keep a pickled copy of the matches in Redis
per student session. Building those objects costs far more than the eligibility
logic, and the per-session copies (2-5 MB each) would exhaust Redis memory at
results-day traffic. The catalogue is identical for every student, so each worker
loads it once per course type and shares it.

Rules for callers:
  * Treat the returned offerings (and their course/institution/cluster objects) as
    read-only. Put per-request data in your own dicts, never on the model objects.
  * Course data changes are picked up via VERSION_KEY, bumped on model save/delete
    (see courses.apps) and by import_kuccps_portal. Bulk writes that skip signals
    (queryset.update, bulk_create) show up within _TTL seconds, or call
    bump_version() after them.
"""
import threading
import time

from django.core.cache import cache

VERSION_KEY = 'course_catalogue_version'
_TTL = 15 * 60

DEGREE_RELATED = (
    'course', 'course__cluster', 'course__category', 'course__course_type',
    'institution', 'institution__institution_type',
)
TYPED_RELATED = (
    'course', 'course__course_type', 'course__category',
    'institution', 'institution__institution_type',
)

_lock = threading.Lock()
_store = {}  # key -> (version, loaded_at, offerings)


def version():
    try:
        return cache.get(VERSION_KEY) or 0
    except Exception:
        return 0  # cache down: fall back to the TTL


def bump_version(**_kwargs):
    """Invalidate every worker's catalogue. Usable directly as a signal receiver."""
    try:
        cache.set(VERSION_KEY, time.time_ns(), None)
    except Exception:
        pass


def _share_related(offerings):
    """select_related builds a separate Course/Institution per row; keep one of each."""
    courses, institutions = {}, {}
    for o in offerings:
        o.course = courses.setdefault(o.course_id, o.course)
        o.institution = institutions.setdefault(o.institution_id, o.institution)
    return offerings


def _get(key, build_queryset):
    ver = version()
    hit = _store.get(key)
    if hit and hit[0] == ver and time.monotonic() - hit[1] < _TTL:
        return hit[2]
    with _lock:
        hit = _store.get(key)  # another thread may have rebuilt it while we waited
        if hit and hit[0] == ver and time.monotonic() - hit[1] < _TTL:
            return hit[2]
        offerings = tuple(_share_related(list(build_queryset())))
        _store[key] = (ver, time.monotonic(), offerings)
        return offerings


def degree_offerings(degree_type):
    """Degree offerings that have at least one cutoff on record."""
    from .models import CourseOffering
    return _get(('degree', degree_type.pk), lambda: (
        CourseOffering.objects
        .filter(course__course_type=degree_type)
        .exclude(cutoff_points__isnull=True)
        .select_related(*DEGREE_RELATED)
    ))


def start_warmer():
    """Load every pathway's catalogue in a background thread, so the first student on a
    freshly started (or max_requests-recycled) gunicorn worker doesn't pay for it."""
    def _warm():
        from django.db import connection
        try:
            from career.views import COURSE_TYPE_MAP, _get_degree_course_type
            degree_type = _get_degree_course_type()
            if degree_type:
                degree_offerings(degree_type)
            for type_names in COURSE_TYPE_MAP.values():
                typed_offerings(type_names)
        except Exception:
            pass  # requests load it on demand instead
        finally:
            connection.close()
    threading.Thread(target=_warm, name='course-catalogue-warmer', daemon=True).start()


def typed_offerings(type_names):
    """Offerings whose course type name is in type_names (Diploma, KMTC, TTC, ...)."""
    from .models import CourseOffering
    names = tuple(sorted(type_names))
    return _get(('types', names), lambda: (
        CourseOffering.objects
        .filter(course__course_type__name__in=names)
        .select_related(*TYPED_RELATED)
    ))
