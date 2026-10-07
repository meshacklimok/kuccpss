"""
Programme grouping — KUCCPS lists the same programme under many names
("BACHELOR OF SCIENCE (DATA SCIENCE)", "BACHELOR OF SCIENCE IN DATA SCIENCE",
"BACHELOR OF DATA SCIENCE"). Each is a separate Course row. These helpers reduce
a name to its core programme ("data science") so search results and course
pages can group variations the way the KUCCPS portal does.
"""
import re
from collections import OrderedDict

from django.db.models import Count, Prefetch

_PUNCT = re.compile(r'[^a-z0-9 ]+')
_SPACES = re.compile(r'\s+')

# Qualification prefixes stripped from the front of a name, longest first.
# "bachelor of science in data science" → "data science"
_PREFIXES = (
    'bachelor of science in', 'bachelor of science', 'bachelor of arts in', 'bachelor of arts',
    'bachelor of technology in', 'bachelor of technology', 'bachelor of', 'bachelors of',
    'bsc in', 'bsc', 'b sc', 'ba in',
    'higher national diploma in', 'higher diploma in', 'national diploma in', 'diploma in', 'diploma',
    'artisan certificate in', 'craft certificate in', 'national certificate in', 'certificate in',
    'certificate', 'artisan in', 'craft in',
)

# Words ignored when matching a query against a name
_STOP = frozenset({'of', 'in', 'and', 'the', 'with', 'for', 'a', 'an'})


def normalize(text: str) -> str:
    text = (text or '').lower().replace('&', ' and ')
    return _SPACES.sub(' ', _PUNCT.sub(' ', text)).strip()


def core_name(name: str) -> str:
    """'BACHELOR OF SCIENCE (DATA SCIENCE)' → 'data science'."""
    n = normalize(name)
    for p in _PREFIXES:
        if n.startswith(p + ' '):
            rest = n[len(p) + 1:]
            if rest.startswith('in '):
                rest = rest[3:]
            return rest or n
    return n


def display_title(core: str) -> str:
    """'data science and analytics' → 'Data Science and Analytics'."""
    words = core.split()
    return ' '.join(w if (i and w in _STOP) else w.capitalize() for i, w in enumerate(words))


def _contains_phrase(haystack: str, needle: str) -> bool:
    return f' {needle} ' in f' {haystack} '


def _tokens(text: str) -> list[str]:
    return [t for t in normalize(text).split() if t not in _STOP]


def query_filter(q: str):
    """Q object requiring every significant word of `q` to appear in the name
    (so "data science" no longer matches every "Bachelor of Science ...")."""
    from django.db.models import Q
    words = _tokens(core_name(q)) or _tokens(q) or [q]
    f = Q()
    for w in words:
        f &= Q(name__icontains=w)
    return f


def relevance(q: str, name: str) -> int:
    """Higher = better. Exact programme first, then programmes that start with
    the query, then those that merely contain it."""
    qc, nc = core_name(q), core_name(name)
    if nc == qc:
        return 100
    if nc.startswith(qc + ' '):
        return 80
    if _contains_phrase(nc, qc):
        return 60
    return 40


def search_courses(q: str, qs):
    """Filter `qs` by `q` and return a list ordered by relevance, then name."""
    matches = list(qs.filter(query_filter(q)))
    matches.sort(key=lambda c: (-relevance(q, c.name), core_name(c.name), c.name))
    return matches


def group_by_programme(q: str, courses):
    """Group courses (already annotated with `n_institutions`) by core name +
    course type. Returns a list of dicts, best match first."""
    groups: 'OrderedDict[tuple, dict]' = OrderedDict()
    for c in courses:
        key = (c.course_type_id, core_name(c.name))
        g = groups.get(key)
        if g is None:
            g = groups[key] = {
                'title': display_title(key[1]),
                'course_type': c.course_type,
                'courses': [],
                'n_institutions': 0,
                'score': relevance(q, c.name),
            }
        g['courses'].append(c)
        g['n_institutions'] += getattr(c, 'n_institutions', 0)
    out = list(groups.values())
    for g in out:
        g['courses'].sort(key=lambda c: -getattr(c, 'n_institutions', 0))
        g['primary'] = g['courses'][0]
    out.sort(key=lambda g: (-g['score'], -g['n_institutions'], g['title']))
    return out


def find_variations(course, limit: int = 30):
    """Other courses of the same type that are the same programme under a
    different name (`same`), or a closely related one (`related`) — e.g. for
    Data Science: 'BSc Data Science' (same), 'Data Science and Analytics' (related).
    Each course carries its offerings prefetched as `var_offerings`."""
    from .models import Course, CourseOffering

    core = core_name(course.name)
    if not core:
        return {'core': core, 'title': '', 'same': [], 'related': [], 'n_institutions': 0}
    # Short one-word cores like "science" would pull in half the catalogue
    allow_reverse = len(core.split()) >= 2 or len(core) >= 8

    candidates = Course.objects.filter(course_type_id=course.course_type_id).exclude(pk=course.pk)
    same_ids, related_ids = [], []
    for pk, name in candidates.values_list('pk', 'name'):
        c = core_name(name)
        if c == core:
            same_ids.append(pk)
        elif _contains_phrase(c, core) or (allow_reverse and len(c.split()) >= 2 and _contains_phrase(core, c)):
            related_ids.append(pk)

    offering_qs = CourseOffering.objects.select_related(
        'institution', 'institution__institution_type'
    ).order_by('institution__name')

    def _load(ids):
        if not ids:
            return []
        items = list(
            Course.objects.filter(pk__in=ids)
            .select_related('course_type', 'category')
            .annotate(n_institutions=Count('offerings'))
            .prefetch_related(Prefetch('offerings', queryset=offering_qs, to_attr='var_offerings'))
        )
        items.sort(key=lambda c: (-c.n_institutions, c.name))
        return items

    same = _load(same_ids)
    related = _load(related_ids)[:max(0, limit - len(same))]
    institution_ids = {o.institution_id for c in same + related for o in c.var_offerings}
    return {
        'core': core, 'title': display_title(core), 'same': same, 'related': related,
        'n_institutions': len(institution_ids),
    }


# Leading qualification → short tag shown on course cards, longest first.
_QUALIFICATIONS = (
    (r'bachelors?\s+of\s+science', 'BSc'),
    (r'bachelors?\s+of\s+arts', 'BA'),
    (r'bachelors?\s+of\s+technology', 'BTech'),
    (r'bachelors?\s+of', 'Bachelor'),
    (r'higher\s+national\s+diploma', 'HND'),
    (r'diploma', 'Diploma'),
    (r'artisan(?:\s+certificate)?', 'Artisan'),
    (r'craft(?:\s+certificate)?', 'Craft'),
    (r'(?:national\s+)?certificate', 'Certificate'),
)
_QUAL_RE = [(re.compile(rf'^{p}\b\s*(?:in\b|of\b)?\s*', re.I), tag) for p, tag in _QUALIFICATIONS]


def split_course_name(name: str) -> tuple[str, str]:
    """'BACHELOR OF SCIENCE (COMPUTER SCIENCE)' → ('BSc', 'Computer Science')."""
    from kuccpss.seo import _display_name

    name = (name or '').strip()
    for rx, tag in _QUAL_RE:
        m = rx.match(name)
        if not m:
            continue
        rest = name[m.end():].strip()
        if rest.startswith('(') and rest.endswith(')') and rest.count('(') == 1:
            rest = rest[1:-1].strip()
        if rest:
            return tag, _display_name(rest)
        break
    return '', _display_name(name)
