"""
Lightweight course-name relevance scoring.

Used to order courses by how closely they match a target phrase, e.g. a
career title ("Data Scientist") or another course name ("BSc Data Science").
No external dependencies — tokens are compared by shared prefix so that
scientist/science, analyst/analytics, nurse/nursing etc. line up.
"""
import re

# Words that describe the award, not the discipline — ignored on both sides.
_GENERIC = frozenset({
    'bachelor', 'bachelors', 'master', 'masters', 'degree', 'diploma',
    'certificate', 'cert', 'dip', 'craft', 'artisan', 'level', 'higher',
    'national', 'bsc', 'ba', 'bed', 'bcom', 'hons', 'honours', 'of', 'in',
    'and', 'the', 'with', 'for', 'a', 'an', 'to', 'on', 'science', 'sciences',
    'arts', 'art', 'studies', 'programme', 'program', 'option', 'options',
    'general', 'kmtc', 'tvet', 'ttc',
})

# Job-role words stripped from career titles only ("Data Scientist" → data).
_ROLE_WORDS = frozenset({
    'scientist', 'specialist', 'officer', 'assistant', 'expert',
    'professional', 'practitioner', 'consultant', 'worker', 'personnel',
})

# Partial credit for closely related disciplines (keys/values are stems).
_RELATED = {
    'data': {'analytics', 'statistics', 'informatics', 'computer', 'computing'},
    'computer': {'software', 'informatics', 'computing', 'information', 'data'},
    'software': {'computer', 'computing', 'informatics'},
    'statistic': {'data', 'analytics', 'actuarial', 'mathematics'},
    'actuar': {'statistics', 'mathematics', 'finance', 'insurance'},
    'nurs': {'midwifery', 'health'},
    'medic': {'surgery', 'health', 'clinical'},
    'account': {'finance', 'commerce', 'business'},
    'financ': {'accounting', 'commerce', 'economics', 'banking'},
    'teach': {'education'},
    'engineer': {'technology'},
    'law': {'legal'},
    'pharmac': {'pharmaceutical'},
}


def _tokens(text, drop_roles=False):
    words = re.findall(r'[a-z]+', (text or '').lower())
    out = []
    for w in words:
        if len(w) < 2 or w in _GENERIC:
            continue
        if drop_roles and w in _ROLE_WORDS:
            continue
        out.append(w)
    return out


def _common_prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def tokens_match(a, b):
    """True when two words look like forms of the same root."""
    if a == b:
        return True
    shorter = min(len(a), len(b))
    p = _common_prefix(a, b)
    if p == shorter and shorter >= 3:
        return True
    return p >= 4 and p / shorter >= 0.65


def _related(a, b):
    for root, rel in _RELATED.items():
        if tokens_match(a, root) and any(tokens_match(b, r) for r in rel):
            return True
    return False


def relevance_score(target, course_name, extra_terms=(), outcomes=''):
    """
    Score how well `course_name` fits `target` (higher = better).

    target       – career title or course name to match against
    extra_terms  – secondary keywords (e.g. career tags), weaker weight
    outcomes     – course.career_outcomes text; a mention of target is a bonus
    """
    t_tokens = _tokens(target, drop_roles=True) or _tokens(target)
    c_tokens = _tokens(course_name)
    x_tokens = [t for term in extra_terms for t in _tokens(term)]
    if not c_tokens:
        return 0.0

    score = 0.0
    matched_t = 0
    for t in t_tokens:
        if any(tokens_match(t, c) for c in c_tokens):
            matched_t += 1
            score += 4
        elif any(_related(t, c) for c in c_tokens):
            score += 1.5
    if t_tokens:
        score += 10 * matched_t / len(t_tokens)
        # Primary discipline word leads the course name → stronger fit
        if tokens_match(t_tokens[0], c_tokens[0]):
            score += 3

    # Course words unrelated to the target dilute the fit (e.g. "Actuarial")
    for c in c_tokens:
        if any(tokens_match(c, t) for t in t_tokens):
            continue
        if any(_related(t, c) for t in t_tokens):
            continue
        if any(tokens_match(c, x) for x in x_tokens):
            score += 1
            continue
        score -= 1.5

    if outcomes and target and target.lower() in outcomes.lower():
        score += 4
    return score


def is_related_name(target, course_name, threshold=0.5):
    """True when at least `threshold` of target's discipline words appear in course_name."""
    t_tokens = _tokens(target)
    c_tokens = _tokens(course_name)
    if not t_tokens or not c_tokens:
        return False
    hits = sum(1 for t in t_tokens if any(tokens_match(t, c) for c in c_tokens))
    return hits / len(t_tokens) >= threshold


def rank_courses(target, courses, extra_terms=(), name=lambda c: c.name,
                 outcomes=lambda c: getattr(c, 'career_outcomes', '') or ''):
    """Return `courses` sorted best-fit first (ties: shorter name, then A–Z)."""
    return sorted(
        courses,
        key=lambda c: (
            -relevance_score(target, name(c), extra_terms, outcomes(c)),
            len(name(c)),
            name(c).lower(),
        ),
    )
