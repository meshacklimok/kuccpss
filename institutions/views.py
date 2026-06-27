from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_POST
from courses.models import Review
from .models import InstitutionType, Institution, InstitutionPromotion

INSTITUTIONS_PER_PAGE = 24


@cache_page(60 * 15)  # 15-minute cache — institution type list rarely changes
def institution_types_list(request):
    types = InstitutionType.objects.annotate(inst_count=Count('institutions')).order_by('name')
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
    page_num = request.GET.get('page', 1)

    institutions = inst_type.institutions.annotate(
        course_count=Count('offerings')
    ).order_by('name')

    if q:
        from django.db.models import Q as _Q
        f = _Q(name__icontains=q) | _Q(abbreviation__icontains=q)
        for tok in q.split():
            if len(tok) >= 3:
                f |= _Q(name__icontains=tok)
        institutions = institutions.filter(f)

    # IDs of currently-live promoted institutions in this type
    today = date.today()
    sponsored_ids = set(
        InstitutionPromotion.objects.filter(
            start_date__lte=today, end_date__gte=today,
            institution__institution_type=inst_type,
        ).values_list('institution_id', flat=True)
    )

    # Sort: sponsored first, then alphabetically, then paginate
    inst_list = sorted(institutions, key=lambda i: (0 if i.pk in sponsored_ids else 1, i.name))
    paginator = Paginator(inst_list, INSTITUTIONS_PER_PAGE)
    page_obj = paginator.get_page(page_num)

    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        page_num_int = int(page_num)
    except (ValueError, TypeError):
        page_num_int = 1
    if is_htmx and page_num_int > 1:
        template = 'institutions/_institution_items_partial.html'
    elif is_htmx:
        template = 'institutions/_institution_list_partial.html'
    else:
        template = 'institutions/institution_type_detail.html'

    return render(request, template, {
        'inst_type': inst_type,
        'institutions': page_obj,
        'page_obj': page_obj,
        'sponsored_ids': sponsored_ids,
        'q': q,
    })


def institution_detail(request, type_slug, institution_slug):
    institution = get_object_or_404(
        Institution.objects.select_related('institution_type'),
        slug=institution_slug,
        institution_type__slug=type_slug,
    )

    offerings = (
        institution.offerings
        .select_related('course', 'course__course_type', 'course__category')
        .order_by('course__course_type__name', 'course__category__name', 'course__name')
    )

    grouped = {}
    for offering in offerings:
        ct = offering.course.course_type.name
        cat = offering.course.category.name if offering.course.category else 'General'
        grouped.setdefault(ct, {}).setdefault(cat, []).append(offering)

    from analytics.utils import log_view
    log_view(request, content_type='institution', object_id=institution.pk, object_name=institution.name)

    reviews_qs = Review.objects.filter(institution=institution).select_related('user')
    agg = reviews_qs.aggregate(avg=Avg('rating'), total=Count('id'))
    user_review = reviews_qs.filter(user=request.user).first() if request.user.is_authenticated else None

    return render(request, 'institutions/institution_detail.html', {
        'institution': institution,
        'grouped_offerings': grouped,
        'total_courses': offerings.count(),
        'reviews': reviews_qs[:20],
        'avg_rating': round(agg['avg'], 1) if agg['avg'] else None,
        'review_count': agg['total'],
        'user_review': user_review,
    })


@login_required
@require_POST
def submit_institution_review(request, type_slug, institution_slug):
    institution = get_object_or_404(Institution, slug=institution_slug)
    try:
        rating = int(request.POST.get('rating', 0))
    except (ValueError, TypeError):
        rating = 0
    if not 1 <= rating <= 5:
        return JsonResponse({'error': 'Invalid rating'}, status=400)
    body = request.POST.get('body', '').strip()[:280]
    Review.objects.update_or_create(
        user=request.user, institution=institution,
        defaults={'rating': rating, 'body': body},
    )
    agg = Review.objects.filter(institution=institution).aggregate(avg=Avg('rating'), total=Count('id'))
    return JsonResponse({
        'avg': round(agg['avg'], 1) if agg['avg'] else rating,
        'total': agg['total'],
    })
