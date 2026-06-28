import json
import logging
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_POST
from .models import CourseType, CourseCategory, Course, Review

log = logging.getLogger(__name__)

COURSES_PER_PAGE = 24

# ------------------------------
# Course Types List View
# ------------------------------
@cache_page(60 * 15)  # 15-minute cache — course type list rarely changes
def course_types_list(request):
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
        'TVET Short Course',
        'TVET Trade Test',
        'TVET Proficiency',
        'TVET Professional',
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
    course_type = get_object_or_404(CourseType, slug=type_slug)
    q = request.GET.get('q', '').strip()
    page_num = request.GET.get('page', 1)

    categories = list(course_type.categories.all())

    page_obj = None
    courses = None
    if not categories or q:
        qs = Course.objects.filter(course_type=course_type).select_related(
            'course_type', 'category', 'cluster'
        )
        if q:
            from django.db.models import Q as _Q
            f = _Q(name__icontains=q)
            for tok in q.split():
                if len(tok) >= 3:
                    f |= _Q(name__icontains=tok)
            qs = qs.filter(f)
        qs = qs.order_by('name')
        paginator = Paginator(qs, COURSES_PER_PAGE)
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

    context = {
        'course_type': course_type,
        'categories': categories,
        'courses': courses,
        'page_obj': page_obj,
        'q': q,
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
    if q:
        from django.db.models import Q as _Q
        f = _Q(name__icontains=q)
        for tok in q.split():
            if len(tok) >= 3:
                f |= _Q(name__icontains=tok)
        qs = qs.filter(f)
    qs = qs.order_by('name')

    paginator = Paginator(qs, COURSES_PER_PAGE)
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
    }
    return render(request, template, context)


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

    offerings = list(course.offerings.select_related('institution').order_by('institution__name'))

    from analytics.utils import log_view
    log_view(request, content_type='course', object_id=course.pk, object_name=course.name)

    # ── Cutoff trend chart ────────────────────────────────────────────────────
    chart_json = None
    _PALETTE = ['#1e3a8a', '#7c3aed', '#16a34a', '#d97706', '#dc2626', '#0891b2', '#db2777']

    try:
        # Normalize cutoff_points keys to strings — JSON fixtures may store years as int or str
        def _norm_cp(cp):
            return {str(k): v for k, v in cp.items()} if cp else {}

        has_data = [(o, _norm_cp(o.cutoff_points)) for o in offerings
                    if o.cutoff_points and len(o.cutoff_points) >= 2]
        if has_data:
            all_years = set()
            for _, cp in has_data:
                all_years.update(cp.keys())
            years = sorted(all_years)

            top = sorted(has_data, key=lambda t: t[0].latest_cutoff() or 0, reverse=True)[:6]
            datasets = []
            for i, (off, cp) in enumerate(top):
                datasets.append({
                    'label': off.institution.abbreviation or off.institution.name[:22],
                    'data': [cp.get(y) for y in years],
                    'borderColor': _PALETTE[i % len(_PALETTE)],
                    'backgroundColor': _PALETTE[i % len(_PALETTE)] + '18',
                    'tension': 0.38,
                    'pointRadius': 5,
                    'pointHoverRadius': 7,
                    'borderWidth': 2.5,
                    'fill': False,
                })

            if len(has_data) > 1:
                avg = []
                for y in years:
                    vals = [cp.get(y) for _, cp in has_data if cp.get(y) is not None]
                    avg.append(round(sum(vals) / len(vals), 1) if vals else None)
                datasets.append({
                    'label': 'Average',
                    'data': avg,
                    'borderColor': '#94a3b8',
                    'backgroundColor': 'transparent',
                    'borderDash': [6, 3],
                    'tension': 0.38,
                    'pointRadius': 3,
                    'pointHoverRadius': 5,
                    'borderWidth': 2,
                    'fill': False,
                })

            chart_json = json.dumps({'labels': years, 'datasets': datasets})
    except Exception:
        chart_json = None

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

    context = {
        'course': course,
        'offerings': offerings,
        'chart_json': chart_json,
        'is_shortlisted': is_shortlisted,
        'shortlist_count': shortlist_count,
        'reviews': reviews_qs[:20],
        'avg_rating': round(agg['avg'], 1) if agg['avg'] else None,
        'review_count': agg['total'],
        'user_review': user_review,
        'job_market': job_market,
    }
    return render(request, 'courses/course_detail.html', context)


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