from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from .models import InstitutionType, Institution


def institution_types_list(request):
    types = InstitutionType.objects.annotate(inst_count=Count('institutions')).order_by('name')
    # Define a preferred display order and icons/colours
    ORDER = ['Public University', 'Private University', 'KMTC', 'Public TVET', 'Private TVET', 'TTC']
    def sort_key(t):
        try:
            return ORDER.index(t.name)
        except ValueError:
            return len(ORDER)
    types = sorted(types, key=sort_key)
    return render(request, 'institutions/institution_types_list.html', {'types': types})


def institution_type_detail(request, type_slug):
    inst_type = get_object_or_404(InstitutionType, slug=type_slug)
    q = request.GET.get('q', '').strip()

    institutions = inst_type.institutions.annotate(
        course_count=Count('offerings')
    ).order_by('name')

    if q:
        institutions = institutions.filter(name__icontains=q)

    return render(request, 'institutions/institution_type_detail.html', {
        'inst_type': inst_type,
        'institutions': institutions,
        'q': q,
    })


def institution_detail(request, type_slug, institution_slug):
    institution = get_object_or_404(
        Institution,
        slug=institution_slug,
        institution_type__slug=type_slug,
    )

    # Courses offered, grouped by course type in the template
    offerings = (
        institution.offerings
        .select_related('course', 'course__course_type', 'course__category')
        .order_by('course__course_type__name', 'course__category__name', 'course__name')
    )

    # Build grouped structure: {course_type_name: {category_name: [offerings]}}
    grouped = {}
    for offering in offerings:
        ct = offering.course.course_type.name
        cat = offering.course.category.name if offering.course.category else 'General'
        grouped.setdefault(ct, {}).setdefault(cat, []).append(offering)

    return render(request, 'institutions/institution_detail.html', {
        'institution': institution,
        'grouped_offerings': grouped,
        'total_courses': offerings.count(),
    })
