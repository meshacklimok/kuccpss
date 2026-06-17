import json
from django.shortcuts import render, get_object_or_404, redirect
from .models import CourseType, CourseCategory, Course

# ------------------------------
# Course Types List View
# ------------------------------
def course_types_list(request):
    """
    Display all top-level course types grouped: main types (Degree, KMTC, TTC) + TVET levels.
    """
    from django.db.models import Count
    all_types = list(
        CourseType.objects.annotate(course_count=Count('course')).all()
    )
    tvet_types = [t for t in all_types if t.name.startswith('TVET')]
    main_types = [t for t in all_types if not t.name.startswith('TVET')]

    MAIN_ORDER = ['Degree', 'KMTC', 'TTC']
    main_types.sort(key=lambda t: MAIN_ORDER.index(t.name) if t.name in MAIN_ORDER else len(MAIN_ORDER))

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
    Supports ?q= search filtering.
    """
    course_type = get_object_or_404(CourseType, slug=type_slug)
    q = request.GET.get('q', '').strip()

    categories = course_type.categories.all()

    courses = None
    if not categories.exists() or q:
        qs = Course.objects.filter(course_type=course_type)
        if q:
            from django.db.models import Q as _Q
            f = _Q(name__icontains=q)
            for tok in q.split():
                if len(tok) >= 3:
                    f |= _Q(name__icontains=tok)
            qs = qs.filter(f)
        courses = qs.order_by('name')

    context = {
        'course_type': course_type,
        'categories': categories,
        'courses': courses,
        'q': q,
    }
    return render(request, 'courses/course_type_detail.html', context)


# ------------------------------
# Course Category Detail
# ------------------------------
def course_category_detail(request, type_slug, category_slug):
    """
    Display all courses under a specific category.
    Falls back to course detail when the slug matches a course rather than a category.
    Supports ?q= search filtering.
    """
    try:
        category = CourseCategory.objects.get(slug=category_slug, course_type__slug=type_slug)
    except CourseCategory.DoesNotExist:
        return course_detail(request, type_slug, course_slug=category_slug)

    q = request.GET.get('q', '').strip()
    courses = Course.objects.filter(category=category)
    if q:
        from django.db.models import Q as _Q
        f = _Q(name__icontains=q)
        for tok in q.split():
            if len(tok) >= 3:
                f |= _Q(name__icontains=tok)
        courses = courses.filter(f)
    courses = courses.order_by('name')

    context = {
        'category': category,
        'course_type': category.course_type,
        'courses': courses,
        'q': q,
    }
    return render(request, 'courses/course_category_detail.html', context)


# ------------------------------
# Course Detail View
# ------------------------------
def course_detail(request, type_slug, category_slug=None, course_slug=None):
    """
    Display course details including core subjects, institutions, cut-offs, and PDF (if any)
    """
    if category_slug:
        course = Course.objects.filter(slug=course_slug, category__slug=category_slug, course_type__slug=type_slug).first()
    else:
        course = Course.objects.filter(slug=course_slug, course_type__slug=type_slug).first()

    if course is None:
        # Course may have been moved to a different type — find by slug alone and redirect
        course = get_object_or_404(Course, slug=course_slug)
        if category_slug:
            return redirect('courses:course_detail', type_slug=course.course_type.slug,
                            category_slug=category_slug, course_slug=course_slug)
        return redirect('courses:course_detail_no_category', type_slug=course.course_type.slug,
                        course_slug=course_slug)

    offerings = list(course.offerings.select_related('institution').order_by('institution__name'))

    from analytics.utils import log_view
    log_view(request, content_type='course', object_id=course.pk, object_name=course.name)

    # ── Cutoff trend chart ────────────────────────────────────────────────────
    chart_json = None
    _PALETTE = ['#1e3a8a', '#7c3aed', '#16a34a', '#d97706', '#dc2626', '#0891b2', '#db2777']

    has_data = [o for o in offerings if o.cutoff_points and len(o.cutoff_points) >= 2]
    if has_data:
        all_years = set()
        for o in has_data:
            all_years.update(o.cutoff_points.keys())
        years = sorted(all_years)

        top = sorted(has_data, key=lambda o: o.latest_cutoff() or 0, reverse=True)[:6]
        datasets = []
        for i, off in enumerate(top):
            datasets.append({
                'label': off.institution.abbreviation or off.institution.name[:22],
                'data': [off.cutoff_points.get(y) for y in years],
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
                vals = [o.cutoff_points[y] for o in has_data if o.cutoff_points.get(y) is not None]
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

    is_shortlisted = False
    shortlist_count = 0
    if request.user.is_authenticated:
        from accounts.models import CourseShortlist
        is_shortlisted = CourseShortlist.objects.filter(user=request.user, course=course).exists()
        shortlist_count = CourseShortlist.objects.filter(user=request.user).count()

    context = {
        'course': course,
        'offerings': offerings,
        'chart_json': chart_json,
        'is_shortlisted': is_shortlisted,
        'shortlist_count': shortlist_count,
    }
    return render(request, 'courses/course_detail.html', context)