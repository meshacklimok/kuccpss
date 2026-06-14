from django.shortcuts import render, get_object_or_404, redirect
from .models import CourseType, CourseCategory, Course

# ------------------------------
# Course Types List View
# ------------------------------
def course_types_list(request):
    """
    Display all top-level course types grouped: main types (Degree, KMTC, TTC) + TVET levels.
    """
    all_types = list(CourseType.objects.all())
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

    return render(request, 'courses/course_types_list.html', {
        'main_types': main_types,
        'tvet_types': tvet_types,
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
            qs = qs.filter(name__icontains=q)
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
        courses = courses.filter(name__icontains=q)
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

    offerings = course.offerings.select_related('institution').order_by('institution__name')

    context = {
        'course': course,
        'offerings': offerings,
    }
    return render(request, 'courses/course_detail.html', context)