import json
import logging
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_POST
from collections import defaultdict

from .models import CourseType, CourseCategory, Course, CourseOffering, Review, LATEST_CUTOFF_YEAR
from .programmes import find_variations, group_by_programme, search_courses, split_course_name
from kuccpss.seo import course_meta

log = logging.getLogger(__name__)


def _courses_per_page() -> int:
    from resources.models import SiteSetting
    try:
        return int(SiteSetting.get('courses_per_page', '24'))
    except (TypeError, ValueError):
        return 24

COURSE_SORTS = {
    'name': 'A–Z',
    'popular': 'Most offered',
    'cutoff_high': 'Highest cutoff',
    'cutoff_low': 'Lowest cutoff',
}


def _course_cards(qs, q, sort):
    """
    Courses for a listing page as a list, each annotated for the course card:
    n_institutions, cutoff_low/high (LATEST_CUTOFF_YEAR across offerings),
    qualification + title (split from the portal's ALL-CAPS name).
    """
    qs = qs.annotate(n_institutions=Count('offerings'))
    courses = search_courses(q, qs) if q else list(qs.order_by('name'))

    cutoffs = defaultdict(list)
    offerings = CourseOffering.objects.filter(course__in=qs).values_list('course_id', 'cutoff_points')
    for course_id, cp in offerings:
        try:
            cutoffs[course_id].append(float((cp or {})[LATEST_CUTOFF_YEAR]))
        except (KeyError, TypeError, ValueError):
            pass

    for c in courses:
        cs = cutoffs.get(c.pk)
        c.cutoff_low = min(cs) if cs else None
        c.cutoff_high = max(cs) if cs else None
        c.qualification, c.title = split_course_name(c.name)

    # Several portal names can shorten to the same card title; show the official name on those
    seen = defaultdict(int)
    for c in courses:
        seen[(c.qualification, c.title.lower())] += 1
    for c in courses:
        c.show_full_name = seen[(c.qualification, c.title.lower())] > 1

    # Stable sorts keep the relevance/name order as the tiebreak
    if sort == 'popular':
        courses.sort(key=lambda c: -c.n_institutions)
    elif sort == 'cutoff_high':
        courses.sort(key=lambda c: (c.cutoff_high is None, -(c.cutoff_high or 0)))
    elif sort == 'cutoff_low':
        courses.sort(key=lambda c: (c.cutoff_low is None, c.cutoff_low or 0))
    return courses


def _sort_param(request, has_cutoffs=True):
    sort = request.GET.get('sort', 'name')
    if sort not in COURSE_SORTS or (sort.startswith('cutoff') and not has_cutoffs):
        sort = 'name'
    return sort


# ------------------------------
# Course Types List View
# ------------------------------
def course_types_list(request):
    """Course types index, or — with ?q= — programme search grouped KUCCPS-style."""
    q = request.GET.get('q', '').strip()[:80]
    if q:
        return programme_search(request, q)
    return _course_types_index(request)


def programme_search(request, q):
    """
    Search across all course types. Results are grouped by programme, so
    "data science" lists Data Science (with its name variations), then
    Data Science and Analytics, then other programmes containing it.
    """
    qs = Course.objects.select_related('course_type', 'category').annotate(
        n_institutions=Count('offerings')
    )
    type_slug = request.GET.get('type', '')
    if type_slug:
        qs = qs.filter(course_type__slug=type_slug)
    courses = search_courses(q, qs)
    groups = group_by_programme(q, courses)

    type_counts = {}
    for g in groups:
        t = g['course_type']
        type_counts.setdefault(t.slug, {'type': t, 'count': 0})['count'] += 1

    from analytics.utils import log_search
    log_search(request, q, result_count=len(courses))

    return render(request, 'courses/programme_search.html', {
        'q': q,
        'groups': groups,
        'course_count': len(courses),
        'type_filter': type_slug,
        'type_counts': sorted(type_counts.values(), key=lambda x: -x['count']),
    })


@cache_page(60 * 15)  # 15-minute cache — course type list rarely changes
def _course_types_index(request):
    """
    Display all top-level course types grouped: main types (Degree, KMTC, TTC) + TVET levels.
    """
    from django.db.models import Count
    all_types = list(
        CourseType.objects.annotate(course_count=Count('course')).all()
    )
    tvet_types = [t for t in all_types if t.name.startswith('TVET') and t.course_count > 0]

    # Promote TVET Certificate (Level 5) into the main cards with a cleaner label
    cert_tvet = next((t for t in tvet_types if t.slug == 'tvet-certificate-level-5'), None)
    if cert_tvet:
        cert_tvet.display_name = 'Certificate'
        cert_tvet.display_desc = 'TVET Certificate programmes at technical & vocational colleges.'
        tvet_types = [t for t in tvet_types if t.slug != 'tvet-certificate-level-5']

    # Exclude non-TVET types with 0 courses (removes the empty 'Certificate' DB artefact)
    main_types = [t for t in all_types if not t.name.startswith('TVET') and t.course_count > 0]
    if cert_tvet:
        main_types.append(cert_tvet)

    MAIN_ORDER = ['Degree', 'KMTC', 'TTC', 'Certificate']
    main_types.sort(key=lambda t: MAIN_ORDER.index(getattr(t, 'display_name', t.name)) if getattr(t, 'display_name', t.name) in MAIN_ORDER else len(MAIN_ORDER))

    TVET_ORDER = [
        'TVET Diploma (Level 6)',
        'TVET Certificate (Level 5)',
        'TVET Artisan Certificate (Level 4)',
        'TVET Craft Certificate (Level 3)',
    ]
    tvet_types.sort(key=lambda t: TVET_ORDER.index(t.name) if t.name in TVET_ORDER else len(TVET_ORDER))

    total_courses = sum(t.course_count for t in all_types)

    return render(request, 'courses/course_types_list.html', {
        'main_types': main_types,
        'tvet_types': tvet_types,
        'total_courses': total_courses,
    })


# ------------------------------
# Course Type Detail / Categories
# ------------------------------
def course_type_detail(request, type_slug):
    """
    Display all categories under a course type (if any).
    For types without categories (KMTC, TTC, etc.), directly show courses.
    Supports ?q= search + pagination. Returns partial on HTMX requests.
    """
    course_type = CourseType.objects.filter(slug=type_slug).first()
    if course_type is None:
        # Slugs aren't all lowercase (e.g. "KMTC"), so /courses/kmtc/ must still resolve
        course_type = get_object_or_404(CourseType, slug__iexact=type_slug)
        url = reverse('courses:course_type_detail', args=[course_type.slug])
        if request.GET:
            url += '?' + request.GET.urlencode()
        return redirect(url, permanent=True)
    q = request.GET.get('q', '').strip()
    page_num = request.GET.get('page', 1)

    categories = list(course_type.categories.all())
    if categories and not q:
        from .category_meta import enrich_categories
        categories = enrich_categories(course_type, categories)

    page_obj = None
    courses = None
    sort = 'name'
    list_has_cutoffs = False
    if not categories or q:
        qs = Course.objects.filter(course_type=course_type).select_related(
            'course_type', 'category', 'cluster'
        )
        sort = _sort_param(request)
        cards = _course_cards(qs, q, sort)
        list_has_cutoffs = any(c.cutoff_high is not None for c in cards)
        if not list_has_cutoffs and sort.startswith('cutoff'):
            sort = 'name'
        paginator = Paginator(cards, _courses_per_page())
        page_obj = paginator.get_page(page_num)
        courses = page_obj

    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        page_num_int = int(page_num)
    except (ValueError, TypeError):
        page_num_int = 1
    if is_htmx and page_num_int > 1:
        template = 'courses/_course_items_partial.html'
    elif is_htmx:
        template = 'courses/_course_list_partial.html'
    else:
        template = 'courses/course_type_detail.html'

    featured_count = 4 if len(categories) > 6 else 0
    context = {
        'course_type': course_type,
        'categories': categories,
        'featured_categories': categories[:featured_count],
        'other_categories': categories[featured_count:],
        'total_programmes': sum(getattr(c, 'programmes', 0) for c in categories),
        'has_cutoffs': any(getattr(c, 'top_cutoff', None) for c in categories),
        'courses': courses,
        'page_obj': page_obj,
        'q': q,
        'sort': sort,
        'sorts': {k: v for k, v in COURSE_SORTS.items() if list_has_cutoffs or not k.startswith('cutoff')},
    }
    return render(request, template, context)


# ------------------------------
# Course Category Detail
# ------------------------------
def course_category_detail(request, type_slug, category_slug):
    """
    Display all courses under a specific category.
    Falls back to course detail when the slug matches a course rather than a category.
    Supports ?q= search + pagination. Returns partial on HTMX requests.
    """
    try:
        category = CourseCategory.objects.select_related('course_type').get(
            slug=category_slug, course_type__slug=type_slug
        )
    except CourseCategory.DoesNotExist:
        return course_detail(request, type_slug, course_slug=category_slug)

    q = request.GET.get('q', '').strip()
    page_num = request.GET.get('page', 1)

    qs = Course.objects.filter(category=category).select_related(
        'course_type', 'category', 'cluster'
    )
    from .category_meta import enrich_categories
    enrich_categories(category.course_type, [category])
    has_cutoffs = bool(category.top_cutoff)
    sort = _sort_param(request, has_cutoffs)

    paginator = Paginator(_course_cards(qs, q, sort), _courses_per_page())
    page_obj = paginator.get_page(page_num)

    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        page_num_int = int(page_num)
    except (ValueError, TypeError):
        page_num_int = 1
    if is_htmx and page_num_int > 1:
        template = 'courses/_course_items_partial.html'
    elif is_htmx:
        template = 'courses/_course_list_partial.html'
    else:
        template = 'courses/course_category_detail.html'

    context = {
        'category': category,
        'course_type': category.course_type,
        'courses': page_obj,
        'page_obj': page_obj,
        'q': q,
        'sort': sort,
        'sorts': {k: v for k, v in COURSE_SORTS.items() if has_cutoffs or not k.startswith('cutoff')},
        'has_cutoffs': has_cutoffs,
        'hide_category': True,
    }
    return render(request, template, context)


# ------------------------------
# Cutoff trend chart
# ------------------------------
# At most this many institutions are plotted up front; colours are assigned
# per slot in the template (light/dark palettes), so a line keeps its colour.
_TREND_MAX_LINES = 6


def _cutoff_trend(offerings):
    """
    Build the cutoff trend chart for a course from its offerings.

    Plots the top institutions by newest cutoff; every institution with 2+ years
    is sent so the page can add any one of them on demand. Returns None when no
    offering has two years of data.
    """
    # Fixtures may store years as int or str — normalise to str, drop blanks.
    normalised = [(o, {str(k): v for k, v in (o.cutoff_points or {}).items() if v is not None})
                  for o in offerings]
    series = [(o, cp) for o, cp in normalised if len(cp) >= 2]
    if not series:
        return None

    years = sorted({y for _, cp in series for y in cp})
    series.sort(key=lambda t: t[1][max(t[1])], reverse=True)  # newest cutoff first

    def _line(off, cp, role):
        return {
            'label': off.institution.abbreviation or off.institution.name[:22],
            'data': [cp.get(y) for y in years],
            'role': role,
        }

    shown = series[:_TREND_MAX_LINES]
    datasets = [_line(o, cp, i) for i, (o, cp) in enumerate(shown)]

    # Average only over institutions with a value in every year, so a year with
    # fewer published cutoffs (e.g. the latest cycle) doesn't shift the line.
    complete = [cp for _, cp in series if all(y in cp for y in years)]
    if len(complete) >= 2:
        datasets.append({
            'label': f'Average ({len(complete)} institutions)',
            'data': [round(sum(cp[y] for cp in complete) / len(complete), 3) for y in years],
            'role': 'avg',
        })

    extra = [
        {'name': o.institution.name,
         'dataset': _line(o, cp, 'pick')}
        for o, cp in series[len(shown):]
    ]

    rows = [(o, [cp.get(y) for y in reversed(years)]) for o, cp in normalised if cp]

    return {
        'chart_json': json.dumps({'labels': years, 'datasets': datasets, 'extra': extra}),
        'years': list(reversed(years)),
        'rows': rows,
    }


# ------------------------------
# Course Detail View
# ------------------------------
def course_detail(request, type_slug, category_slug=None, course_slug=None):
    """
    Display course details including core subjects, institutions, cut-offs, and PDF (if any)
    """
    _qs = Course.objects.select_related('course_type', 'category', 'cluster')
    if category_slug:
        course = _qs.filter(slug=course_slug, category__slug=category_slug, course_type__slug=type_slug).first()
    else:
        course = _qs.filter(slug=course_slug, course_type__slug=type_slug).first()

    if course is None:
        # Course may have been moved — find by slug and redirect to its actual URL
        course = get_object_or_404(Course, slug=course_slug)
        if course.category:
            return redirect('courses:course_detail', type_slug=course.course_type.slug,
                            category_slug=course.category.slug, course_slug=course_slug)
        return redirect('courses:course_detail_no_category', type_slug=course.course_type.slug,
                        course_slug=course_slug)

    offerings = list(course.offerings.select_related('institution__institution_type').order_by('institution__name'))

    from analytics.utils import log_view
    log_view(request, content_type='course', object_id=course.pk, object_name=course.name)

    trend = _cutoff_trend(offerings)

    is_shortlisted = False
    shortlist_count = 0
    if request.user.is_authenticated:
        from accounts.models import CourseShortlist
        is_shortlisted = CourseShortlist.objects.filter(user=request.user, course=course).exists()
        shortlist_count = CourseShortlist.objects.filter(user=request.user).count()

    reviews_qs = Review.objects.filter(course=course).select_related('user')
    agg = reviews_qs.aggregate(avg=Avg('rating'), total=Count('id'))
    user_review = reviews_qs.filter(user=request.user).first() if request.user.is_authenticated else None

    try:
        from career.job_market import get_jmd_for_course
        job_market = get_jmd_for_course(course)
    except Exception:
        job_market = None

    variations = find_variations(course)

    context = {
        'course': course,
        'offerings': offerings,
        'seo': course_meta(course, offerings),
        'variations': variations,
        'chart_json': trend['chart_json'] if trend else None,
        'trend_years': trend['years'] if trend else [],
        'trend_rows': trend['rows'] if trend else [],
        'is_shortlisted': is_shortlisted,
        'shortlist_count': shortlist_count,
        'reviews': reviews_qs[:20],
        'avg_rating': round(agg['avg'], 1) if agg['avg'] else None,
        'review_count': agg['total'],
        'user_review': user_review,
        'job_market': job_market,
        'expert_mentors': _expert_mentors(),
        'student_mentors': _student_mentors(course),
    }
    return render(request, 'courses/course_detail.html', context)


def _expert_mentors():
    """Live expert mentors (any course), listed after the course's student mentors."""
    from django.db.models import Exists, OuterRef
    from mentorship.models import MentorProfile, TimeSlot, bookable_slots_q
    return list(
        MentorProfile.objects.filter(
            mentor_type=MentorProfile.EXPERT, is_approved=True, is_active=True,
        ).select_related('user')
        .annotate(has_open_slot=Exists(TimeSlot.objects.filter(bookable_slots_q(), mentor=OuterRef('pk'))))
        .order_by('display_order', '-average_rating', 'pk')[:3]
    )


def _student_mentors(course):
    """Student mentors in this course or a close name variation, listed first."""
    from mentorship.matching import student_mentors_for_course
    return student_mentors_for_course(course)


@login_required
@require_POST
def submit_course_review(request, type_slug, category_slug=None, course_slug=None):
    course = get_object_or_404(Course, slug=course_slug)
    try:
        rating = int(request.POST.get('rating', 0))
    except (ValueError, TypeError):
        rating = 0
    if not 1 <= rating <= 5:
        return JsonResponse({'error': 'Invalid rating'}, status=400)
    body = request.POST.get('body', '').strip()[:280]
    Review.objects.update_or_create(
        user=request.user, course=course,
        defaults={'rating': rating, 'body': body},
    )
    agg = Review.objects.filter(course=course).aggregate(avg=Avg('rating'), total=Count('id'))
    return JsonResponse({
        'avg': round(agg['avg'], 1) if agg['avg'] else rating,
        'total': agg['total'],
    })