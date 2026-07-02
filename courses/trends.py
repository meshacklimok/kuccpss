"""
Ranking queries for the Course Spotlight & Trends homepage section.
Results are cached for 1 hour — stays reasonably fresh without hammering the DB.
"""
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count
from django.utils import timezone

CACHE_KEY = 'homepage_trends_v1'


def _cache_ttl() -> int:
    from resources.models import SiteSetting
    try:
        return int(SiteSetting.get('trends_cache_ttl', '3600'))
    except (TypeError, ValueError):
        return 3600


def _most_viewed(limit=5):
    from analytics.models import ViewLog
    from .models import Course

    week_ago = timezone.now() - timedelta(days=14)
    rows = list(
        ViewLog.objects
        .filter(content_type='course', created_at__gte=week_ago)
        .values('object_id')
        .annotate(views=Count('id'))
        .order_by('-views')[: limit * 3]
    )
    if not rows:
        return []

    id_list = [r['object_id'] for r in rows]
    view_map = {r['object_id']: r['views'] for r in rows}

    courses = {
        c.pk: c
        for c in Course.objects
        .filter(pk__in=id_list)
        .select_related('course_type', 'category')
    }
    result = []
    for obj_id in id_list:
        c = courses.get(obj_id)
        if c:
            c.trend_stat  = f"{view_map[obj_id]:,}"
            c.trend_label = "views this week"
            c.trend_icon  = "fa-eye"
            c.trend_color = "#2563eb"
            result.append(c)
            if len(result) >= limit:
                break
    return result


def _most_competitive(limit=5):
    from .models import Course, CourseOffering

    # cutoff_points is JSONB — PostgreSQL has no MAX(jsonb), so we resolve
    # the latest cutoff year per offering in Python, then rank. Only the two
    # columns we need are fetched; full Course objects are loaded for the
    # winners alone.
    rows = (
        CourseOffering.objects
        .exclude(cutoff_points__isnull=True)
        .values_list('course_id', 'cutoff_points')
    )
    course_max: dict = {}
    for cid, cutoffs in rows:
        if not cutoffs:
            continue
        latest_year = max(cutoffs.keys())
        lc = cutoffs.get(latest_year)
        if lc is not None and (cid not in course_max or lc > course_max[cid]):
            course_max[cid] = lc

    top = sorted(course_max.items(), key=lambda x: x[1], reverse=True)[:limit]
    courses = {
        c.pk: c
        for c in Course.objects
        .filter(pk__in=[cid for cid, _ in top])
        .select_related('course_type', 'category')
    }

    result = []
    for cid, cutoff in top:
        course = courses.get(cid)
        if course is None:
            continue
        course.trend_stat  = f"{cutoff}"
        course.trend_label = "pts cutoff"
        course.trend_icon  = "fa-fire"
        course.trend_color = "#dc2626"
        result.append(course)
    return result


def _most_offered(limit=5):
    from .models import Course

    courses = list(
        Course.objects
        .annotate(offering_count=Count('offerings'))
        .filter(offering_count__gt=0)
        .order_by('-offering_count')
        .select_related('course_type', 'category')[:limit]
    )
    for c in courses:
        c.trend_stat  = str(c.offering_count)  # type: ignore[attr-defined]
        c.trend_label = "institutions"
        c.trend_icon  = "fa-university"
        c.trend_color = "#059669"
    return courses


def _top_rated(limit=5):
    from .models import Course

    courses = list(
        Course.objects
        .annotate(
            avg_rating=Avg('reviews__rating'),
            review_count=Count('reviews'),
        )
        .filter(review_count__gte=1)
        .order_by('-avg_rating', '-review_count')
        .select_related('course_type', 'category')[:limit]
    )
    for c in courses:
        c.trend_stat  = f"{round(c.avg_rating, 1)}★"  # type: ignore[attr-defined]
        c.trend_label = f"{c.review_count} review{'s' if c.review_count != 1 else ''}"  # type: ignore[attr-defined]
        c.trend_icon  = "fa-star"
        c.trend_color = "#d97706"
    return courses


def get_trends_context():
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    from .models import CourseSpotlight

    ctx = {
        'spotlight':             CourseSpotlight.current(),
        'trending_viewed':       _most_viewed(),
        'trending_competitive':  _most_competitive(),
        'trending_offered':      _most_offered(),
        'trending_rated':        _top_rated(),
        'trends_generated_at':   timezone.now(),
    }
    cache.set(CACHE_KEY, ctx, _cache_ttl())
    return ctx
