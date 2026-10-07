from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Case, Count, IntegerField, When
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_POST
from courses.models import Review
from .models import InstitutionType, Institution, InstitutionPromotion
from kuccpss.seo import institution_meta

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

    # Annotate sponsored flag in DB so sorting happens at the DB level, not in Python
    institutions = institutions.annotate(
        is_sponsored=Case(
            When(pk__in=sponsored_ids, then=0),
            default=1,
            output_field=IntegerField(),
        )
    ).order_by('is_sponsored', 'name')

    paginator = Paginator(institutions, INSTITUTIONS_PER_PAGE)
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


_TYPE_ORDER = [
    'Degree', 'Diploma', 'KMTC', 'TTC',
    'TVET Diploma (Level 6)', 'TVET Certificate (Level 5)',
    'TVET Artisan Certificate (Level 4)', 'TVET Craft Certificate (Level 3)',
]


def _group_offerings(offerings):
    """
    Group an institution's offerings course type → category for the detail page,
    ordered like the course pages (tech/competitive fields first). Each offering
    gets qualification/title/cutoff/cutoff_pct for its row.
    Returns (groups, list of latest-year cutoffs).
    """
    from courses.category_meta import CATEGORY_META, DEFAULT_META
    from courses.programmes import split_course_name

    types = {}
    cutoffs = []
    for o in offerings:
        course = o.course
        o.qualification, o.title = split_course_name(course.name)
        try:
            o.cutoff = float(o.latest_cutoff()) if o.latest_cutoff() is not None else None
        except (TypeError, ValueError):
            o.cutoff = None
        if o.cutoff is not None:
            cutoffs.append(o.cutoff)
            o.cutoff_pct = round(o.cutoff / 48 * 100)
        cat_name = course.category.name if course.category else 'Other programmes'
        t = types.setdefault(course.course_type.name, {'name': course.course_type.name, 'cats': {}})
        cat = t['cats'].setdefault(cat_name, {
            'name': cat_name,
            'meta': CATEGORY_META.get(cat_name, DEFAULT_META),
            'offerings': [],
        })
        cat['offerings'].append(o)

    def type_key(name):
        if name in _TYPE_ORDER:
            return (_TYPE_ORDER.index(name), name)
        return (len(_TYPE_ORDER), name)

    groups = []
    for name in sorted(types, key=type_key):
        cats = sorted(types[name]['cats'].values(), key=lambda c: (c['meta']['rank'], c['name']))
        groups.append({
            'name': name,
            'categories': cats,
            'count': sum(len(c['offerings']) for c in cats),
        })
    return groups, cutoffs


def institution_detail(request, type_slug, institution_slug):
    institution = get_object_or_404(
        Institution.objects.select_related('institution_type'),
        slug=institution_slug,
        institution_type__slug=type_slug,
    )

    offerings = list(
        institution.offerings
        .select_related('course', 'course__course_type', 'course__category', 'course__cluster')
        .order_by('course__name')
    )
    groups, cutoffs = _group_offerings(offerings)

    from analytics.utils import log_view
    log_view(request, content_type='institution', object_id=institution.pk, object_name=institution.name)

    reviews_qs = Review.objects.filter(institution=institution).select_related('user')
    agg = reviews_qs.aggregate(avg=Avg('rating'), total=Count('id'))
    user_review = reviews_qs.filter(user=request.user).first() if request.user.is_authenticated else None

    return render(request, 'institutions/institution_detail.html', {
        'institution': institution,
        'course_groups': groups,
        'total_courses': len(offerings),
        'field_count': sum(len(g['categories']) for g in groups),
        'cutoff_low': min(cutoffs) if cutoffs else None,
        'cutoff_high': max(cutoffs) if cutoffs else None,
        'seo': institution_meta(institution, len(offerings)),
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
