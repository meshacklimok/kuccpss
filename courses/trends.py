"""
Ranking queries for the Course Spotlight & Trends homepage section.
Results are cached for 30 minutes — accurate enough, fast enough.
"""
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count
from django.utils import timezone

CACHE_KEY = 'homepage_trends_v1'
CACHE_TTL = 1800  # 30 minutes


def _most_viewed(limit=5):
    from analytics.models import ViewLog
    from .models import Course

    week_ago = timezone.now() - timedelta(days=7)
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
    from .models import CourseOffering, Course
    from django.db.models import Max

    # Find the highest latest_cutoff per course via DB, then hydrate
    top_ids = list(
        CourseOffering.objects
        .exclude(cutoff_points__isnull=True)
        .values('course_id')
        .annotate(max_cutoff=Max('cutoff_points__2024'))
        .order_by('-max_cutoff')
        .values_list('course_id', flat=True)
        [:limit * 3]
    )

    if not top_ids:
        # Fallback to Python-side when JSON key extraction isn't supported
        offerings = list(
            CourseOffering.objects
            .exclude(cutoff_points__isnull=True)
            .select_related('course', 'course__course_type', 'course__category')
        )
        course_max = {}
        for off in offerings:
            lc = off.latest_cutoff()
            if lc is not None:
                cid = off.course_id
                if cid not in course_max or lc > course_max[cid][1]:
                    course_max[cid] = (off.course, lc)
        sorted_pairs = sorted(course_max.values(), key=lambda x: x[1], reverse=True)[:limit]
    else:
        # Compute per-course max in Python from a targeted set
        offerings = list(
            CourseOffering.objects
            .filter(course_id__in=top_ids)
            .exclude(cutoff_points__isnull=True)
            .select_related('course', 'course__course_type', 'course__category')
        )
        course_max = {}
        for off in offerings:
            lc = off.latest_cutoff()
            if lc is not None:
                cid = off.course_id
                if cid not in course_max or lc > course_max[cid][1]:
                    course_max[cid] = (off.course, lc)
        sorted_pairs = sorted(course_max.values(), key=lambda x: x[1], reverse=True)[:limit]

    result = []
    for course, cutoff in sorted_pairs:
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
        c.trend_stat  = str(c.offering_count)
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
        c.trend_stat  = f"{round(c.avg_rating, 1)}★"
        c.trend_label = f"{c.review_count} review{'s' if c.review_count != 1 else ''}"
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
    }
    cache.set(CACHE_KEY, ctx, CACHE_TTL)
    return ctx
