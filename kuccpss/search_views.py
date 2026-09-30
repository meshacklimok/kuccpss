"""
Global search suggest API — returns JSON for the navbar autocomplete.

Scoring logic (highest wins):
  100  exact substring in name
   98  exact abbreviation match  (e.g. query "JKUAT" == inst.abbreviation)
   95  generated acronym match   (e.g. query "UoN"  == first-letters of "University of Nairobi")
   85  abbreviation startswith query
   82  any word in name starts with query
   75  generated acronym starts with query
   70  multi-word query — all tokens found in name
   55  difflib ratio > 0.75 on full name
   45  difflib ratio > 0.80 on individual words
    0  no match → excluded from results
"""

from difflib import SequenceMatcher
from urllib.parse import quote
from django.http import JsonResponse
from django.db.models import Q

# Words ignored when building an acronym
_STOP = frozenset({'of', 'and', 'the', 'for', 'in', 'at', 'to', 'a', 'an', '&'})


def _acronym(text: str) -> str:
    """'University of Nairobi' → 'uon'  |  'JKUAT' → 'jkuat' (already an acronym)"""
    words = text.split()
    letters = [w[0] for w in words if w and w.lower() not in _STOP]
    return ''.join(letters).lower()


def _score(query: str, name: str, abbr: str = '') -> int:
    q = query.lower().strip()
    n = name.lower()
    a = abbr.lower() if abbr else ''

    if not q:
        return 0

    # 1. Exact substring
    if q in n:
        return 100 if (n.startswith(q) or f' {q}' in n) else 90

    # 2. Exact abbreviation
    if a and q == a:
        return 98

    # 3. Generated acronym exact match
    acr = _acronym(name)
    if q == acr:
        return 95

    # 4. Abbreviation prefix
    if a and a.startswith(q) and len(q) >= 2:
        return 85

    # 5. Any word in name starts with query
    words = n.split()
    if any(w.startswith(q) for w in words):
        return 82

    # 6. Generated acronym prefix
    if acr.startswith(q) and len(q) >= 2:
        return 75

    # 7. All query tokens found somewhere in name
    q_tokens = [t for t in q.split() if len(t) >= 2]
    if len(q_tokens) > 1:
        matched = sum(1 for qt in q_tokens if any(qt in w or w.startswith(qt) for w in words))
        if matched == len(q_tokens):
            return 70
        if matched > 0:
            return 40 + matched * 8

    # 8. Fuzzy: whole query vs full name
    ratio = SequenceMatcher(None, q, n).ratio()
    if ratio > 0.75:
        return int(ratio * 70)

    # 9. Fuzzy: query vs individual words (handles single-word typos)
    best = max(
        (SequenceMatcher(None, q, w).ratio() for w in words if abs(len(w) - len(q)) <= 3),
        default=0,
    )
    if best > 0.80:
        return int(best * 58)

    return 0


def api_search_suggest(request):
    from courses.models import Course
    from institutions.models import Institution

    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'courses': [], 'institutions': []})

    prefix = q[:4]          # first 4 chars — cast a wide net at the DB level
    is_short = len(q) <= 5  # could be an acronym like "UoN", "KMTC", "BSc"

    # ── Institution candidates ────────────────────────────────────────────────
    inst_qs = Institution.objects.select_related('institution_type').filter(
        Q(name__icontains=prefix)
        | Q(abbreviation__icontains=q)
        | Q(name__icontains=q)
    ).values('id', 'name', 'abbreviation', 'slug', 'institution_type__slug', 'location')[:60]

    inst_candidates = list(inst_qs)

    # ── Course candidates ─────────────────────────────────────────────────────
    course_qs = Course.objects.select_related('course_type', 'category').filter(
        Q(name__icontains=prefix) | Q(name__icontains=q)
    ).values('id', 'name', 'slug', 'course_type__name', 'course_type__slug', 'category__slug')[:150]

    course_candidates = list(course_qs)

    # Acronym fallback: short query with few DB hits → score all courses
    if is_short and len(course_candidates) < 4:
        course_candidates = list(
            Course.objects.select_related('course_type', 'category')
            .values('id', 'name', 'slug', 'course_type__name', 'course_type__slug', 'category__slug')
            [:300]
        )

    # ── Score & deduplicate ───────────────────────────────────────────────────
    THRESHOLD = 30

    scored_insts = []
    for i in inst_candidates:
        s = _score(q, i['name'], i.get('abbreviation') or '')
        if s >= THRESHOLD:
            scored_insts.append((s, i))
    scored_insts.sort(key=lambda x: -x[0])

    seen_course_names: set = set()
    scored_courses = []
    for c in course_candidates:
        s = _score(q, c['name'])
        if s >= THRESHOLD and c['name'] not in seen_course_names:
            seen_course_names.add(c['name'])
            scored_courses.append((s, c))
    scored_courses.sort(key=lambda x: -x[0])

    # ── Build response ────────────────────────────────────────────────────────
    inst_out = []
    for _, i in scored_insts[:3]:
        inst_out.append({
            'name': i['name'],
            'abbr': i.get('abbreviation') or '',
            'location': i.get('location') or '',
            'url': f"/institutions/{i['institution_type__slug']}/{i['slug']}/",
        })

    course_out = []
    for _, c in scored_courses[:5]:
        type_slug = c['course_type__slug'] or ''
        cat_slug  = c.get('category__slug') or ''
        slug      = c['slug']
        url = (
            f"/courses/{type_slug}/{cat_slug}/{slug}/"
            if cat_slug else
            f"/courses/{type_slug}/{slug}/"
        )
        course_out.append({
            'name': c['name'],
            'type': c['course_type__name'] or '',
            'url': url,
        })

    total_results = len(inst_out) + len(course_out)
    more_courses = max(0, len(scored_courses) - len(course_out))
    from analytics.utils import log_search
    log_search(request, q, result_count=total_results)

    return JsonResponse({
        'courses': course_out,
        'institutions': inst_out,
        'more_courses': more_courses,
        'search_url': f"/courses/?q={quote(q)}",
    })


# ── Page-level search suggestions ────────────────────────────────────────────
# Powers the dropdown on in-page search boxes (static/js/search_suggest.js).
# Unlike the navbar API, results are scoped to what that page actually filters,
# and each suggestion is a plain term that gets dropped into the page's ?q=.

def _suggest_candidates(request, scope, q):
    """Return a list of (label, sub, abbr) candidates for `scope`."""
    prefix = q[:4]
    name_q = Q(name__icontains=prefix) | Q(name__icontains=q)

    if scope in ('courses', 'career'):
        from courses.models import Course
        qs = Course.objects.filter(name_q)
        if scope == 'career':
            # Only courses in the student's current Career Engine pathway
            from career.views import COURSE_TYPE_MAP, _get_degree_course_type
            pathway = request.session.get('career_pathway', '')
            if pathway == 'Degree':
                qs = qs.filter(course_type=_get_degree_course_type())
            elif pathway in COURSE_TYPE_MAP:
                qs = qs.filter(course_type__name__in=COURSE_TYPE_MAP[pathway])
        if request.GET.get('type'):
            qs = qs.filter(course_type__slug=request.GET['type'])
        if request.GET.get('category'):
            qs = qs.filter(category__slug=request.GET['category'])
        return [(c['name'], c['course_type__name'] or '', '')
                for c in qs.values('name', 'course_type__name')[:200]]

    if scope == 'institutions':
        from institutions.models import Institution
        qs = Institution.objects.filter(name_q | Q(abbreviation__icontains=q))
        if request.GET.get('itype'):
            qs = qs.filter(institution_type__slug=request.GET['itype'])
        return [(i['name'], i['location'] or '', i['abbreviation'] or '')
                for i in qs.values('name', 'location', 'abbreviation')[:100]]

    if scope == 'careers':
        from career.models import CareerProfile
        qs = CareerProfile.objects.filter(Q(title__icontains=prefix) | Q(title__icontains=q))
        return [(t, 'Career', '') for t in qs.values_list('title', flat=True)[:100]]

    if scope == 'articles':
        from resources.models import Article
        qs = Article.objects.filter(is_published=True).filter(
            Q(title__icontains=prefix) | Q(title__icontains=q))
        return [(t, 'Article', '') for t in qs.values_list('title', flat=True)[:100]]

    if scope == 'resources':
        from resources.models import Resource
        qs = Resource.objects.filter(Q(title__icontains=prefix) | Q(title__icontains=q))
        return [(t, 'Resource', '') for t in qs.values_list('title', flat=True)[:100]]

    if scope == 'mentors':
        # Mentor search matches course, university or mentor name
        from mentorship.models import MentorProfile
        mentors = MentorProfile.objects.filter(is_approved=True, is_active=True)
        out = []
        for c in mentors.filter(Q(course__name__icontains=prefix) | Q(course__name__icontains=q)) \
                        .values_list('course__name', flat=True).distinct()[:50]:
            out.append((c, 'Course', ''))
        for i in mentors.filter(Q(institution__name__icontains=prefix) | Q(institution__name__icontains=q)) \
                        .values('institution__name', 'institution__abbreviation').distinct()[:50]:
            out.append((i['institution__name'], 'University', i['institution__abbreviation'] or ''))
        for n in mentors.filter(user__full_name__icontains=q) \
                        .values_list('user__full_name', flat=True)[:20]:
            out.append((n, 'Mentor', ''))
        return out

    return []


SUGGEST_SCOPES = ('courses', 'career', 'institutions', 'careers', 'articles', 'resources', 'mentors')


def api_search_terms(request):
    q = request.GET.get('q', '').strip()[:80]
    scope = request.GET.get('scope', 'courses')
    if len(q) < 2 or scope not in SUGGEST_SCOPES:
        return JsonResponse({'suggestions': []})

    scored, seen = [], set()
    for label, sub, abbr in _suggest_candidates(request, scope, q):
        if not label or label.lower() in seen:
            continue
        s = _score(q, label, abbr)
        if s >= 30:
            seen.add(label.lower())
            scored.append((s, label, sub))
    scored.sort(key=lambda x: (-x[0], len(x[1]), x[1].lower()))

    return JsonResponse({
        'suggestions': [{'label': label, 'sub': sub} for _, label, sub in scored[:8]],
    })
