"""
Match student mentors to a course by name, so a course page can list students
who study the same course or a close variation of it.

Course names on the KUCCPS portal vary a lot for the same programme:
"BACHELOR OF SCIENCE IN DATA SCIENCE", "BACHELOR OF SCIENCE DATA SCIENCE",
"BACHELOR OF DATA SCIENCE AND ANALYTICS". These reduce to a core ("data science",
"data science analytics") and two courses match when one core starts with the
other, or the cores are nearly identical (typos, plurals). A different
combination such as "ECONOMICS AND DATA SCIENCE" does not match "DATA SCIENCE".
"""
import re
from difflib import SequenceMatcher

EXACT, SAME_CORE, VARIATION = 0, 1, 2

_QUALIFIER = re.compile(r"^(?:bachelors?|diploma|higher diploma|certificate|degree)\s+(?:of|in)\s+")
_ABBREVIATION = re.compile(r"^(?:bsc|b sc|ba|b ed|bed)\s+(?:in\s+)?")
_FIELD = re.compile(r"^(?:science|arts)\s+(?:in\s+)?")
_STOPWORDS = {"and", "of", "in", "with", "the", "for"}
# A course whose whole core is one of these ("Bachelor of Science") is too broad to
# have variations; it only matches itself.
_GENERIC = {"science", "arts", "education", "technology", "engineering"}
FUZZY_RATIO = 0.9


def course_core(name):
    """Tokens that identify a course, without the qualification wording."""
    text = re.sub(r"[^a-z0-9]+", " ", (name or "").lower().replace("&", " and ")).strip()
    text = _QUALIFIER.sub("", text, count=1)
    text = _ABBREVIATION.sub("", text, count=1)
    stripped = _FIELD.sub("", text, count=1)
    if stripped:  # plain "Bachelor of Science" keeps "science"
        text = stripped
    tokens = [t for t in text.split() if t not in _STOPWORDS]
    if len(tokens) > 1 and tokens[0] == "applied":
        tokens = tokens[1:]
    return tokens


def match_rank(a, b):
    """EXACT/SAME_CORE/VARIATION for two course cores, or None if they don't match."""
    if not a or not b:
        return None
    if a == b:
        return SAME_CORE
    short, long_ = sorted((a, b), key=len)
    if len(short) == 1 and short[0] in _GENERIC:
        return None
    if long_[:len(short)] == short:
        return VARIATION
    if SequenceMatcher(None, " ".join(a), " ".join(b)).ratio() >= FUZZY_RATIO:
        return VARIATION
    return None


def student_mentors_for_course(course, limit=3):
    """Live student mentors studying `course` or a close variation, best match first:
    same course, then same core name, then variations; within each, admin-pinned
    mentors, then most completed sessions, then an open slot, then higher ratings."""
    from django.db.models import Exists, OuterRef

    from .models import MentorProfile, TimeSlot, bookable_slots_q

    target = course_core(course.name)
    if not target:
        return []
    mentors = (
        MentorProfile.objects
        .filter(mentor_type=MentorProfile.STUDENT, is_approved=True, is_active=True, course__isnull=False)
        .select_related("user", "course", "institution")
        .annotate(has_open_slot=Exists(TimeSlot.objects.filter(bookable_slots_q(), mentor=OuterRef("pk"))))
    )
    ranked = []
    for mentor in mentors:
        rank = EXACT if mentor.course_id == course.pk else match_rank(target, course_core(mentor.course.name))
        if rank is not None:
            ranked.append((rank, not mentor.is_pinned, -mentor.total_sessions, not mentor.has_open_slot,
                           -mentor.average_rating, mentor.pk, mentor))
    ranked.sort(key=lambda r: r[:-1])
    return [r[-1] for r in ranked[:limit]]
