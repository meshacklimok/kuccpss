"""
Search-result titles and meta descriptions for the high-volume detail pages
(institutions, courses, career profiles).

Built in Python rather than in templates so the wording can branch on
institution/course type and stay within the lengths Google displays
(~60 chars for titles, ~155 for descriptions). Degree pages talk about
cluster-point cutoffs; KMTC/TVET/TTC pages talk about minimum KCSE mean grade,
because that is how KUCCPS places those students.
"""
from django.conf import settings

from courses.models import LATEST_CUTOFF_YEAR

TITLE_MAX = 70
DESCRIPTION_MAX = 160
BRAND = " | CareerNext"


def kcse_year():
    """KCSE exam year of the students the site is currently serving."""
    return settings.KCSE_CANDIDATE_YEAR


def kuccps_year():
    """Year those students apply through KUCCPS (the year after they sit KCSE)."""
    return settings.KCSE_CANDIDATE_YEAR + 1


def _fit_title(*candidates):
    """Most descriptive candidate that fits TITLE_MAX, with the brand if room.

    Candidates go from most to least descriptive. Keywords matter more than the
    brand suffix, so a candidate is tried without the brand before falling back
    to a shorter one. The last is used even if too long (long names can't shrink).
    """
    for text in candidates:
        if len(text) + len(BRAND) <= TITLE_MAX:
            return text + BRAND
        if len(text) <= TITLE_MAX:
            return text
    return candidates[-1]


def _fit_description(*sentences):
    """Join sentences in order, stopping before the one that would overflow."""
    out = ""
    for s in sentences:
        joined = f"{out} {s}".strip()
        if len(joined) > DESCRIPTION_MAX and out:
            break
        out = joined
    if len(out) > DESCRIPTION_MAX:
        out = out[: DESCRIPTION_MAX - 1].rsplit(" ", 1)[0] + "…"
    return out


_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"}
_ACRONYMS = {"IT", "ICT", "LLB", "BSC", "BED", "HIV", "AIDS", "ECDE", "CPA", "KMTC", "TVET"}


def _display_name(name):
    """Course names imported from the KUCCPS portal are ALL CAPS; title-case them."""
    if not name.isupper():
        return name
    words = []
    for i, w in enumerate(name.split()):
        core = w.strip("()/,-")
        if core in _ACRONYMS:
            words.append(w)
        elif i and core.lower() in _SMALL_WORDS:
            words.append(w.lower())
        else:
            words.append(w.capitalize() if w[:1].isalpha() else w[:1] + w[1:].capitalize())
    return " ".join(words)


def _fmt_points(value):
    return f"{float(value):.1f}"


def _plural(n, word, plural=None):
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def _article(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


def _is_university(institution):
    return "university" in institution.institution_type.slug


def _is_degree(course):
    return course.cluster_id is not None or course.course_type.slug == "degree"


def institution_meta(institution, total_courses):
    name = institution.name
    where = f" in {institution.location}" if institution.location else ""
    year = kuccps_year()

    if _is_university(institution):
        title = _fit_title(
            f"{name} Courses & Cutoff Points {year}",
            f"{name} Courses & Cutoff Points",
            f"{name} Courses",
            name,
        )
        offer = (
            f"{name}{where} offers {_plural(total_courses, 'degree course')} with "
            f"KCSE {LATEST_CUTOFF_YEAR} cutoff points and requirements."
            if total_courses else
            f"{name}{where}: degree courses, KUCCPS cutoff points and requirements."
        )
    else:
        title = _fit_title(
            f"{name}: Courses Offered & Requirements {year}",
            f"{name}: Courses & Requirements {year}",
            f"{name}: Courses & Requirements",
            f"{name} Courses",
            name,
        )
        offer = (
            f"{name}{where} offers {_plural(total_courses, 'KUCCPS course')} "
            f"with the minimum KCSE mean grade needed."
            if total_courses else
            f"{name}{where}: courses offered and the minimum KCSE mean grade needed."
        )

    description = _fit_description(
        offer,
        f"KCSE {kcse_year()} candidate? See which you qualify for.",
    )
    return {"title": title, "description": description}


def course_meta(course, offerings):
    name = _display_name(course.name)
    n = len(offerings)
    year = kuccps_year()

    if _is_degree(course):
        title = _fit_title(
            f"{name}: Cutoff Points & Universities {year}",
            f"{name}: Cutoff Points & Universities",
            f"{name}: KUCCPS Cutoff Points",
            name,
        )
        cutoffs = [o.latest_cutoff() for o in offerings]
        cutoffs = sorted(float(c) for c in cutoffs if c is not None)
        where = (f"{name} is offered at {_plural(n, 'university', 'universities')} in Kenya."
                 if n else f"{name} is a KUCCPS degree programme.")
        if len(cutoffs) > 1 and cutoffs[0] != cutoffs[-1]:
            points = (f"KCSE {LATEST_CUTOFF_YEAR} cutoffs range from "
                      f"{_fmt_points(cutoffs[0])} to {_fmt_points(cutoffs[-1])} points.")
        elif cutoffs:
            points = f"KCSE {LATEST_CUTOFF_YEAR} cutoff: {_fmt_points(cutoffs[0])} points."
        else:
            points = "See cutoff points and subject requirements."
        description = _fit_description(
            where,
            points,
            f"Check if your KCSE {kcse_year()} grades qualify.",
        )
    else:
        title = _fit_title(
            f"{name}: Requirements & Where to Study {year}",
            f"{name}: Requirements & Where to Study",
            f"{name}: Entry Requirements",
            name,
        )
        where = (f"{name} is offered at {_plural(n, 'institution')} in Kenya."
                 if n else f"{name} is a {course.course_type.name} course in Kenya.")
        grade = (f"Minimum KCSE mean grade: {course.minimum_mean_grade}."
                 if course.minimum_mean_grade else
                 "See the minimum KCSE grade and subjects needed.")
        description = _fit_description(
            where,
            grade,
            f"Check if your KCSE {kcse_year()} results qualify.",
        )
    return {"title": title, "description": description}


def career_profile_meta(profile, total_courses):
    title = _fit_title(
        f"{profile.title} in Kenya: Courses, Salary & Requirements",
        f"{profile.title} in Kenya: Courses & Salary",
        f"{profile.title} Career Guide Kenya",
        profile.title,
    )
    salary = f"Typical pay: {profile.average_salary}." if profile.average_salary else ""
    courses = (f"{_plural(total_courses, 'KUCCPS course')} that lead there."
               if total_courses else "The KUCCPS courses that lead there.")
    description = _fit_description(
        f"How to become {_article(profile.title)} {profile.title} in Kenya after KCSE.",
        courses,
        salary,
        "Find out which ones your grades qualify you for.",
    )
    return {"title": title, "description": description}


def seo_years(request):
    """Context processor: candidate/application years for static page titles."""
    return {"kcse_year": kcse_year(), "kuccps_year": kuccps_year()}
