from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.urls import reverse, NoReverseMatch
from django.db import models
from math import sqrt as _sqrt
import re as _re
import time as _time
from .models import (
    TVETCourse, StudentCourseMatch, AIRecommendation, CareerInsight, TVETCategory,
    CareerProfile, QuizQuestion, QuizSubmission, QuizAnswer, SharedResult,
)
from .engine import career_guidance_engine
from typing import Dict, List

# =====================================================
# Helper Functions
# =====================================================

def parse_kcse_grades(post_data) -> Dict[str, str]:
    """
    Converts POSTed KCSE grade form into a dictionary
    Expects keys like 'Mathematics', 'English', etc.
    """
    kcse_grades = {}
    for key, value in post_data.items():
        if key != 'csrfmiddlewaretoken' and value:
            kcse_grades[key] = value.strip().upper()
    return kcse_grades


def save_student_matches(matches: List[StudentCourseMatch]):
    """
    Bulk save all matches to DB
    """
    for match in matches:
        match.save()


def get_course_from_match(match: StudentCourseMatch):
    """
    Return the actual course object from a match
    """
    return match.course or match.tvet_course or match.kmc_course or match.ttc_course


# =====================================================
# 1. Home / Pathway Selection
# =====================================================
def home(request):
    from courses.models import Course
    from institutions.models import Institution

    categories = ["Degree", "Diploma", "TVET", "KMTC", "TTC"]
    tvet_categories = TVETCategory.objects.all()
    context = {
        "categories": categories,
        "tvet_categories": tvet_categories,
        "course_count": Course.objects.count(),
        "institution_count": Institution.objects.count(),
    }
    return render(request, "career/home.html", context)


# =====================================================
# 2. KCSE Input / Career Guidance Form
# =====================================================
@require_http_methods(["GET", "POST"])
def kcse_input(request):
    """
    KCSE input page: user inputs grades per subject
    Handles submission and calls career guidance engine
    """
    if request.method == "POST":
        pathway = request.POST.get("pathway")
        tvet_category = request.POST.get("tvet_category", None)
        kcse_grades = parse_kcse_grades(request.POST)

        if not kcse_grades:
            messages.error(request, "Please input at least one KCSE grade.")
            return redirect("career:kcse_input")

        try:
            matches, ai = career_guidance_engine(kcse_grades, pathway, tvet_category)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("career:kcse_input")
        except Exception as e:
            messages.error(request, f"Unexpected error: {str(e)}")
            return redirect("career:kcse_input")

        # Save matches to DB
        save_student_matches(matches)

        # Store session info for filtering / sorting later
        request.session['kcse_grades'] = kcse_grades
        request.session['pathway'] = pathway
        request.session['tvet_category'] = tvet_category

        context = {
            "matches": matches,
            "ai": ai,
            "pathway": pathway
        }
        return render(request, "career/results.html", context)

    # GET: show form — pre-select pathway if passed from the grid cards
    pathway = request.GET.get("pathway", "")
    return render(request, "career/kcse_input.html", {"pathway": pathway})


# =====================================================
# 3. Detailed Course View
# =====================================================
def course_detail(request, match_id: int):
    """
    Shows detailed information about a course match
    Includes career insights
    """
    try:
        match = StudentCourseMatch.objects.get(id=match_id)
    except StudentCourseMatch.DoesNotExist:
        messages.error(request, "Course match not found.")
        return redirect("career:kcse_input")

    course_obj = get_course_from_match(match)

    insights = CareerInsight.objects.filter(
        course=match.course
    ) or CareerInsight.objects.filter(
        tvet_course=match.tvet_course
    ) or CareerInsight.objects.filter(
        kmc_course=match.kmc_course
    ) or CareerInsight.objects.filter(
        ttc_course=match.ttc_course
    )

    # Pagination for insights if many
    paginator = Paginator(insights, 5)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "match": match,
        "course": course_obj,
        "insights": page_obj
    }
    return render(request, "career/course_detail.html", context)


# =====================================================
# 4. AI Recommendation History
# =====================================================
def ai_recommendations(request):
    """
    Shows historical AI guidance generated in the system
    """
    ai_list = AIRecommendation.objects.all().order_by("-created_at")
    paginator = Paginator(ai_list, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, "career/ai_recommendations.html", {"ai_list": page_obj})


# =====================================================
# 5. Filter Matches by University / Admission Chance
# =====================================================
def filter_matches(request):
    """
    Filters existing StudentCourseMatches based on GET parameters
    """
    pathway = request.session.get('pathway', None)
    matches = StudentCourseMatch.objects.all()

    # Filter by pathway
    if pathway == "Degree":
        matches = matches.filter(course__isnull=False)
    elif pathway == "Diploma":
        matches = matches.filter(course__category__name="Diploma")
    elif pathway == "TVET":
        tvet_cat = request.session.get('tvet_category', None)
        if tvet_cat:
            matches = matches.filter(tvet_course__category__name=tvet_cat)
    elif pathway == "KMTC":
        matches = matches.filter(kmc_course__isnull=False)
    elif pathway == "TTC":
        matches = matches.filter(ttc_course__isnull=False)

    # Filter by university
    uni_id = request.GET.get("university")
    if uni_id:
        matches = matches.filter(university__id=uni_id)

    # Filter by admission chance
    chance = request.GET.get("admission_chance")
    if chance:
        matches = matches.filter(admission_chance__iexact=chance.upper())

    # Sorting
    sort_by = request.GET.get("sort_by", "match_score")
    if sort_by == "match_score":
        matches = matches.order_by("-match_score")
    elif sort_by == "admission_chance":
        matches = matches.order_by("-admission_chance")

    paginator = Paginator(matches, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, "career/results.html", {"matches": page_obj, "pathway": pathway})


# =====================================================
# 6. AJAX: Dynamic Subject Validation for TVET
# =====================================================
@require_http_methods(["POST"])
def ajax_validate_tvet_subjects(request):
    """
    Checks if the entered KCSE grades meet required subjects for a TVET course
    Returns JSON
    """
    kcse_grades = parse_kcse_grades(request.POST)
    course_id = request.POST.get("course_id")
    try:
        course = TVETCourse.objects.get(id=course_id)
    except TVETCourse.DoesNotExist:
        return JsonResponse({"valid": False, "message": "Course not found"})

    required_subjects = [s.name for s in course.required_subjects.all()]
    missing_subjects = [s for s in required_subjects if s not in kcse_grades]

    if missing_subjects:
        return JsonResponse({
            "valid": False,
            "message": f"Missing required subjects: {', '.join(missing_subjects)}"
        })

    return JsonResponse({"valid": True, "message": "All required subjects met"})


# =====================================================
# 7. AJAX: Auto-Update Admission Chances
# =====================================================
@require_http_methods(["POST"])
def ajax_update_admission(request):
    """
    Recalculates admission chance based on updated grades
    """
    kcse_grades = parse_kcse_grades(request.POST)
    pathway = request.POST.get("pathway")
    tvet_category = request.POST.get("tvet_category", None)

    try:
        matches, _ = career_guidance_engine(kcse_grades, pathway, tvet_category)
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

    # Build JSON response
    match_list = []
    for match in matches:
        course_obj = get_course_from_match(match)
        match_list.append({
            "course": course_obj.name,
            "admission_chance": match.admission_chance,
            "match_score": int(match.match_score)
        })

    return JsonResponse({"success": True, "matches": match_list})


# =====================================================
# 8. Search Courses
# =====================================================
def search_courses(request):
    """
    Allows searching by course name or keyword
    """
    query = request.GET.get("q", "")
    matches = StudentCourseMatch.objects.filter(
        course__name__icontains=query
    ) | StudentCourseMatch.objects.filter(
        tvet_course__name__icontains=query
    ) | StudentCourseMatch.objects.filter(
        kmc_course__name__icontains=query
    ) | StudentCourseMatch.objects.filter(
        ttc_course__name__icontains=query
    )
    matches = matches.order_by("-match_score")
    paginator = Paginator(matches, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, "career/results.html", {"matches": page_obj})


# =====================================================
# 9. Export Matches to CSV
# =====================================================
import csv
from django.http import HttpResponse

def export_matches_csv(_request):
    matches = StudentCourseMatch.objects.all()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="career_matches.csv"'

    writer = csv.writer(response)
    writer.writerow(['Course', 'Pathway', 'University', 'Admission Chance', 'Match Score'])

    for match in matches:
        course_obj = get_course_from_match(match)
        pathway = ""
        if match.course:
            pathway = "Degree/Diploma"
        elif match.tvet_course:
            pathway = match.tvet_course.category.name
        elif match.kmc_course:
            pathway = "KMTC"
        elif match.ttc_course:
            pathway = "TTC"

        writer.writerow([course_obj.name, pathway, match.university.name if match.university else "N/A",
                         match.admission_chance, int(match.match_score)])

    return response


# =====================================================
# 10. Career Profiles List
# =====================================================
SECTOR_TABS = [
    ("", "All Careers", "fas fa-th"),
    ("technology", "Technology", "fas fa-laptop-code"),
    ("health", "Health", "fas fa-heartbeat"),
    ("engineering", "Engineering", "fas fa-hard-hat"),
    ("finance", "Finance", "fas fa-chart-line"),
    ("business", "Business", "fas fa-briefcase"),
    ("law", "Law", "fas fa-balance-scale"),
    ("education", "Education", "fas fa-chalkboard-teacher"),
    ("agriculture", "Agriculture", "fas fa-leaf"),
    ("creative", "Creative", "fas fa-paint-brush"),
    ("science", "Science", "fas fa-flask"),
    ("environment", "Environment", "fas fa-globe"),
    ("social", "Social Work", "fas fa-hand-holding-heart"),
]


def career_profiles_list(request):
    from django.db.models import Count
    profiles = CareerProfile.objects.annotate(course_count=Count('related_courses', distinct=True))
    query = request.GET.get("q", "")
    if query:
        profiles = profiles.filter(title__icontains=query)

    sector = request.GET.get("sector", "")
    if sector:
        profiles = profiles.filter(career_tags__icontains=sector)

    demand = request.GET.get("demand", "")
    if demand:
        profiles = profiles.filter(demand_level=demand)

    paginator = Paginator(profiles, 24)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    return render(request, "career/career_profiles.html", {
        "page_obj": page_obj,
        "query": query,
        "active_demand": demand,
        "active_sector": sector,
        "demand_choices": CareerProfile.DEMAND_CHOICES,
        "sector_tabs": SECTOR_TABS,
    })


# =====================================================
# 11. Career Profile Detail
# =====================================================
def career_profile_detail(request, slug):
    profile = get_object_or_404(CareerProfile, slug=slug)
    is_saved = False
    if request.user.is_authenticated:
        from accounts.models import SavedCareer
        is_saved = SavedCareer.objects.filter(
            user=request.user, career_profile=profile
        ).exists()

    # Related careers: prefer same-sector tags over arbitrary first-4
    tags = profile.get_tags_list()
    related_qs = CareerProfile.objects.exclude(pk=profile.pk)
    if tags:
        from django.db.models import Q as _Q
        tq = _Q()
        for t in tags[:2]:
            tq |= _Q(career_tags__icontains=t)
        related_qs = related_qs.filter(tq)
    related = list(related_qs[:4])

    # Linked courses: prefetch offerings+institutions, then group by type
    from collections import defaultdict
    raw_courses = list(
        profile.related_courses
        .select_related('course_type', 'category', 'cluster')
        .prefetch_related('offerings__institution')
        .all()
    )
    _TYPE_ORDER = ['Degree', 'Diploma', 'KMTC', 'TTC']
    bucket = defaultdict(list)
    for c in raw_courses:
        bucket[c.course_type.name].append(c)
    courses_by_type = []
    for t in _TYPE_ORDER:
        if t in bucket:
            courses_by_type.append((t, bucket.pop(t)))
    for t in sorted(bucket):
        courses_by_type.append((t, bucket[t]))

    return render(request, "career/career_profile_detail.html", {
        "profile": profile,
        "is_saved": is_saved,
        "related": related,
        "courses_by_type": courses_by_type,
        "total_linked": len(raw_courses),
    })


# =====================================================
# 12. Career Assessment Quiz
# =====================================================
def quiz_view(request):
    questions = QuizQuestion.objects.prefetch_related("options").all()

    if request.method == "POST":
        submission = QuizSubmission.objects.create(
            user=request.user if request.user.is_authenticated else None,
            session_key=request.session.session_key or "",
        )
        tag_scores: Dict[str, int] = {}
        for question in questions:
            option_id = request.POST.get(f"q_{question.pk}")
            if option_id:
                try:
                    option = question.options.get(pk=option_id)
                    QuizAnswer.objects.create(
                        submission=submission, question=question, option=option
                    )
                    for tag in option.get_tags_list():
                        tag_scores[tag] = tag_scores.get(tag, 0) + 1
                except Exception:
                    pass

        request.session["quiz_tag_scores"] = tag_scores
        request.session["quiz_submission_id"] = submission.pk
        return redirect("career:quiz_results")

    return render(request, "career/quiz.html", {"questions": questions})


# =====================================================
# 13. Quiz Results
# =====================================================

def _generate_quiz_ai_summary(tag_scores: dict, top_career_names: list) -> str:
    """Call GPT-4o-mini for a short personalised career summary. Returns '' on any error."""
    from django.conf import settings as _s
    api_key = getattr(_s, 'OPENAI_API_KEY', '')
    if not api_key or api_key.startswith('sk-xxx') or not top_career_names:
        return ''
    try:
        cfg = _get_career_config()
        if not getattr(cfg, 'ai_enabled', True):
            return ''

        top_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        tag_str = ', '.join(f"{t} ({s})" for t, s in top_tags)
        careers_str = ', '.join(top_career_names[:3])

        custom_template = getattr(cfg, 'ai_prompt_template', '').strip()
        if custom_template:
            prompt = custom_template.format(tag_str=tag_str, careers_str=careers_str)
        else:
            prompt = (
                f"A Kenyan secondary school student completed a career quiz. "
                f"Their top interest tags and scores: {tag_str}. "
                f"Top matched careers: {careers_str}. "
                "Write a warm, encouraging 2-sentence personalised summary (max 60 words) "
                "explaining why these careers suit them. Address the student as 'you'. No bullet points."
            )

        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=120,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as _e:
        import logging as _lg
        _lg.getLogger(__name__).error("AI summary error: %s", _e)
        return ''


def quiz_results_view(request):
    tag_scores = request.session.get("quiz_tag_scores", {})
    if not tag_scores:
        return redirect("career:quiz")

    # Score each career profile by how many of its tags appear in top results
    profiles = CareerProfile.objects.all()
    scored: List[Dict] = []
    for profile in profiles:
        profile_tags = profile.get_tags_list()
        score = sum(tag_scores.get(t, 0) for t in profile_tags)
        if score > 0:
            scored.append({"profile": profile, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_matches = scored[:6]

    top_career_names = [m['profile'].title for m in top_matches[:3]]
    ai_summary = _generate_quiz_ai_summary(tag_scores, top_career_names)

    return render(request, "career/quiz_results.html", {
        "top_matches": top_matches,
        "tag_scores": tag_scores,
        "ai_summary": ai_summary,
    })


# =====================================================
# Shared helper — build real DB context for AI
# =====================================================
def _build_ai_db_context(request) -> str:
    """
    Returns a string of the student's actual course matches from the DB.
    Uses CareerSessionSnapshot for logged-in users, or a quick query for anonymous.
    """
    pathway            = request.session.get('career_pathway', '')
    cluster_pts_single = float(request.session.get('career_cluster_pts_single', 0) or 0)
    mean_grade         = request.session.get('career_mean_grade', '')
    score_str          = f"{cluster_pts_single:.1f}/48 cluster points" if pathway == 'Degree' else f"mean grade {mean_grade}"

    lines      = [f"STUDENT: {pathway} pathway | Score: {score_str}"]
    top_matches = []

    # Logged-in users — use stored snapshot
    if request.user.is_authenticated:
        try:
            from accounts.models import CareerSessionSnapshot
            snap = CareerSessionSnapshot.objects.filter(
                user=request.user, pathway=pathway
            ).order_by('-computed_at').first()
            if snap and snap.top_matches_json:
                top_matches = snap.top_matches_json
                lines.append(f"Total matches in database: {snap.total_matches}")
                tc = snap.tier_counts_json or {}
                tier_summary = ', '.join(f"{k}: {v}" for k, v in tc.items())
                if tier_summary:
                    lines.append(f"Tier breakdown: {tier_summary}")
        except Exception:
            pass

    # Anonymous users (or snapshot missing) — quick live query
    if not top_matches:
        try:
            from courses.models import CourseOffering, CourseType
            cluster_points_dict = request.session.get('career_cluster_points', {})
            cfg = _get_career_config()

            if pathway == 'Degree':
                degree_type = CourseType.objects.filter(name__icontains='Degree').first()
                if degree_type:
                    qs = (CourseOffering.objects
                          .filter(course__course_type=degree_type)
                          .select_related('course', 'course__cluster', 'institution')
                          .exclude(cutoff_points__isnull=True)[:100])
                    raw = []
                    for offering in qs:
                        cutoff = offering.latest_cutoff()
                        if cutoff is None:
                            continue
                        cluster = offering.course.cluster
                        knum    = cluster.kuccps_number if cluster else None
                        s_pts   = float(cluster_points_dict.get(str(knum), cluster_pts_single)) if knum else cluster_pts_single
                        diff    = round(s_pts - float(cutoff), 2)
                        tier, _ = _tier_from_diff(diff, cfg)
                        raw.append({
                            'course_name':      offering.course.name,
                            'institution_name': offering.institution.name,
                            'cutoff':           cutoff,
                            'student_pts':      round(s_pts, 1),
                            'diff':             diff,
                            'tier':             tier,
                            'chance':           _chance_from_diff(diff)[0],
                        })
                    _ORDER = {'Best Match':1,'Stretch':2,'Safe Option':3,'Easy Admission':4,'Long Shot':5}
                    raw.sort(key=lambda m: (_ORDER.get(m['tier'], 9), abs(m['diff'])))
                    top_matches = raw[:10]
            else:
                subject_grades = request.session.get('career_subject_grades', {})
                student_pts_val = GRADE_POINTS.get(mean_grade, 0)
                type_names = COURSE_TYPE_MAP.get(pathway, [])
                if type_names:
                    qs = (CourseOffering.objects
                          .filter(course__course_type__name__in=type_names)
                          .select_related('course', 'institution')[:100])
                    default_min = PATHWAY_DEFAULT_MIN_GRADE.get(pathway, 'E')
                    raw = []
                    for offering in qs:
                        min_g  = (offering.course.minimum_mean_grade or '').strip() or default_min
                        min_p  = GRADE_POINTS.get(min_g, 0)
                        diff   = student_pts_val - min_p
                        tier, _= _tier_from_diff(diff, cfg)
                        raw.append({
                            'course_name':      offering.course.name,
                            'institution_name': offering.institution.name,
                            'cutoff':           min_g,
                            'student_pts':      mean_grade,
                            'diff':             diff,
                            'tier':             tier,
                            'chance':           _chance_from_grade_diff(diff)[0],
                        })
                    _ORDER = {'Best Match':1,'Stretch':2,'Safe Option':3,'Easy Admission':4,'Long Shot':5}
                    raw.sort(key=lambda m: (_ORDER.get(m['tier'], 9), abs(m['diff'])))
                    top_matches = raw[:10]
        except Exception:
            pass

    if top_matches:
        lines.append("\nTOP MATCHED COURSES FROM YOUR DATABASE:")
        for i, m in enumerate(top_matches, 1):
            diff     = m.get('diff', 0)
            diff_str = f"+{diff:.1f}" if diff >= 0 else f"{diff:.1f}"
            lines.append(
                f"{i}. {m.get('course_name','?')} — {m.get('institution_name','?')} | "
                f"Cutoff: {m.get('cutoff','?')} | Your score: {m.get('student_pts','?')} | "
                f"Diff: {diff_str} | Tier: {m.get('tier','?')} | Chance: {m.get('chance','?')}"
            )
    else:
        lines.append("\nNo specific course data found — advise based on pathway and score only.")

    lines.append(
        "\nRULE: Use ONLY the real course data above. Never invent cutoff points or institution names. "
        "If asked about a specific course not listed, say you can only see their top 10 matches."
    )
    return '\n'.join(lines)


# =====================================================
# 14. AJAX — AI Insight for Career Results page
# =====================================================
def ajax_ai_insight(request):
    """
    Called by the 'AI Insight' button on career_results_v2.html.
    Reads session career data and returns a GPT-4o-mini insight as JSON.
    """
    from django.conf import settings as _s
    api_key = getattr(_s, 'OPENAI_API_KEY', '')
    if not api_key:
        return JsonResponse({"error": "AI not configured."}, status=400)

    try:
        from openai import OpenAI
        cfg = _get_career_config()
        if not getattr(cfg, 'ai_enabled', True):
            return JsonResponse({"error": "AI insight is disabled."}, status=400)

        db_context = _build_ai_db_context(request)

        prompt = (
            f"{db_context}\n\n"
            "Based on the real course data above, write a personalised 3-sentence opening message to this student:\n"
            "(1) Name their top 2 specific matched courses and institutions from the data.\n"
            "(2) Tell them what their score means — are they competitive?\n"
            "(3) Give one specific actionable tip for their next step.\n"
            "Be warm, specific, and address them as 'you'. No bullet points."
        )

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=200,
            temperature=0.7,
        )
        text = resp.choices[0].message.content.strip()
        return JsonResponse({"insight": text})

    except Exception as e:
        import logging as _lg
        _lg.getLogger(__name__).error("AI insight error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


# =====================================================
# Knowledge base search — DB-first before calling GPT
# =====================================================
_KB_STOP_WORDS = {
    'i', 'a', 'an', 'the', 'is', 'are', 'was', 'be', 'can', 'do', 'does',
    'for', 'of', 'in', 'to', 'my', 'me', 'what', 'how', 'which', 'why',
    'and', 'or', 'if', 'it', 'this', 'that', 'with', 'have', 'has', 'will',
    'good', 'best', 'better', 'any', 'some', 'about', 'get', 'give', 'tell',
    'want', 'would', 'could', 'should', 'need', 'like', 'who', 'where', 'when',
    'am', 'got', 'get', 'did', 'had', 'not', 'so', 'on', 'at', 'as', 'by',
    'from', 'its', 'than', 'then', 'them', 'they', 'just', 'also', 'after',
}


def _search_knowledge_base(query: str, max_results: int = 4) -> list:
    """
    Search AIKnowledgeEntry by keyword matching.
    Returns up to max_results entries ranked by relevance score.
    """
    from .models import AIKnowledgeEntry
    from django.db.models import Q

    if not query:
        return []

    raw_words = [w.lower().strip('?!.,;:') for w in query.split() if len(w) > 1]
    keywords  = [w for w in raw_words if w not in _KB_STOP_WORDS] or raw_words

    if not keywords:
        return []

    q = Q()
    for kw in keywords[:8]:
        q |= Q(question__icontains=kw) | Q(keywords__icontains=kw) | Q(answer__icontains=kw)

    entries = list(AIKnowledgeEntry.objects.filter(q, is_active=True).distinct()[:60])

    scored = []
    for entry in entries:
        text_q  = entry.question.lower()
        text_kw = entry.keywords.lower()
        text_a  = entry.answer.lower()
        score = 0
        for kw in keywords:
            if kw in text_q:
                score += 4
            if kw in text_kw:
                score += 3
            if kw in text_a:
                score += 1
        scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:max_results] if _ > 0]


# =====================================================
# 15. AJAX — AI Chat (DB-first, then GPT)
# =====================================================
@require_POST
def ajax_ai_chat(request):
    """
    Multi-turn AI chat.
    1. Search AIKnowledgeEntry for relevant verified facts.
    2. Inject them into the system prompt so GPT answers from DB data.
    3. Also include the student's matched course context.
    Body: { message, history: [{role, content}, ...] }
    """
    import json as _json
    from django.conf import settings as _s

    api_key = getattr(_s, 'OPENAI_API_KEY', '')
    if not api_key:
        return JsonResponse({"error": "AI not configured."}, status=400)

    try:
        body = _json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "Invalid request."}, status=400)

    user_message = body.get("message", "").strip()
    history      = body.get("history", [])

    if not user_message:
        return JsonResponse({"error": "Empty message."}, status=400)

    # ── 1. Search knowledge base ─────────────────────────
    kb_entries = _search_knowledge_base(user_message)
    kb_section = ""
    if kb_entries:
        lines = ["VERIFIED FACTS FROM DATABASE (use these first):"]
        for e in kb_entries:
            lines.append(f"Q: {e.question}\nA: {e.answer}")
        kb_section = "\n\n".join(lines)

    # ── 2. Student's own course match context ────────────
    db_context = _build_ai_db_context(request)

    # ── 3. Compose system prompt ─────────────────────────
    system_parts = [
        "You are CareerNext AI, a professional career guidance assistant for Kenyan students. "
        "You help students choose courses, careers, and universities based on KCSE results and interests.",
        "",
        "GRADE → PATHWAY RULES (Kenya):",
        "- Degree: minimum mean grade C+ (cluster points 0–48 used for ranking)",
        "- Diploma: minimum mean grade C or C- depending on course",
        "- Certificate: minimum mean grade C- or D+ depending on course",
        "- Artisan: for students with D and below",
        "- KMTC: most courses require minimum C; Clinical Medicine/Nursing may require higher",
        "- TTC (Primary teacher): minimum C or C-",
        "- Non-degree KUCCPS choices: students submit only 2 course choices (not 6)",
        "",
    ]

    if kb_section:
        system_parts += [kb_section, ""]

    if db_context:
        system_parts += [
            "STUDENT'S MATCHED COURSES FROM DATABASE:",
            db_context,
            "",
        ]

    system_parts += [
        "RULES:",
        "- Answer using the VERIFIED FACTS above first. Only add your own knowledge if the facts don't cover it.",
        "- Keep responses under 120 words. Use bullet points only when listing 3+ items.",
        "- Be warm and address the student as 'you'.",
        "- If unsure about specific cutoff numbers, say 'varies yearly — check KUCCPS portal'.",
        "- Never invent institution names or exact cutoff figures not in the verified facts.",
    ]

    system_prompt = "\n".join(system_parts)

    messages = [{"role": "system", "content": system_prompt}]
    for turn in history[-6:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=messages,
            max_tokens=220,
            temperature=0.5,
        )
        reply = resp.choices[0].message.content.strip()
        return JsonResponse({"reply": reply, "kb_used": len(kb_entries)})

    except Exception as e:
        import logging as _lg
        _lg.getLogger(__name__).error("AI chat error: %s", e)
        return JsonResponse({"error": "AI error, please try again."}, status=500)


# =====================================================
# 15b. Standalone Chat page
# =====================================================
def career_chat(request):
    """Full-page CareerNext AI chat for students."""
    from django.conf import settings as _s
    ai_ready = bool(getattr(_s, 'OPENAI_API_KEY', ''))
    return render(request, 'career/chat.html', {'ai_ready': ai_ready})


# ═══════════════════════════════════════════════════════
# CAREER GUIDANCE ENGINE v2 — DEGREE FLOW + ALL PATHWAYS
# ═══════════════════════════════════════════════════════

MEAN_GRADES = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'E']

GRADE_POINTS = {
    'A': 12, 'A-': 11, 'B+': 10, 'B': 9, 'B-': 8,
    'C+': 7, 'C': 6, 'C-': 5, 'D+': 4, 'D': 3, 'D-': 2, 'E': 1,
}

KENYAN_COUNTIES = [
    'BARINGO', 'BOMET', 'BUNGOMA', 'BUSIA', 'ELGEYO MARAKWET', 'EMBU',
    'GARISSA', 'HOMA BAY', 'ISIOLO', 'KAJIADO', 'KAKAMEGA', 'KERICHO',
    'KIAMBU', 'KILIFI', 'KIRINYAGA', 'KISII', 'KISUMU', 'KITUI', 'KWALE',
    'LAIKIPIA', 'LAMU', 'MACHAKOS', 'MAKUENI', 'MANDERA', 'MARSABIT',
    'MERU', 'MIGORI', 'MOMBASA', "MURANG'A", 'NAIROBI', 'NAKURU',
    'NANDI', 'NAROK', 'NYAMIRA', 'NYANDARUA', 'NYERI', 'SAMBURU',
    'SIAYA', 'TAITA TAVETA', 'TANA RIVER', 'THARAKA NITHI', 'TRANS NZOIA',
    'TURKANA', 'UASIN GISHU', 'VIHIGA', 'WAJIR', 'WEST POKOT',
]

TVET_CATEGORIES = [
    'Business and Related',
    'Building Construction and Related',
    'Engineering Technology and Related',
    'Environmental Sciences',
    'Applied Sciences',
    'Health Sciences and Related',
    'Food Science and Related',
    'Nutrition and Dietetics',
    'Social Sciences',
    'IT and Related',
    'Agriculture and Related',
    'Hospitality and Tourism',
    'Fashion and Design',
]

PATHWAY_SLUG_TO_LABEL = {
    'degree':      'Degree',
    'diploma':     'Diploma',
    'certificate': 'Certificate',
    'kmtc':        'KMTC',
    'ttc':         'TTC',
    'artisan':     'Artisan',
    'shortcourse': 'Short Course',
}

COURSE_TYPE_MAP = {
    'Diploma':      ['TVET Diploma (Level 6)'],
    'Certificate':  ['TVET Certificate (Level 5)'],
    'KMTC':         ['KMTC'],
    'TTC':          ['TTC'],
    'Artisan':      ['TVET Artisan Certificate (Level 4)', 'TVET Craft Certificate (Level 3)'],
    'Short Course': ['TVET Short Course', 'TVET Trade Test', 'TVET Professional', 'TVET Proficiency'],
}


def _chance_from_diff(diff):
    """Admission chance for cluster points (degree)."""
    if diff >= 5:
        return 'High Likelihood', 'success'
    if diff >= 0:
        return 'Likely', 'success'
    if diff >= -3:
        return 'Borderline', 'warning'
    return 'Unlikely', 'danger'


def _compute_cluster_points_for_session(pts_by_name):
    """
    Compute per-cluster points from a {subject_name: points_int} dict.
    Returns (cluster_points_dict {str(cluster_id): float}, avg_pts float).
    Falls back to top-4 single value if SubjectGroups are not seeded.
    """
    from math import sqrt as _sqrt2
    from clusters.models import Cluster

    # Aggregate total: Maths + best language + 5 best remaining
    working = pts_by_name.copy()
    agg = []
    if 'Mathematics' in working:
        agg.append(working.pop('Mathematics'))
    lang_scores = {lang: working.pop(lang) for lang in ['English', 'Kiswahili'] if lang in working}
    if lang_scores:
        best_lang = max(lang_scores, key=lambda k: lang_scores[k])
        agg.append(lang_scores[best_lang])
        for lang, pts in lang_scores.items():
            if lang != best_lang:
                working[lang] = pts
    agg += sorted(working.values(), reverse=True)[:5]
    aggregate_total = sum(agg)

    clusters = (
        Cluster.objects
        .filter(subject_groups__isnull=False)
        .distinct()
        .prefetch_related('subject_groups__subjects')
    )
    cluster_list = list(clusters)

    if not cluster_list:
        # SubjectGroups not seeded — fall back to top-4 for all clusters
        all_pts = sorted(pts_by_name.values(), reverse=True)
        core_total = min(sum(all_pts[:4]), 48)
        single = round(48 * _sqrt2((core_total / 48) * (aggregate_total / 84)), 2) if aggregate_total and core_total else 0.0
        all_ids = list(Cluster.objects.values_list('id', flat=True))
        return {str(cid): single for cid in all_ids}, single

    cluster_points = {}
    for cluster in cluster_list:
        slots = cluster.subject_groups.prefetch_related('subjects').order_by('priority')
        used_names = set()
        core_pts = []
        any_unfilled = False

        for slot in slots:
            if len(core_pts) >= 4:
                break
            best_name, best_val = None, -1
            for subj in slot.subjects.all():
                if subj.name not in used_names and subj.name in pts_by_name:
                    v = pts_by_name[subj.name]
                    if v > best_val:
                        best_val, best_name = v, subj.name
            if best_name:
                core_pts.append(best_val)
                used_names.add(best_name)
            else:
                core_pts.append(0)
                any_unfilled = True

        while len(core_pts) < 4:
            core_pts.append(0)

        raw_core = sum(core_pts[:4])
        if any_unfilled or raw_core == 0 or aggregate_total == 0:
            weighted = 0.0
        else:
            weighted = round(min(48 * _sqrt2((raw_core / 48) * (aggregate_total / 84)), 48.0), 2)

        # Key by KUCCPS group number (1-20) so career_results can look up
        # by cluster.kuccps_number regardless of whether the course uses a
        # sub-cluster (5-65) or a master cluster (66-85).
        knum = cluster.kuccps_number
        if knum is not None:
            cluster_points[str(knum)] = weighted

    avg = round(sum(cluster_points.values()) / len(cluster_points), 2) if cluster_points else 0.0
    return cluster_points, avg


def _chance_from_grade_diff(diff):
    """Admission chance for mean grade comparison (non-degree)."""
    if diff >= 3:
        return 'High Likelihood', 'success'
    if diff >= 0:
        return 'Likely', 'success'
    if diff >= -2:
        return 'Borderline', 'warning'
    return 'Unlikely', 'danger'


# ── Career config cache (refreshed every 60 s) ───────────────────────────────

class _DefaultCareerCfg:
    best_match_max_diff  = 3.0
    stretch_min_diff     = -3.0
    safe_max_diff        = 8.0
    competitive_threshold = 40.0

_career_cfg_cache: object = None
_career_cfg_ts:    float  = 0.0

def _get_career_config() -> _DefaultCareerCfg:
    global _career_cfg_cache, _career_cfg_ts
    now = _time.monotonic()
    if _career_cfg_cache is None or now - _career_cfg_ts > 60:
        try:
            from career.models import CareerConfig
            _career_cfg_cache = CareerConfig.get()
        except Exception:
            _career_cfg_cache = _DefaultCareerCfg()
        _career_cfg_ts = now
    return _career_cfg_cache  # type: ignore[return-value]


# Tier metadata: label → (sort_order, stripe_colour, badge_css, description)
TIER_META = {
    'Best Match':     (1, '#059669', 'tier-best',     'Your score is right at or just above the cutoff — ideal fit.'),
    'Stretch':        (2, '#d97706', 'tier-stretch',  'Slightly below the cutoff — competitive but worth applying.'),
    'Safe Option':    (3, '#2563eb', 'tier-safe',     'Comfortably above the cutoff — strong chance of admission.'),
    'Easy Admission': (4, '#64748b', 'tier-easy',     'Well above the cutoff — very high certainty of admission.'),
    'Long Shot':      (5, '#dc2626', 'tier-longshot', 'Significantly below the cutoff — low probability.'),
}


def _tier_from_diff(diff: float, cfg: _DefaultCareerCfg) -> tuple:
    """Return (tier_label, tier_order) based on student_score - cutoff."""
    if diff < cfg.stretch_min_diff:
        return 'Long Shot', 5
    if diff < 0:
        return 'Stretch', 2
    if diff <= cfg.best_match_max_diff:
        return 'Best Match', 1
    if diff <= cfg.safe_max_diff:
        return 'Safe Option', 3
    return 'Easy Admission', 4


CHANCE_DESC = {
    'High Likelihood': 'Your score is above the high-end predicted cutoff. Very strong candidate — apply with confidence.',
    'Likely':          'Your score is above the predicted cutoff. Good chance — include as a top choice.',
    'Borderline':      'Your score falls within the predicted range. Possible — a strong application matters here.',
    'Unlikely':        'Your score is below the predicted range. Very competitive — treat as a long-shot only.',
}


def _build_course_url(course) -> str | None:
    """Build a link to the course detail page. Returns None if URL can't be resolved."""
    try:
        if course.category and course.course_type:
            return reverse('courses:course_detail', kwargs={
                'type_slug':     course.course_type.slug,
                'category_slug': course.category.slug,
                'course_slug':   course.slug,
            })
        if course.course_type:
            return reverse('courses:course_detail_no_category', kwargs={
                'type_slug':   course.course_type.slug,
                'course_slug': course.slug,
            })
    except (NoReverseMatch, AttributeError):
        pass
    return None


# ── Grade-band lookup ─────────────────────────
_GRADE_BANDS = [
    (81, 'A'),  (74, 'A-'), (67, 'B+'), (60, 'B'),  (53, 'B-'),
    (46, 'C+'), (40, 'C'),  (35, 'C-'), (29, 'D+'), (23, 'D'),
    (18, 'D-'), (0,  'E'),
]

def _aggregate_to_mean_grade(aggregate):
    for threshold, grade in _GRADE_BANDS:
        if aggregate >= threshold:
            return grade
    return 'E'

# Default minimum grade when a course has no minimum_mean_grade set
PATHWAY_DEFAULT_MIN_GRADE = {
    'Diploma':      'C-',
    'Certificate':  'D+',
    'KMTC':         'C',
    'TTC':          'C-',
    'Artisan':      'D',
    'Short Course': 'E',
}


# Maps KUCCPS subject shortcodes (from subject_requirements JSONField) to lowercase full names
_KUCCPS_CODE_TO_NAME = {
    'eng':   'english',
    'kis':   'kiswahili',
    'mat a': 'mathematics',
    'mat':   'mathematics',
    'bio':   'biology',
    'bsc':   'biology',
    'che':   'chemistry',
    'phy':   'physics',
    'psc':   'physics',
    'geo':   'geography',
    'his':   'history and government',
    'hst':   'history and government',
    'bst':   'business studies',
    'econ':  'business studies',
    'cmp':   'computer studies',
    'com':   'computer studies',
    'agr':   'agriculture',
    'hsc':   'home science',
    'cre':   'christian religious education',
    'ire':   'islamic religious education',
    'hre':   'hindu religious education',
    'mus':   'music',
    'art':   'art and design',
    'drd':   'drawing and design',
    'bld':   'building construction',
    'bc':    'building construction',
    'pw':    'power mechanics',
    'pm':    'power mechanics',
    'ele':   'electricity',
    'ect':   'electricity',
    'mw':    'metalwork',
    'ww':    'woodwork',
    'fre':   'french',
    'ger':   'german',
    'ara':   'arabic',
    'avi':   'aviation technology',
    'gsc':   'physics',
    'ksl':   'kenyan sign language',
}


def _meets_subject_requirements(requirements, subject_grades_lower):
    """
    Check if a student satisfies a course's subject_requirements JSONField.
    requirements: list of dicts like [{"slot":1,"subjects_str":"BIO/BST","min_grade":"C"}, ...]
    subject_grades_lower: dict of {lowercase_subject_name: points_int}
    Returns True if all slots are satisfied (or requirements is empty/None).
    """
    if not requirements:
        return True
    for slot in requirements:
        subjects_str = slot.get('subjects_str', '')
        min_grade_str = (slot.get('min_grade') or 'E').strip()
        min_pts = GRADE_POINTS.get(min_grade_str, 1)
        raw_codes = [s.strip().lower() for s in _re.split(r'[/|,]', subjects_str) if s.strip()]
        if not raw_codes:
            continue
        # Resolve each shortcode to a full subject name, fall back to the code itself
        resolved = [_KUCCPS_CODE_TO_NAME.get(code, code) for code in raw_codes]
        satisfied = any(subject_grades_lower.get(name, 0) >= min_pts for name in resolved)
        if not satisfied:
            return False
    return True


# ─────────────────────────────────────────────
# A. DEGREE ENTRY — 4-choice landing
# ─────────────────────────────────────────────
def degree_entry(request):
    return redirect('career:degree_calculate')


# ─────────────────────────────────────────────
# B. DEGREE: Calculate cluster points from KCSE grades
# ─────────────────────────────────────────────
def degree_calculate(request):
    from clusterpoints.forms import KCSEForm
    from clusters.models import Subject, Cluster

    # If coming from OCR upload, pre-populate the form with extracted grades
    ocr_prefill = request.session.pop('ocr_prefill', None)

    if request.method == 'POST':
        form = KCSEForm(request.POST)
    elif ocr_prefill:
        # Build initial data from {subject_id: points_int} dict
        initial = {f'subject_{sid}': pts for sid, pts in ocr_prefill.items()}
        form = KCSEForm(initial=initial)
    else:
        form = KCSEForm()

    if request.method == 'POST' and form.is_valid():
        points_by_id = form.get_points_dict()  # {subject_id: points_int}

        # Build name → points dict (keep subjects_map for DB persistence below)
        subjects_qs = Subject.objects.filter(id__in=points_by_id.keys())
        subjects_map = {s.id: s for s in subjects_qs}
        pts_by_name = {s.name: points_by_id[s.id] for s in subjects_qs}

        # Persist for subject-requirement filtering in results
        request.session['career_subject_grades'] = {k.lower(): v for k, v in pts_by_name.items()}

        # Aggregate total: Math + best(Eng/Kis) + 5 best remaining
        working = pts_by_name.copy()
        agg = []
        if 'Mathematics' in working:
            agg.append(working.pop('Mathematics'))
        lang_scores = {lang: working.pop(lang) for lang in ['English', 'Kiswahili'] if lang in working}
        if lang_scores:
            best = max(lang_scores, key=lambda k: lang_scores[k])
            agg.append(lang_scores[best])
            for lang, pts in lang_scores.items():
                if lang != best:
                    working[lang] = pts
        agg += sorted(working.values(), reverse=True)[:5]
        aggregate_total = sum(agg)

        # Per-cluster points using SubjectGroups (same logic as clusterpoints/services.py)
        precomputed, cluster_pts_single = _compute_cluster_points_for_session(pts_by_name)

        request.session['career_pathway'] = 'Degree'
        request.session['career_degree_method'] = 'calculate'
        request.session['career_precomputed'] = precomputed
        request.session['career_aggregate_total'] = aggregate_total
        request.session['career_cluster_pts_single'] = cluster_pts_single

        # Also persist to DB so that Eligible Courses (clusterpoints app) stays in sync
        if request.user.is_authenticated:
            from django.db import transaction
            from django.utils import timezone
            from clusterpoints.models import UserKCSEResult, SubjectResult
            from clusterpoints.services import calculate_all_clusters
            with transaction.atomic():
                UserKCSEResult.objects.filter(user=request.user).delete()
                kcse_result = UserKCSEResult.objects.create(
                    user=request.user, created_at=timezone.now()
                )
                SubjectResult.objects.bulk_create([
                    SubjectResult(kcse_result=kcse_result, subject=subjects_map[sid], points=pts)
                    for sid, pts in points_by_id.items()
                    if sid in subjects_map
                ])
                kcse_result.recalc_total_points()
                calculate_all_clusters(kcse_result)

        return redirect('career:degree_options')

    # Build grouped subject data for the redesigned grade-entry UI
    from clusters.models import GROUP_CHOICES as _GC
    from clusterpoints.forms import COMPULSORY_SUBJECT_NAMES as _COMP

    _ICONS = {
        'English': 'bi-book-half', 'Kiswahili': 'bi-translate',
        'Mathematics': 'bi-calculator-fill', 'Chemistry': 'bi-droplet-fill',
        'Biology': 'bi-flower1', 'Physics': 'bi-lightning-charge-fill',
        'Geography': 'bi-globe2', 'History and Government': 'bi-bank',
        'Christian Religious Education': 'bi-book', 'Islamic Religious Education': 'bi-moon-stars-fill',
        'Hindu Religious Education': 'bi-sun', 'Computer Studies': 'bi-laptop',
        'Agriculture': 'bi-tree-fill', 'Business Studies': 'bi-graph-up-arrow',
        'Home Science': 'bi-house-heart', 'Art and Design': 'bi-palette-fill',
        'Music': 'bi-music-note-beamed', 'French': 'bi-chat-left-text',
        'German': 'bi-chat-left-text', 'Arabic': 'bi-chat-left-text-fill',
        'Building Construction': 'bi-building', 'Electricity': 'bi-plug-fill',
        'Metalwork': 'bi-tools', 'Woodwork': 'bi-hammer',
        'Power Mechanics': 'bi-gear-fill', 'Drawing and Design': 'bi-pencil-fill',
        'Aviation Technology': 'bi-airplane-fill', 'Kenyan Sign Language': 'bi-hand-index-thumb',
    }
    _GROUP_META = {
        'II':  {'label': 'Sciences',                    'color': '#059669', 'icon': 'bi-beaker'},
        'III': {'label': 'Humanities',                  'color': '#0891b2', 'icon': 'bi-book-fill'},
        'IV':  {'label': 'Technical & Applied',         'color': '#d97706', 'icon': 'bi-tools'},
        'V':   {'label': 'Languages, Business & Music', 'color': '#db2777', 'icon': 'bi-music-note'},
    }

    compulsory_fields, groups_map = [], {g: [] for g, _ in _GC if g != 'I'}
    for subj in Subject.objects.all().order_by('group', 'name'):
        entry = (subj, form[f'subject_{subj.id}'], _ICONS.get(subj.name, 'bi-journal'))
        if subj.name in _COMP:
            compulsory_fields.append(entry)
        elif subj.group in groups_map:
            groups_map[subj.group].append(entry)

    optional_groups = [
        (_GROUP_META[g], groups_map[g])
        for g, _ in _GC if g != 'I' and groups_map.get(g)
    ]

    return render(request, 'career/degree_calculate.html', {
        'form': form,
        'compulsory_fields': compulsory_fields,
        'optional_groups': optional_groups,
    })


# ─────────────────────────────────────────────
# B2. DEGREE: Options page — shown after grade entry
# ─────────────────────────────────────────────
def degree_options(request):
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'calculate':
            precomputed = request.session.get('career_precomputed', {})
            request.session['career_cluster_points'] = precomputed
            request.session.pop('career_precomputed', None)
            return redirect('career:loading_page', pathway='degree')
        elif action == 'upload':
            return redirect('career:degree_upload')
        elif action == 'paste':
            return redirect('career:degree_paste')
        elif action == 'manual':
            return redirect('career:degree_manual')

    has_grades = bool(request.session.get('career_subject_grades'))
    return render(request, 'career/degree_options.html', {'has_grades': has_grades})


# ─────────────────────────────────────────────
# C. DEGREE: Upload KCSE slip OR cluster points doc → OCR via OpenAI Vision
# ─────────────────────────────────────────────

# Maps common KCSE slip abbreviations / alternate spellings → DB subject names
_SUBJECT_ALIASES = {
    # Core subjects
    'english language': 'english',
    'eng': 'english',
    'kis': 'kiswahili',
    'kiswahili language': 'kiswahili',
    'maths': 'mathematics',
    'math': 'mathematics',
    # Sciences
    'bio': 'biology',
    'chem': 'chemistry',
    'phy': 'physics',
    'phys': 'physics',
    # Humanities
    'history': 'history and government',
    'history & government': 'history and government',
    'hist': 'history and government',
    'geo': 'geography',
    'geog': 'geography',
    # Religious education
    'cre': 'christian religious education',
    'christian religious': 'christian religious education',
    'christian re': 'christian religious education',
    'c.r.e': 'christian religious education',
    'c.r.e.': 'christian religious education',
    'ire': 'islamic religious education',
    'islamic religious': 'islamic religious education',
    'i.r.e': 'islamic religious education',
    'i.r.e.': 'islamic religious education',
    'hre': 'hindu religious education',
    # Technical
    'bst': 'business studies',
    'business': 'business studies',
    'comp': 'computer studies',
    'computer science': 'computer studies',
    'it': 'computer studies',
    'ict': 'computer studies',
    'agri': 'agriculture',
    'art': 'art and design',
    'art & design': 'art and design',
    'home sc': 'home science',
    'home sciences': 'home science',
    # Technical subjects
    'building': 'building construction',
    'elec': 'electricity',
    'metal': 'metalwork',
    'wood': 'woodwork',
    'power mech': 'power mechanics',
    'drawing': 'drawing and design',
    'aviation': 'aviation technology',
    'ksl': 'kenyan sign language',
    'sign language': 'kenyan sign language',
    # Languages
    'fr': 'french',
    'ger': 'german',
    'arb': 'arabic',
    'arab': 'arabic',
}


def _extract_json_from_text(text: str) -> dict:
    """Pull the first JSON object out of any GPT response, handling code fences."""
    import json, re
    text = text.strip()
    # Remove code fences
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.I)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()
    # Try straight parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Walk brace pairs to extract the outermost JSON object (handles nested dicts)
    start = text.find('{')
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return {}


def _resolve_subject(name: str, all_subjects: dict):
    """Return Subject object or None; tries exact match then aliases."""
    key = name.lower().strip()
    # Direct match
    if key in all_subjects:
        return all_subjects[key]
    # Alias map
    mapped = _SUBJECT_ALIASES.get(key)
    if mapped and mapped in all_subjects:
        return all_subjects[mapped]
    # Partial match: if key is a substring of exactly one DB subject name
    matches = [s for s in all_subjects.values() if key in s.name.lower()]
    if len(matches) == 1:
        return matches[0]
    return None


def degree_upload(request):
    if request.method == 'POST':
        img = request.FILES.get('slip_image')
        if not img:
            messages.warning(request, 'Please select an image file to upload.')
            return render(request, 'career/degree_upload.html')

        from django.conf import settings as _settings
        api_key = getattr(_settings, 'OPENAI_API_KEY', '')

        if not api_key or api_key.startswith('sk-xxx'):
            messages.warning(
                request,
                'OCR is not configured yet — please add your OPENAI_API_KEY to the .env file. '
                'Enter your cluster points manually instead.'
            )
            return redirect('career:degree_manual')

        try:
            import base64, json, logging
            from openai import OpenAI

            log = logging.getLogger(__name__)
            img_bytes = img.read()
            mime = img.content_type or 'image/jpeg'

            # PDF → render first page to PNG in memory
            if mime == 'application/pdf' or img.name.lower().endswith('.pdf'):
                import fitz  # PyMuPDF
                doc = fitz.open(stream=img_bytes, filetype='pdf')
                page = doc[0]
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes('png')
                mime = 'image/png'
                doc.close()

            b64 = base64.b64encode(img_bytes).decode('utf-8')
            client = OpenAI(api_key=api_key)

            prompt = """You are reading a KUCCPS cluster points document issued in Kenya.
It contains cluster numbers (1–20) and their corresponding cluster point scores (0.0–48.0).

Extract every cluster number and its point score that you can see.

Return ONLY a JSON object in this exact format — no explanation, no extra text:
{"data": {"1": 42.5, "4": 38.2, "9": 35.0}}

Rules:
- Keys are cluster numbers as strings ("1" through "20").
- Values are the point scores as numbers (e.g. 42.5, not "42.5").
- Include every cluster whose score appears in the document.
- If no cluster points are visible, return {"data": {}}."""

            response = client.chat.completions.create(
                model='gpt-4o',
                messages=[{
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': prompt},
                        {'type': 'image_url', 'image_url': {
                            'url': f'data:{mime};base64,{b64}',
                            'detail': 'high',
                        }},
                    ],
                }],
                max_tokens=600,
            )

            raw = response.choices[0].message.content.strip()
            log.info('OCR cluster points raw response: %s', raw[:400])
            extracted = _extract_json_from_text(raw)

            if not extracted:
                raise ValueError('AI returned no parseable JSON — try a clearer photo')

            data = extracted.get('data', {})
            if not data:
                raise ValueError('No cluster points found in the document — make sure you upload a KUCCPS cluster points document')

            cluster_points = {}
            found = []
            for k, v in data.items():
                try:
                    num = int(str(k).strip())
                    if not (1 <= num <= 20):
                        continue
                    pts = max(0.0, min(48.0, float(v)))
                    cluster_points[str(num)] = pts
                    found.append(f'Cluster {num}: {pts:.1f}')
                except (ValueError, TypeError):
                    continue

            if not cluster_points:
                raise ValueError('No valid cluster numbers (1–20) with scores (0–48) found')

            request.session['career_pathway'] = 'Degree'
            request.session['career_degree_method'] = 'manual'
            request.session['career_cluster_points'] = cluster_points
            count = len(cluster_points)
            messages.success(
                request,
                f'Scanned {count} cluster score{"s" if count != 1 else ""}: '
                f'{", ".join(found[:6])}{"…" if count > 6 else ""}. '
                'Proceeding to your results.'
            )
            return redirect('career:loading_page', pathway='degree')

        except Exception as e:
            import logging
            logging.getLogger(__name__).error('OCR error: %s', e, exc_info=True)
            messages.warning(
                request,
                f'Could not read the document: {e}. '
                'Please enter your cluster points manually instead.'
            )
            return redirect('career:degree_manual')

    return render(request, 'career/degree_upload.html')


# ─────────────────────────────────────────────
# C2. DEGREE: Copy-paste cluster points
# ─────────────────────────────────────────────
def degree_paste(request):
    import re
    from clusters.models import Cluster
    from courses.models import CourseOffering, CourseType

    if request.method == 'POST':
        raw = request.POST.get('cluster_data', '')

        # Try KUCCPS format: "Cluster N\nVALUE" or "VALUE\tCluster N"
        named_pairs = re.findall(r'Cluster\s+(\d+)\s+([\d.]+)', raw, re.IGNORECASE)

        cluster_points = {}
        if named_pairs:
            # Named format — map directly by cluster number
            for cnum_str, val_str in named_pairs:
                try:
                    val = max(0.0, min(48.0, float(val_str)))
                    cluster_points[cnum_str] = val
                except ValueError:
                    pass
        else:
            # Fallback: plain numbers in order, map to clusters sequentially
            plain_vals = [v.strip() for v in re.split(r'[\s,;]+', raw) if v.strip()]
            try:
                clusters = list(Cluster.objects.all().order_by('number'))
            except Exception:
                clusters = []
            for i, cluster in enumerate(clusters):
                try:
                    val = max(0.0, min(48.0, float(plain_vals[i]))) if i < len(plain_vals) else 0.0
                except (ValueError, TypeError):
                    val = 0.0
                if cluster.kuccps_number is not None:
                    cluster_points[str(cluster.kuccps_number)] = val

        valid_vals = [v for v in cluster_points.values() if v > 0]
        if valid_vals:
            single = round(sum(valid_vals) / len(valid_vals), 2)
            request.session['career_pathway'] = 'Degree'
            request.session['career_degree_method'] = 'paste'
            request.session['career_cluster_points'] = cluster_points
            request.session['career_cluster_pts_single'] = single
            return redirect('career:loading_page', pathway='degree')

        messages.error(request, 'No valid cluster points found. Paste your KUCCPS cluster results and try again.')

    return render(request, 'career/degree_paste.html')


# ─────────────────────────────────────────────
# D. DEGREE: Manual cluster points entry
#    Also serves as the confirm/edit step after Calculate or Upload
# ─────────────────────────────────────────────
def degree_manual(request):
    import re as _re
    from clusters.models import Cluster

    # Only the ~20 master clusters that have SubjectGroups defined —
    # these are exactly what the KUCCPS formula uses for degree matching.
    all_clusters = list(
        Cluster.objects
        .filter(subject_groups__isnull=False)
        .distinct()
        .order_by('number')
    )

    # Group sub-clusters (e.g. 1A, 1B, 2A...) into 20 main KUCCPS groups
    _grouped = {}
    for c in all_clusters:
        m = _re.search(r'\((\d+)[A-Za-z]+\)', c.name)
        if m:
            main_num = int(m.group(1))
            if main_num not in _grouped:
                base_name = c.name[:c.name.rfind('(')].strip()
                _grouped[main_num] = {'main_num': main_num, 'name': base_name, 'subs': []}
            _grouped[main_num]['subs'].append(c)
        else:
            _grouped[id(c)] = {'main_num': None, 'name': c.name, 'subs': [c]}

    cluster_groups = sorted(
        _grouped.values(),
        key=lambda g: (g['main_num'] if g['main_num'] is not None else 999)
    )
    # Pre-build a comma-separated sub-cluster ID string for the template
    for grp in cluster_groups:
        grp['sub_ids'] = ','.join(str(c.id) for c in grp['subs'])

    precomputed = request.session.get('career_precomputed', {})
    calc_single = request.session.get('career_cluster_pts_single')

    if request.method == 'POST':
        cluster_points = {}
        for grp in cluster_groups:
            raw = request.POST.get(f'group_{grp["main_num"]}', '').strip()
            try:
                val = max(0.0, min(48.0, float(raw)))
            except (ValueError, TypeError):
                # Fall back to precomputed value keyed by KUCCPS group number
                knum = grp['main_num']
                val = float(precomputed.get(str(knum), 0)) if knum is not None else 0.0
            # Store by KUCCPS group number (1-20) — matches career_results lookup
            if grp['main_num'] is not None:
                cluster_points[str(grp['main_num'])] = val

        request.session['career_pathway'] = 'Degree'
        request.session['career_degree_method'] = request.session.get('career_degree_method', 'manual')
        request.session['career_cluster_points'] = cluster_points
        request.session.pop('career_precomputed', None)

        return redirect('career:loading_page', pathway='degree')

    return render(request, 'career/degree_manual.html', {
        'cluster_groups': cluster_groups,
        'precomputed': precomputed,
        'calc_single': calc_single,
        'from_calculate': bool(precomputed),
    })


# ─────────────────────────────────────────────
# E. PATHWAY INPUT: Diploma / Certificate / KMTC / TTC / Artisan
# ─────────────────────────────────────────────
def pathway_input(request, pathway):
    from clusterpoints.forms import KCSEForm

    pathway_label = PATHWAY_SLUG_TO_LABEL.get(pathway.lower())
    if not pathway_label:
        return redirect('career:home')

    use_kcse_form = pathway.lower() in ('diploma', 'certificate', 'kmtc', 'artisan')

    if request.method == 'POST':
        request.session['career_pathway'] = pathway_label
        request.session['career_categories'] = request.POST.getlist('categories')
        request.session['career_counties'] = request.POST.getlist('counties')
        request.session['career_institution_type'] = request.POST.get('institution_type', '').strip()

        if use_kcse_form:
            form = KCSEForm(request.POST)
            if form.is_valid():
                from clusters.models import Subject
                points_by_id = form.get_points_dict()
                subjects = Subject.objects.filter(id__in=points_by_id.keys())
                pts_by_name = {s.name: points_by_id[s.id] for s in subjects}

                working = pts_by_name.copy()
                agg = []
                if 'Mathematics' in working:
                    agg.append(working.pop('Mathematics'))
                lang_scores = {lang: working.pop(lang) for lang in ['English', 'Kiswahili'] if lang in working}
                if lang_scores:
                    best = max(lang_scores, key=lambda k: lang_scores[k])
                    agg.append(lang_scores[best])
                    for lang, pts in lang_scores.items():
                        if lang != best:
                            working[lang] = pts
                agg += sorted(working.values(), reverse=True)[:5]
                aggregate_total = sum(agg)
                mean_grade = _aggregate_to_mean_grade(aggregate_total)
                request.session['career_mean_grade'] = mean_grade
                request.session['career_subject_grades'] = {k.lower(): v for k, v in pts_by_name.items()}
                return redirect('career:loading_page', pathway=pathway.lower())
            # Fall through to re-render with errors
        else:
            request.session['career_mean_grade'] = request.POST.get('mean_grade', '').strip()
            return redirect('career:loading_page', pathway=pathway.lower())
    else:
        if use_kcse_form and request.GET.get('edit'):
            # Pre-populate form from stored session grades
            from clusters.models import Subject as _EditSubj
            stored = request.session.get('career_subject_grades', {})
            if stored:
                name_to_id = {s.name.lower(): s.id for s in _EditSubj.objects.all()}
                initial = {
                    f'subject_{name_to_id[name]}': pts
                    for name, pts in stored.items()
                    if name in name_to_id
                }
                form = KCSEForm(initial=initial)
            else:
                form = KCSEForm()
        else:
            form = KCSEForm() if use_kcse_form else None

    current_mean_grade = request.session.get('career_mean_grade', '') if request.GET.get('edit') else ''

    # Build pill-button context for diploma/certificate grade entry
    compulsory_fields, optional_groups = [], []
    if use_kcse_form and form is not None:
        from clusters.models import GROUP_CHOICES as _GC2, Subject as _Subj2
        from clusterpoints.forms import COMPULSORY_SUBJECT_NAMES as _COMP2
        _ICONS2 = {
            'English': 'bi-book-half', 'Kiswahili': 'bi-translate',
            'Mathematics': 'bi-calculator-fill', 'Chemistry': 'bi-droplet-fill',
            'Biology': 'bi-flower1', 'Physics': 'bi-lightning-charge-fill',
            'Geography': 'bi-globe2', 'History and Government': 'bi-bank',
            'Christian Religious Education': 'bi-book', 'Islamic Religious Education': 'bi-moon-stars-fill',
            'Hindu Religious Education': 'bi-sun', 'Computer Studies': 'bi-laptop',
            'Agriculture': 'bi-tree-fill', 'Business Studies': 'bi-graph-up-arrow',
            'Home Science': 'bi-house-heart', 'Art and Design': 'bi-palette-fill',
            'Music': 'bi-music-note-beamed', 'French': 'bi-chat-left-text',
            'German': 'bi-chat-left-text', 'Arabic': 'bi-chat-left-text-fill',
            'Building Construction': 'bi-building', 'Electricity': 'bi-plug-fill',
            'Metalwork': 'bi-tools', 'Woodwork': 'bi-hammer',
            'Power Mechanics': 'bi-gear-fill', 'Drawing and Design': 'bi-pencil-fill',
            'Aviation Technology': 'bi-airplane-fill', 'Kenyan Sign Language': 'bi-hand-index-thumb',
        }
        _GM2 = {
            'II':  {'label': 'Sciences',                    'color': '#059669', 'icon': 'bi-beaker'},
            'III': {'label': 'Humanities',                  'color': '#0891b2', 'icon': 'bi-book-fill'},
            'IV':  {'label': 'Technical & Applied',         'color': '#d97706', 'icon': 'bi-tools'},
            'V':   {'label': 'Languages, Business & Music', 'color': '#db2777', 'icon': 'bi-music-note'},
        }
        _gmap = {g: [] for g, _ in _GC2 if g != 'I'}
        for _s in _Subj2.objects.all().order_by('group', 'name'):
            _e = (_s, form[f'subject_{_s.id}'], _ICONS2.get(_s.name, 'bi-journal'))
            if _s.name in _COMP2:
                compulsory_fields.append(_e)
            elif _s.group in _gmap:
                _gmap[_s.group].append(_e)
        optional_groups = [(_GM2[g], _gmap[g]) for g, _ in _GC2 if g != 'I' and _gmap.get(g)]

    return render(request, 'career/pathway_input.html', {
        'pathway': pathway.lower(),
        'pathway_label': pathway_label,
        'mean_grades': MEAN_GRADES,
        'tvet_categories': TVET_CATEGORIES,
        'use_kcse_form': use_kcse_form,
        'form': form,
        'compulsory_fields': compulsory_fields,
        'optional_groups': optional_groups,
        'current_mean_grade': current_mean_grade,
        'is_edit': bool(request.GET.get('edit')),
        'kenyan_counties': KENYAN_COUNTIES if pathway.lower() == 'artisan' else [],
    })


# ─────────────────────────────────────────────
# F. LOADING PAGE — animated processing stages
# ─────────────────────────────────────────────
def loading_page(request, pathway):
    results_url = reverse('career:career_results')
    return render(request, 'career/loading.html', {
        'pathway': pathway.lower(),
        'results_url': results_url,
    })


# ─────────────────────────────────────────────
# G. CAREER RESULTS — unified session-driven results
# ─────────────────────────────────────────────
def career_results(request):
    from courses.models import CourseOffering, CourseType
    from predictor.services import predict_cutoff as _predict_cutoff, TREND_ICON, TREND_COLOR, TREND_TIP
    from payments.services import has_paid_for_feature, is_feature_enabled

    is_guest = not request.user.is_authenticated

    pathway             = request.session.get('career_pathway', '')
    filter_chance       = request.GET.get('chance', '')
    filter_tier         = request.GET.get('tier', '')
    search_q            = request.GET.get('q', '').strip()
    sort_by             = request.GET.get('sort', 'tier')

    if not pathway:
        messages.info(request, "Your session has expired. Please start the Career Engine again.")
        return redirect('career:home')

    # Guard: score data must still be in session (it's separate from pathway and expires independently)
    if pathway == 'Degree':
        _has_score = bool(
            request.session.get('career_cluster_pts_single') or
            request.session.get('career_cluster_points')
        )
    else:
        _has_score = bool(request.session.get('career_mean_grade'))
    if not _has_score:
        messages.info(request, "Your session expired. Please re-enter your grades to see results.")
        return redirect('career:home')

    cfg = _get_career_config()

    matches             = []
    cluster_pts_single  = float(request.session.get('career_cluster_pts_single', 0) or 0)
    mean_grade          = request.session.get('career_mean_grade', '')
    subject_grades      = request.session.get('career_subject_grades', {})
    cluster_points_dict = {}

    def _enrich_pred(offering):
        """Return prediction dict with trend decorators, or None."""
        try:
            p = _predict_cutoff(getattr(offering, 'cutoff_points', None))
            if p:
                p['trend_icon']  = TREND_ICON[p['trend']]
                p['trend_color'] = TREND_COLOR[p['trend']]
                p['trend_tip']   = TREND_TIP[p['trend']]
            return p
        except Exception:
            return None

    if pathway == 'Degree':
        cluster_points_dict = request.session.get('career_cluster_points', {})
        degree_type = CourseType.objects.filter(name__icontains='Degree').first()

        if degree_type:
            qs = (
                CourseOffering.objects
                .filter(course__course_type=degree_type)
                .select_related(
                    'course', 'course__cluster', 'course__category', 'course__course_type',
                    'institution', 'institution__institution_type',
                )
                .exclude(cutoff_points__isnull=True)
            )
            if search_q:
                qs = qs.filter(course__name__icontains=search_q)

            for offering in qs:
                cutoff = offering.latest_cutoff()
                if cutoff is None:
                    continue

                if subject_grades and offering.course.subject_requirements:
                    if not _meets_subject_requirements(offering.course.subject_requirements, subject_grades):
                        continue

                cluster     = offering.course.cluster
                if cluster and cluster_points_dict:
                    knum        = cluster.kuccps_number
                    student_pts = float(cluster_points_dict.get(str(knum), cluster_pts_single)) if knum else cluster_pts_single
                else:
                    student_pts = cluster_pts_single
                diff        = round(student_pts - float(cutoff), 2)

                chance, badge    = _chance_from_diff(diff)
                tier, tier_order = _tier_from_diff(diff, cfg)

                if filter_chance and chance != filter_chance:
                    continue
                if filter_tier and tier != filter_tier:
                    continue

                matches.append({
                    'offering':       offering,
                    'course':         offering.course,
                    'institution':    offering.institution,
                    'cluster':        cluster,
                    'cutoff':         cutoff,
                    'student_points': round(student_pts, 1),
                    'diff':           diff,
                    'chance':         chance,
                    'chance_desc':    CHANCE_DESC.get(chance, ''),
                    'badge':          badge,
                    'tier':           tier,
                    'tier_order':     tier_order,
                    'tier_color':     TIER_META[tier][1],
                    'tier_css':       TIER_META[tier][2],
                    'tier_desc':      TIER_META[tier][3],
                    'pred':           _enrich_pred(offering),
                    'is_competitive': float(cutoff) >= cfg.competitive_threshold,
                    'course_url':     _build_course_url(offering.course),
                })

    else:
        student_pts = GRADE_POINTS.get(mean_grade, 0)
        type_names  = COURSE_TYPE_MAP.get(pathway, [])

        if type_names:
            qs = (
                CourseOffering.objects
                .filter(course__course_type__name__in=type_names)
                .select_related(
                    'course', 'course__course_type', 'course__category',
                    'institution', 'institution__institution_type',
                )
            )
            if search_q:
                qs = qs.filter(course__name__icontains=search_q)

            # Category filter — narrow to preferred programme areas
            _categories = request.session.get('career_categories', [])
            if _categories:
                qs = qs.filter(course__category__name__in=_categories)

            default_min = PATHWAY_DEFAULT_MIN_GRADE.get(pathway, 'E')
            for offering in qs:
                course    = offering.course

                # Layer 1a: subject requirements (Diploma/Certificate only — KMTC/TTC enter mean grade only)
                if subject_grades and course.subject_requirements:
                    if not _meets_subject_requirements(course.subject_requirements, subject_grades):
                        continue

                min_grade = (course.minimum_mean_grade or '').strip() or default_min
                min_pts   = GRADE_POINTS.get(min_grade, 0)
                diff      = student_pts - min_pts

                # Layer 1b: hard grade filter — student must meet the minimum mean grade
                if diff < 0:
                    continue

                chance, badge    = _chance_from_grade_diff(diff)
                tier, tier_order = _tier_from_diff(diff, cfg)

                # Layer 3: qualification label for display/PDF
                if diff == 0:
                    qual_label = 'Meets Minimum'
                elif diff <= 2:
                    qual_label = 'Comfortably Qualifies'
                else:
                    qual_label = 'Strongly Qualifies'

                if filter_chance and chance != filter_chance:
                    continue
                if filter_tier and tier != filter_tier:
                    continue

                matches.append({
                    'offering':        offering,
                    'course':          course,
                    'institution':     offering.institution,
                    'cluster':         None,
                    'cutoff':          min_grade or '—',
                    'min_pts':         min_pts,
                    'student_points':  mean_grade,
                    'diff':            diff,
                    'chance':          chance,
                    'chance_desc':     CHANCE_DESC.get(chance, ''),
                    'badge':           badge,
                    'tier':            tier,
                    'tier_order':      tier_order,
                    'tier_color':      TIER_META[tier][1],
                    'tier_css':        TIER_META[tier][2],
                    'tier_desc':       TIER_META[tier][3],
                    'qual_label':      qual_label,
                    'pred':            None,
                    'is_competitive':  False,
                    'course_url':      _build_course_url(course),
                    'has_specific_min': bool((course.minimum_mean_grade or '').strip()),
                })

    if pathway == 'Degree':
        if sort_by == 'tier':
            def _tier_key(m):
                cutoff_val = (
                    float(m['cutoff'])
                    if isinstance(m['cutoff'], (int, float))
                    else GRADE_POINTS.get(str(m['cutoff']).strip(), 0)
                )
                if m['tier_order'] == 1:
                    return (m['tier_order'], -cutoff_val)
                return (m['tier_order'], abs(m['diff']))
            matches.sort(key=_tier_key)
        elif sort_by == 'chance':
            _CHANCE_ORDER = {'High Likelihood': 0, 'Likely': 1, 'Borderline': 2, 'Unlikely': 3}
            matches.sort(key=lambda m: (_CHANCE_ORDER.get(m['chance'], 4), abs(m['diff'])))
        elif sort_by == 'institution':
            matches.sort(key=lambda m: m['institution'].name)
        elif sort_by == 'course':
            matches.sort(key=lambda m: m['course'].name)
    else:
        # Non-degree: default sort by required grade descending (most selective first),
        # then by student margin, then alphabetically — gives meaningful ordering even
        # when all courses share the same pathway-default minimum.
        if sort_by in ('tier', 'chance'):
            matches.sort(key=lambda m: (-m.get('min_pts', 0), -m['diff'], m['course'].name))
        elif sort_by == 'institution':
            matches.sort(key=lambda m: (m['institution'].name, -m.get('min_pts', 0)))
        elif sort_by == 'course':
            matches.sort(key=lambda m: m['course'].name)

    tier_counts = {}
    for m in matches:
        key = m['tier'].replace(' ', '')
        tier_counts[key] = tier_counts.get(key, 0) + 1

    # ── Persist snapshot for logged-in users (powers Personalised Dashboard) ──
    if request.user.is_authenticated and matches and not filter_tier and not filter_chance and not search_q:
        try:
            from accounts.models import CareerSessionSnapshot
            sorted_top = sorted(matches, key=lambda m: (m['tier_order'], abs(m['diff'])))[:10]
            top_json = [{
                'course_id':        _m['offering'].course.id,
                'offering_id':      _m['offering'].id,
                'course_name':      _m['course'].name,
                'institution_name': _m['institution'].name,
                'tier':             _m['tier'],
                'tier_css':         _m['tier_css'],
                'tier_color':       _m['tier_color'],
                'diff':             _m['diff'],
                'chance':           _m['chance'],
                'cutoff':           _m['cutoff'],
                'student_pts':      float(_m['student_points']) if isinstance(_m['student_points'], (int, float)) else 0,
                'kuccps_num':       _m['cluster'].kuccps_number if _m['cluster'] else None,
                'cluster_name':     _m['cluster'].name if _m['cluster'] else '',
            } for _m in sorted_top]
            CareerSessionSnapshot.objects.filter(
                user=request.user, pathway=pathway
            ).delete()
            CareerSessionSnapshot.objects.create(
                user=request.user,
                pathway=pathway,
                cluster_points_json=cluster_points_dict,
                mean_grade=mean_grade,
                aggregate_score=cluster_pts_single,
                total_matches=len(matches),
                tier_counts_json=tier_counts,
                top_matches_json=top_json,
            )
        except Exception:
            pass  # never let snapshot saving break the results page

    from analytics.utils import log_career_engine
    log_career_engine(request, pathway=pathway, result_count=len(matches), mean_grade=mean_grade)

    # ── Backup Plan (Degree only, no active filters) ──────────────────────────
    backup_plan = []
    if pathway == 'Degree' and not filter_chance and not filter_tier and not search_q:
        from collections import defaultdict

        qual_matches   = [m for m in matches if m['diff'] >= 0]
        missed_matches = [m for m in matches if m['diff'] < -1]  # meaningfully below cutoff

        if missed_matches and qual_matches:
            qual_by_cluster = defaultdict(list)
            for m in qual_matches:
                if m['cluster']:
                    qual_by_cluster[m['cluster'].id].append(m)

            seen = set()
            for m in missed_matches:
                if not m['cluster']:
                    continue
                cid = m['cluster'].id
                if cid in seen:
                    continue
                seen.add(cid)

                alts = qual_by_cluster.get(cid, [])
                if not alts:
                    continue

                # aspiration = the missed course closest to qualifying in this cluster
                cluster_missed = [x for x in missed_matches if x['cluster'] and x['cluster'].id == cid]
                aspiration     = max(cluster_missed, key=lambda x: x['diff'])

                # show up to 3 qualifying alternatives, closest cutoff first
                alts_sorted = sorted(alts, key=lambda a: a['diff'])[:3]

                backup_plan.append({
                    'cluster':    m['cluster'],
                    'aspiration': aspiration,
                    'alts':       alts_sorted,
                    'gap':        abs(round(aspiration['diff'], 1)),
                })

            # show clusters with smallest gap first (most "reachable" aspirations)
            backup_plan.sort(key=lambda p: p['gap'])
            backup_plan = backup_plan[:4]  # cap at 4 cluster cards

    saved_ids: set = set()
    if request.user.is_authenticated:
        try:
            from accounts.models import SavedCourse
            saved_ids = set(SavedCourse.objects.filter(user=request.user).values_list('course_id', flat=True))
        except Exception:
            pass

    # Attach job market data to every match (in-memory dict lookup, no extra DB queries)
    try:
        from career.job_market import get_jmd_for_course
        for m in matches:
            m['job_market'] = get_jmd_for_course(m.get('course'))
    except Exception:
        pass

    paginator = Paginator(matches, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    _LABEL_TO_SLUG = {v: k for k, v in PATHWAY_SLUG_TO_LABEL.items()}
    _pathway_slug  = _LABEL_TO_SLUG.get(pathway, pathway.lower())
    if pathway == 'Degree':
        _edit_url = reverse('career:degree_calculate')
    elif _pathway_slug:
        _edit_url = reverse('career:pathway_input', kwargs={'pathway': _pathway_slug}) + '?edit=1'
    else:
        _edit_url = reverse('career:home')

    # Payment gate — computed after matches so we can show the real count on the overlay
    from payments.services import price_for_feature as _price_for
    _is_locked = (
        not is_guest
        and is_feature_enabled('premium_career_report')
        and not has_paid_for_feature(request.user, 'premium_career_report')
    )
    _gate_items = [
        "Your full personalised course list — filtered for YOUR exact cluster points",
        "Admission probability for every course: Very High, Likely, Borderline, Long Shot",
        "Cutoff trend analysis — see if competition is rising or falling this season",
        "Smart Backup Plan: ranked alternatives if your top choice is out of reach",
        "Save & shortlist your favourites for KUCCPS application season",
        "Share your results with family via WhatsApp in one tap",
    ]

    return render(request, 'career/career_results_v2.html', {
        'page_obj':            page_obj,
        'pathway':             pathway,
        'total_count':         len(matches),
        'filter_chance':       filter_chance,
        'filter_tier':         filter_tier,
        'search_q':            search_q,
        'sort_by':             sort_by,
        'mean_grade':          mean_grade,
        'cluster_pts_single':  cluster_pts_single,
        'best_cluster_pts':    max(cluster_points_dict.values(), default=cluster_pts_single) if cluster_points_dict else cluster_pts_single,
        'tier_counts':         tier_counts,
        'tier_meta':           TIER_META,
        'has_per_cluster':     bool(cluster_points_dict),
        'saved_ids':           list(saved_ids),
        'backup_plan':         backup_plan,
        'edit_url':            _edit_url,
        'clear_url':           reverse('career:clear_session'),
        'guest':               is_guest,
        'is_locked':           _is_locked,
        'gate_feature':        'premium_career_report',
        'gate_price':          _price_for('premium_career_report'),
        'gate_items':          _gate_items,
        'gate_subtext':        f"We've scanned every university, KMTC, TVET & TTC in Kenya against your exact grades — {len(matches)} courses are waiting for you.",
    })


# ─────────────────────────────────────────────
# H1. CLEAR CAREER SESSION
# ─────────────────────────────────────────────
def clear_session(request):
    """Wipe all career engine session keys and restart from home."""
    for key in list(request.session.keys()):
        if key.startswith('career_'):
            del request.session[key]
    return redirect('career:home')


# ─────────────────────────────────────────────
# H. CAREER PDF DOWNLOADS
# ─────────────────────────────────────────────

def _build_career_matches(request):
    """
    Build all career course matches from session data (shared by both PDF views).
    Returns (matches, pathway, cluster_pts_single, mean_grade, cluster_points_dict).
    """
    from courses.models import CourseOffering, CourseType
    from predictor.services import predict_cutoff as _predict_cutoff, TREND_ICON, TREND_COLOR, TREND_TIP

    pathway             = request.session.get('career_pathway', '')
    cluster_pts_single  = float(request.session.get('career_cluster_pts_single', 0) or 0)
    mean_grade          = request.session.get('career_mean_grade', '')
    subject_grades      = request.session.get('career_subject_grades', {})
    cluster_points_dict = {}
    matches             = []
    cfg                 = _get_career_config()

    def _enrich_pred(offering):
        try:
            p = _predict_cutoff(getattr(offering, 'cutoff_points', None))
            if p:
                p['trend_icon']  = TREND_ICON[p['trend']]
                p['trend_color'] = TREND_COLOR[p['trend']]
                p['trend_tip']   = TREND_TIP[p['trend']]
            return p
        except Exception:
            return None

    if pathway == 'Degree':
        cluster_points_dict = request.session.get('career_cluster_points', {})
        degree_type = CourseType.objects.filter(name__icontains='Degree').first()
        if degree_type:
            qs = (
                CourseOffering.objects
                .filter(course__course_type=degree_type)
                .select_related(
                    'course', 'course__cluster', 'course__category', 'course__course_type',
                    'institution', 'institution__institution_type',
                )
                .exclude(cutoff_points__isnull=True)
            )
            for offering in qs:
                cutoff = offering.latest_cutoff()
                if cutoff is None:
                    continue
                if subject_grades and offering.course.subject_requirements:
                    if not _meets_subject_requirements(offering.course.subject_requirements, subject_grades):
                        continue
                cluster     = offering.course.cluster
                if cluster and cluster_points_dict:
                    knum        = cluster.kuccps_number
                    student_pts = float(cluster_points_dict.get(str(knum), cluster_pts_single)) if knum else cluster_pts_single
                else:
                    student_pts = cluster_pts_single
                diff        = round(student_pts - float(cutoff), 2)
                chance, badge    = _chance_from_diff(diff)
                tier, tier_order = _tier_from_diff(diff, cfg)
                matches.append({
                    'course':         offering.course,
                    'institution':    offering.institution,
                    'cluster':        cluster,
                    'cutoff':         cutoff,
                    'student_points': round(student_pts, 1),
                    'diff':           diff,
                    'chance':         chance,
                    'tier':           tier,
                    'tier_order':     tier_order,
                    'pred':           _enrich_pred(offering),
                    'is_competitive': float(cutoff) >= cfg.competitive_threshold,
                })
    else:
        student_pts_val = GRADE_POINTS.get(mean_grade, 0)
        type_names      = COURSE_TYPE_MAP.get(pathway, [])
        if type_names:
            qs = (
                CourseOffering.objects
                .filter(course__course_type__name__in=type_names)
                .select_related(
                    'course', 'course__course_type', 'course__category',
                    'institution', 'institution__institution_type',
                )
            )
            # Category filter
            _categories = request.session.get('career_categories', [])
            if _categories:
                qs = qs.filter(course__category__name__in=_categories)

            default_min = PATHWAY_DEFAULT_MIN_GRADE.get(pathway, 'E')
            for offering in qs:
                course = offering.course
                if subject_grades and course.subject_requirements:
                    if not _meets_subject_requirements(course.subject_requirements, subject_grades):
                        continue
                min_grade = (course.minimum_mean_grade or '').strip() or default_min
                min_pts   = GRADE_POINTS.get(min_grade, 0)
                diff      = student_pts_val - min_pts
                if diff < 0:
                    continue
                chance, badge    = _chance_from_grade_diff(diff)
                tier, tier_order = _tier_from_diff(diff, cfg)
                if diff == 0:
                    qual_label = 'Meets Minimum'
                elif diff <= 2:
                    qual_label = 'Comfortably Qualifies'
                else:
                    qual_label = 'Strongly Qualifies'
                matches.append({
                    'course':         course,
                    'institution':    offering.institution,
                    'cluster':        None,
                    'cutoff':         min_grade or '—',
                    'student_points': mean_grade,
                    'diff':           diff,
                    'chance':         chance,
                    'tier':           tier,
                    'tier_order':     tier_order,
                    'qual_label':     qual_label,
                    'pred':           None,
                    'is_competitive': False,
                })

    if pathway == 'Degree':
        matches.sort(key=lambda m: (m['tier_order'], abs(m['diff'])))
    else:
        matches.sort(key=lambda m: (-m['diff'], m['course'].name))

    # Build 20-group KUCCPS cluster score table for PDF display.
    # career_cluster_points is now keyed by KUCCPS group number (1-20 as strings).
    cluster_score_table = []   # list of (kuccps_num, group_name, score)
    if pathway == 'Degree' and cluster_points_dict:
        from clusters.models import Cluster as _Cluster
        import re as _re2
        # Build a name lookup: kuccps_num → clean group name
        # Use sub-clusters (numbered 1-99 in DB) to get official KUCCPS group names
        knum_to_name = {}
        for cl in _Cluster.objects.filter(number__lt=100).exclude(number__isnull=True):
            kn = cl.kuccps_number
            if kn and kn not in knum_to_name:
                clean = _re2.sub(r'\s*\(\d+[A-Za-z]*\)\s*$', '', cl.name).strip()
                knum_to_name[kn] = clean
        # Fallback names from master clusters if sub-cluster name not found
        for cl in _Cluster.objects.filter(number__gte=100):
            kn = cl.kuccps_number
            if kn and kn not in knum_to_name:
                knum_to_name[kn] = cl.name

        for kn_str, score in sorted(cluster_points_dict.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
            try:
                knum = int(kn_str)
            except ValueError:
                continue
            name  = knum_to_name.get(knum, f'Cluster {knum}')
            cluster_score_table.append((knum, name, round(float(score), 1)))

    return matches, pathway, cluster_pts_single, mean_grade, cluster_points_dict, cluster_score_table


def career_results_pdf_quick(request):
    """Quick summary PDF — compact landscape table of all course matches."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from django.http import HttpResponse
    from django.utils import timezone

    matches, pathway, cluster_pts_single, mean_grade, _, cluster_score_table = _build_career_matches(request)
    if not matches:
        return HttpResponse(
            "No career matches found. Please run the career guidance tool first.",
            status=400,
        )

    numeric_pts = [m['student_points'] for m in matches if isinstance(m['student_points'], (int, float))]
    best_pts    = max(numeric_pts, default=cluster_pts_single) if pathway == 'Degree' else None

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="careernext_career_matches.pdf"'

    c = canvas.Canvas(response, pagesize=landscape(A4))
    W, H = landscape(A4)

    NAVY  = colors.HexColor("#1e3a8a")
    SLATE = colors.HexColor("#64748b")
    LIGHT = colors.HexColor("#f1f5f9")

    TIER_COLORS = {
        'Best Match':     colors.HexColor("#059669"),
        'Stretch':        colors.HexColor("#d97706"),
        'Safe Option':    colors.HexColor("#2563eb"),
        'Easy Admission': colors.HexColor("#64748b"),
        'Long Shot':      colors.HexColor("#dc2626"),
    }
    CHANCE_COLORS = {
        'High Likelihood': colors.HexColor("#16a34a"),
        'Likely':          colors.HexColor("#059669"),
        'Borderline':      colors.HexColor("#f97316"),
        'Unlikely':        colors.HexColor("#dc2626"),
    }

    page_num = [0]

    def new_page():
        page_num[0] += 1
        if page_num[0] > 1:
            c.showPage()
        c.setFillColor(NAVY)
        c.rect(0, H - 1.5*cm, W, 1.5*cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(1.5*cm, H - 0.95*cm, "CareerNext — Career Course Matches Summary")
        c.setFont("Helvetica", 9)
        c.drawRightString(W - 1.5*cm, H - 0.95*cm, f"Page {page_num[0]}")
        c.setFillColor(colors.HexColor("#0e7490"))
        c.rect(0, 1.35*cm, W, 0.08*cm, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.rect(0, 0, W, 1.35*cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(W / 2, 0.82*cm,
            "careernext.co.ke  —  Your Journey Begins Here")
        c.setFont("Helvetica", 6.5)
        c.setFillColor(colors.HexColor("#93c5fd"))
        c.drawCentredString(W / 2, 0.45*cm,
            "For guidance only. Verify all cutoffs on the official KUCCPS portal (kuccps.net) before applying.")
        c.setFillColor(colors.black)
        return H - 1.9*cm

    y = new_page()

    # Profile line
    score_txt = f"Your Score: {best_pts:.1f} / 48 pts" if best_pts is not None else f"Mean Grade: {mean_grade}"
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(NAVY)
    c.drawString(1.5*cm, y, f"Pathway: {pathway}   |   {score_txt}   |   Total Matches: {len(matches)}")
    y -= 0.45*cm
    c.setFont("Helvetica", 8)
    c.setFillColor(SLATE)
    c.drawString(1.5*cm, y, f"Generated: {timezone.now().strftime('%d %B %Y %H:%M')}")
    y -= 0.65*cm

    if pathway == 'Degree':
        # ── Degree: cluster scores mini-table ────────────────────────────────
        if cluster_score_table:
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(NAVY)
            c.drawString(1.5*cm, y, "YOUR CLUSTER SCORES (KUCCPS Groups 1–20, out of 48 pts)")
            y -= 0.4*cm
            col_w = (W - 3*cm) / 4
            GREEN = colors.HexColor("#16a34a")
            for i, (knum, gname, score) in enumerate(cluster_score_table):
                col = i % 4
                if col == 0 and i > 0:
                    y -= 0.5*cm
                x = 1.5*cm + col * col_w
                bar_max = col_w - 1.4*cm
                bar_w   = (score / 48.0) * bar_max if score else 0
                bar_col = GREEN if score >= 36 else (NAVY if score >= 24 else colors.HexColor("#f97316"))
                c.setFillColor(LIGHT)
                c.rect(x + 1.05*cm, y - 0.28*cm, bar_max, 0.16*cm, fill=1, stroke=0)
                c.setFillColor(bar_col)
                c.rect(x + 1.05*cm, y - 0.28*cm, bar_w, 0.16*cm, fill=1, stroke=0)
                c.setFont("Helvetica", 7.5)
                c.setFillColor(colors.black)
                c.drawString(x, y, f"C{knum}: {score:.1f}")
            y -= 0.65*cm
        elif best_pts:
            c.setFont("Helvetica", 8)
            c.setFillColor(SLATE)
            c.drawString(1.5*cm, y, f"Single score {best_pts:.1f} pts applied to all clusters")
            y -= 0.45*cm

        y -= 0.25*cm

        COL = {
            'course':  1.6*cm, 'inst': 9.8*cm, 'cluster': 16.0*cm,
            'tier': 17.8*cm, 'chance': 21.0*cm, 'cutoff': 24.5*cm,
            'pred': 26.3*cm, 'diff': 28.1*cm,
        }

        def draw_headers():
            nonlocal y
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(SLATE)
            c.drawString(COL['course'],  y, "COURSE")
            c.drawString(COL['inst'],    y, "INSTITUTION")
            c.drawString(COL['cluster'], y, "CLUST")
            c.drawString(COL['tier'],    y, "TIER")
            c.drawString(COL['chance'],  y, "LIKELIHOOD")
            c.drawString(COL['cutoff'],  y, "CUTOFF")
            c.drawString(COL['pred'],    y, "EST 2026")
            c.drawString(COL['diff'],    y, "DIFF")
            y -= 0.1*cm
            c.setStrokeColor(colors.HexColor("#cbd5e1"))
            c.line(1.5*cm, y, W - 1.5*cm, y)
            y -= 0.4*cm
            c.setFillColor(colors.black)

        draw_headers()

        for i, m in enumerate(matches):
            if y < 2.0*cm:
                y = new_page()
                draw_headers()
            if i % 2 == 0:
                c.setFillColor(LIGHT)
                c.rect(1.5*cm, y - 0.22*cm, W - 3*cm, 0.36*cm, fill=1, stroke=0)
            c.setFont("Helvetica", 7.5)
            c.setFillColor(colors.black)
            course_name = m['course'].name
            if len(course_name) > 44:
                course_name = course_name[:42] + '…'
            c.drawString(COL['course'], y, course_name)
            inst_name = m['institution'].name
            if len(inst_name) > 30:
                inst_name = inst_name[:28] + '…'
            c.drawString(COL['inst'], y, inst_name)
            knum = m['cluster'].kuccps_number if m['cluster'] else None
            c.drawString(COL['cluster'], y, f"C{knum}" if knum else '—')
            c.setFillColor(TIER_COLORS.get(m['tier'], colors.grey))
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(COL['tier'], y, m['tier'][:14])
            c.setFillColor(CHANCE_COLORS.get(m['chance'], colors.grey))
            chance_abbr = {'High Likelihood': 'High Like.', 'Likely': 'Likely',
                           'Borderline': 'Borderline', 'Unlikely': 'Unlikely'}.get(m['chance'], m['chance'])
            c.drawString(COL['chance'], y, chance_abbr)
            c.setFont("Helvetica", 7.5)
            c.setFillColor(colors.black)
            c.drawString(COL['cutoff'], y, str(m['cutoff'])[:6])
            pred = m.get('pred')
            c.drawString(COL['pred'], y, f"{pred['predicted']:.1f}" if pred else '—')
            diff_val = m['diff']
            diff_str = f"+{diff_val:.1f}" if diff_val >= 0 else f"{diff_val:.1f}"
            c.setFillColor(colors.HexColor("#15803d") if diff_val >= 0 else colors.HexColor("#dc2626"))
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(COL['diff'], y, diff_str)
            y -= 0.41*cm

    else:
        # ── Non-degree: columns suited to KMTC / TTC / Diploma / Certificate ──
        y -= 0.25*cm

        COL_ND = {
            'course':    1.6*cm,
            'inst':      9.0*cm,
            'location':  17.0*cm,
            'category':  20.5*cm,
            'chance':    24.0*cm,
            'min_grade': 26.5*cm,
            'qual':      27.8*cm,
        }

        def draw_headers_nd():
            nonlocal y
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(SLATE)
            c.drawString(COL_ND['course'],    y, "COURSE / PROGRAMME")
            c.drawString(COL_ND['inst'],      y, "INSTITUTION")
            c.drawString(COL_ND['location'],  y, "LOCATION")
            c.drawString(COL_ND['category'],  y, "CATEGORY")
            c.drawString(COL_ND['chance'],    y, "LIKELIHOOD")
            c.drawString(COL_ND['min_grade'], y, "MIN")
            c.drawString(COL_ND['qual'],      y, "STATUS")
            y -= 0.1*cm
            c.setStrokeColor(colors.HexColor("#cbd5e1"))
            c.line(1.5*cm, y, W - 1.5*cm, y)
            y -= 0.4*cm
            c.setFillColor(colors.black)

        draw_headers_nd()

        QUAL_COLORS = {
            'Strongly Qualifies':    colors.HexColor("#065f46"),
            'Comfortably Qualifies': colors.HexColor("#15803d"),
            'Meets Minimum':         colors.HexColor("#1d4ed8"),
        }

        for i, m in enumerate(matches):
            if y < 2.0*cm:
                y = new_page()
                draw_headers_nd()
            if i % 2 == 0:
                c.setFillColor(LIGHT)
                c.rect(1.5*cm, y - 0.22*cm, W - 3*cm, 0.36*cm, fill=1, stroke=0)
            c.setFont("Helvetica", 7.5)
            c.setFillColor(colors.black)
            course_name = m['course'].name
            if len(course_name) > 40:
                course_name = course_name[:38] + '…'
            c.drawString(COL_ND['course'], y, course_name)
            inst_name = m['institution'].name
            if len(inst_name) > 26:
                inst_name = inst_name[:24] + '…'
            c.drawString(COL_ND['inst'], y, inst_name)
            location = (getattr(m['institution'], 'location', '') or '—')[:14]
            c.drawString(COL_ND['location'], y, location)
            cat = m['course'].category.name[:14] if m['course'].category else '—'
            c.drawString(COL_ND['category'], y, cat)
            c.setFillColor(CHANCE_COLORS.get(m['chance'], colors.grey))
            c.setFont("Helvetica-Bold", 7.5)
            chance_abbr = {'High Likelihood': 'High Like.', 'Likely': 'Likely'}.get(m['chance'], m['chance'])
            c.drawString(COL_ND['chance'], y, chance_abbr)
            c.setFont("Helvetica", 7.5)
            c.setFillColor(colors.black)
            c.drawString(COL_ND['min_grade'], y, str(m['cutoff'])[:4])
            ql = m.get('qual_label', '—')
            c.setFillColor(QUAL_COLORS.get(ql, SLATE))
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(COL_ND['qual'], y, ql[:22])
            y -= 0.41*cm

    c.save()
    return response


def career_results_pdf_detailed(request):
    """Detailed placement report PDF — cover page + per-tier grouped results."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from django.http import HttpResponse
    from django.utils import timezone
    from collections import Counter

    matches, pathway, cluster_pts_single, mean_grade, _, cluster_score_table = _build_career_matches(request)
    if not matches:
        return HttpResponse(
            "No career matches found. Please run the career guidance tool first.",
            status=400,
        )

    numeric_pts = [m['student_points'] for m in matches if isinstance(m['student_points'], (int, float))]
    best_pts    = max(numeric_pts, default=cluster_pts_single) if pathway == 'Degree' else None

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="careernext_career_report.pdf"'

    c = canvas.Canvas(response, pagesize=landscape(A4))
    W, H = landscape(A4)   # ~29.7 × 21 cm

    NAVY  = colors.HexColor("#1e3a8a")
    GREEN = colors.HexColor("#16a34a")
    SLATE = colors.HexColor("#64748b")
    LIGHT = colors.HexColor("#f1f5f9")

    TIER_COLORS = {
        'Best Match':     colors.HexColor("#059669"),
        'Stretch':        colors.HexColor("#d97706"),
        'Safe Option':    colors.HexColor("#2563eb"),
        'Easy Admission': colors.HexColor("#64748b"),
        'Long Shot':      colors.HexColor("#dc2626"),
    }
    CHANCE_COLORS = {
        'High Likelihood': colors.HexColor("#16a34a"),
        'Likely':          colors.HexColor("#059669"),
        'Borderline':      colors.HexColor("#f97316"),
        'Unlikely':        colors.HexColor("#dc2626"),
    }
    TIER_DESC_SHORT = {
        'Best Match':     'Score right at or just above cutoff — ideal fit.',
        'Stretch':        'Slightly below cutoff — competitive, worth applying.',
        'Safe Option':    'Comfortably above cutoff — strong admission chance.',
        'Easy Admission': 'Well above cutoff — very high certainty.',
        'Long Shot':      'Significantly below cutoff — low probability.',
    }

    page_num = [0]

    def new_page(subtitle=""):
        page_num[0] += 1
        if page_num[0] > 1:
            c.showPage()
        c.setFillColor(NAVY)
        c.rect(0, H - 1.8*cm, W, 1.8*cm, fill=1, stroke=0)
        c.setFillColor(GREEN)
        c.rect(0, H - 1.85*cm, W, 0.07*cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(1.5*cm, H - 1.15*cm, "CareerNext — Career Placement Report 2026")
        if subtitle:
            c.setFont("Helvetica", 8)
            c.drawString(1.5*cm, H - 1.55*cm, subtitle)
        c.setFont("Helvetica", 9)
        c.drawRightString(W - 1.5*cm, H - 1.15*cm, f"Page {page_num[0]}")
        c.setFillColor(colors.HexColor("#0e7490"))
        c.rect(0, 1.35*cm, W, 0.08*cm, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.rect(0, 0, W, 1.35*cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(W / 2, 0.82*cm,
            "careernext.co.ke  —  Your Journey Begins Here")
        c.setFont("Helvetica", 6.5)
        c.setFillColor(colors.HexColor("#93c5fd"))
        c.drawCentredString(W / 2, 0.45*cm,
            "For planning purposes only. Verify all cutoffs on the official KUCCPS portal (kuccps.net) before submitting applications.")
        c.setFillColor(colors.black)
        return H - 2.4*cm

    # ── Page 1: Cover / Profile ───────────────────────────────────────────────
    y = new_page("Student Profile & Match Summary")

    user_label = "Student"
    if request.user.is_authenticated:
        user_label = getattr(request.user, 'full_name', None) or request.user.email

    c.setFillColor(LIGHT)
    c.roundRect(1.5*cm, y - 3.8*cm, W - 3*cm, 3.5*cm, 8, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2.2*cm, y - 1.1*cm, "CareerNext — KCSE Career Placement Report")
    c.setFont("Helvetica", 9)
    c.setFillColor(SLATE)
    c.drawString(2.2*cm, y - 1.7*cm,  f"Prepared for: {user_label}")
    c.drawString(2.2*cm, y - 2.15*cm, f"Generated:    {timezone.now().strftime('%d %B %Y, %H:%M')}")
    c.drawString(2.2*cm, y - 2.6*cm,  f"Pathway:      {pathway}")
    if pathway == 'Degree':
        score_line = f"Best Cluster Score: {best_pts:.1f} / 48 pts" if best_pts is not None else "—"
        c.drawString(2.2*cm, y - 3.05*cm, score_line)
        c.drawString(2.2*cm, y - 3.5*cm,
            "Prediction model: 70% Weighted Moving Average + 30% Naive blend")
    else:
        c.drawString(2.2*cm, y - 3.05*cm, f"Mean Grade Entered:  {mean_grade}")
        c.drawString(2.2*cm, y - 3.5*cm,
            "Eligibility: based on minimum mean grade and subject requirements per programme.")
    y -= 4.5*cm

    chance_counts = Counter(m['chance'] for m in matches)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(NAVY)
    c.drawString(1.5*cm, y, f"MATCH SUMMARY — {len(matches)} qualifying programmes found")
    y -= 0.55*cm

    if pathway == 'Degree':
        tier_counts = Counter(m['tier'] for m in matches)
        for tier in ['Best Match', 'Stretch', 'Safe Option', 'Easy Admission', 'Long Shot']:
            cnt = tier_counts.get(tier, 0)
            if cnt == 0:
                continue
            c.setFillColor(TIER_COLORS.get(tier, SLATE))
            c.rect(1.5*cm, y - 0.28*cm, 0.22*cm, 0.28*cm, fill=1, stroke=0)
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 9)
            c.drawString(2.0*cm, y, f"{tier}: {cnt} courses — {TIER_DESC_SHORT.get(tier, '')}")
            y -= 0.44*cm
    else:
        QUAL_COLORS_PDF = {
            'Strongly Qualifies':    colors.HexColor("#065f46"),
            'Comfortably Qualifies': colors.HexColor("#15803d"),
            'Meets Minimum':         colors.HexColor("#1d4ed8"),
        }
        qual_counts = Counter(m.get('qual_label', '') for m in matches)
        QUAL_DESC = {
            'Strongly Qualifies':    'Mean grade is well above the minimum — very strong candidate.',
            'Comfortably Qualifies': 'Mean grade exceeds the minimum by 1–2 grades — good candidate.',
            'Meets Minimum':         'Mean grade exactly meets the minimum — eligible to apply.',
        }
        for ql in ['Strongly Qualifies', 'Comfortably Qualifies', 'Meets Minimum']:
            cnt = qual_counts.get(ql, 0)
            if cnt == 0:
                continue
            c.setFillColor(QUAL_COLORS_PDF.get(ql, SLATE))
            c.rect(1.5*cm, y - 0.28*cm, 0.22*cm, 0.28*cm, fill=1, stroke=0)
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 9)
            c.drawString(2.0*cm, y, f"{ql}: {cnt} programmes — {QUAL_DESC.get(ql, '')}")
            y -= 0.44*cm

    y -= 0.4*cm
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(NAVY)
    c.drawString(1.5*cm, y, "ADMISSION LIKELIHOOD")
    y -= 0.44*cm
    for chance in ['High Likelihood', 'Likely']:
        cnt = chance_counts.get(chance, 0)
        if cnt == 0:
            continue
        c.setFillColor(CHANCE_COLORS.get(chance, SLATE))
        c.rect(1.5*cm, y - 0.28*cm, 0.22*cm, 0.28*cm, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 9)
        c.drawString(2.0*cm, y, f"{chance}: {cnt} {'courses' if pathway == 'Degree' else 'programmes'}")
        y -= 0.42*cm

    y -= 0.4*cm
    # Legend / how-to-read box
    c.setFillColor(LIGHT)
    c.rect(1.5*cm, y - 1.7*cm, W - 3*cm, 1.6*cm, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(2.0*cm, y - 0.38*cm, "HOW TO READ THIS REPORT")
    c.setFont("Helvetica", 8)
    c.setFillColor(SLATE)
    if pathway == 'Degree':
        c.drawString(2.0*cm, y - 0.75*cm, "CUTOFF = latest known cutoff (2024).   EST 2026 = model prediction.   DIFF = Your score minus the cutoff.")
        c.drawString(2.0*cm, y - 1.1*cm,  "Best Match: score 0–+3 pts above cutoff.  Stretch: within 3 pts below.  Safe/Easy: comfortably above.")
        c.drawString(2.0*cm, y - 1.45*cm, "Verify all cutoffs on the official KUCCPS portal (kuccps.net) before applying.")
    else:
        c.drawString(2.0*cm, y - 0.75*cm, "MIN = minimum mean grade required for the programme.  STATUS = how well your grade meets that requirement.")
        c.drawString(2.0*cm, y - 1.1*cm,  "All programmes listed are ones you qualify for.  Sorted strongest qualification first.")
        c.drawString(2.0*cm, y - 1.45*cm, "Verify requirements at the institution directly or via the KUCCPS portal before applying.")
    y -= 2.1*cm

    # ── Cluster scores — Degree only ─────────────────────────────────────────
    if pathway == 'Degree':
        if cluster_score_table:
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(NAVY)
            c.drawString(1.5*cm, y, "YOUR KUCCPS CLUSTER SCORES (Groups 1–20, out of 48 pts)")
            y -= 0.42*cm
            col_w = (W - 3*cm) / 4
            BAR_GREEN  = colors.HexColor("#16a34a")
            BAR_ORANGE = colors.HexColor("#f97316")
            for i, (knum, gname, score) in enumerate(cluster_score_table):
                col = i % 4
                if col == 0 and i > 0:
                    y -= 0.5*cm
                    if y < 2.0*cm:
                        y = new_page("Student Cluster Scores (continued)")
                x = 1.5*cm + col * col_w
                bar_max = col_w - 1.4*cm
                bar_w   = (score / 48.0) * bar_max if score else 0
                bar_col = BAR_GREEN if score >= 36 else (NAVY if score >= 24 else BAR_ORANGE)
                c.setFillColor(LIGHT)
                c.rect(x + 1.05*cm, y - 0.28*cm, bar_max, 0.16*cm, fill=1, stroke=0)
                c.setFillColor(bar_col)
                c.rect(x + 1.05*cm, y - 0.28*cm, bar_w, 0.16*cm, fill=1, stroke=0)
                c.setFont("Helvetica", 7.5)
                c.setFillColor(colors.black)
                c.drawString(x, y, f"C{knum}: {score:.1f}")
            y -= 0.65*cm
        elif best_pts:
            c.setFont("Helvetica", 8.5)
            c.setFillColor(SLATE)
            c.drawString(1.5*cm, y,
                f"Single cluster score applied: {best_pts:.1f} pts / 48  "
                f"(use per-cluster entry for detailed breakdown)")
            y -= 0.45*cm

    # ── Detail pages ──────────────────────────────────────────────────────────
    if pathway == 'Degree':
        COL = {
            'course': 1.7*cm, 'inst': 9.8*cm, 'cluster': 16.0*cm,
            'chance': 17.8*cm, 'cutoff': 21.4*cm, 'pred': 23.2*cm,
            'range': 25.0*cm, 'diff': 28.0*cm,
        }

        def draw_tier_headers(y_pos):
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(SLATE)
            c.drawString(COL['course'],  y_pos, "COURSE")
            c.drawString(COL['inst'],    y_pos, "INSTITUTION")
            c.drawString(COL['cluster'], y_pos, "CLUST")
            c.drawString(COL['chance'],  y_pos, "LIKELIHOOD")
            c.drawString(COL['cutoff'],  y_pos, "CUTOFF")
            c.drawString(COL['pred'],    y_pos, "EST 2026")
            c.drawString(COL['range'],   y_pos, "PRED RANGE")
            c.drawString(COL['diff'],    y_pos, "DIFF")
            y_pos -= 0.1*cm
            c.setStrokeColor(colors.HexColor("#cbd5e1"))
            c.line(1.5*cm, y_pos, W - 1.5*cm, y_pos)
            return y_pos - 0.38*cm

        for tier_label in ['Best Match', 'Stretch', 'Safe Option', 'Easy Admission', 'Long Shot']:
            tier_matches = [m for m in matches if m['tier'] == tier_label]
            if not tier_matches:
                continue
            y = new_page(f"Tier: {tier_label} — {TIER_DESC_SHORT.get(tier_label, '')}")
            tier_col = TIER_COLORS.get(tier_label, SLATE)
            c.setFillColor(tier_col)
            c.rect(1.5*cm, y - 0.55*cm, W - 3*cm, 0.5*cm, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 9.5)
            c.drawString(2.0*cm, y - 0.36*cm, f"{tier_label.upper()}  ({len(tier_matches)} courses)")
            y -= 0.95*cm
            y = draw_tier_headers(y)
            for i, m in enumerate(tier_matches):
                if y < 2.0*cm:
                    y = new_page(f"Tier: {tier_label} (continued)")
                    y = draw_tier_headers(y)
                if i % 2 == 0:
                    c.setFillColor(LIGHT)
                    c.rect(1.5*cm, y - 0.22*cm, W - 3*cm, 0.36*cm, fill=1, stroke=0)
                c.setFont("Helvetica", 7.5)
                c.setFillColor(colors.black)
                cn = m['course'].name
                c.drawString(COL['course'], y, (cn[:44] + '…') if len(cn) > 46 else cn)
                iname = m['institution'].name
                c.drawString(COL['inst'], y, (iname[:32] + '…') if len(iname) > 34 else iname)
                knum = m['cluster'].kuccps_number if m['cluster'] else None
                c.drawString(COL['cluster'], y, f"C{knum}" if knum else '—')
                chance_abbr = {'High Likelihood': 'High Like.', 'Likely': 'Likely',
                               'Borderline': 'Borderline', 'Unlikely': 'Unlikely'}.get(m['chance'], m['chance'])
                c.setFillColor(CHANCE_COLORS.get(m['chance'], colors.grey))
                c.setFont("Helvetica-Bold", 7.5)
                c.drawString(COL['chance'], y, chance_abbr)
                c.setFont("Helvetica", 7.5)
                c.setFillColor(colors.black)
                c.drawString(COL['cutoff'], y, str(m['cutoff'])[:5])
                pred = m.get('pred')
                if pred:
                    c.drawString(COL['pred'],  y, f"{pred['predicted']:.1f}")
                    c.drawString(COL['range'], y, f"{pred['low']:.1f}–{pred['high']:.1f}")
                else:
                    c.drawString(COL['pred'], y, '—')
                    c.drawString(COL['range'], y, '—')
                diff_val = m['diff']
                diff_str = f"+{diff_val:.1f}" if diff_val >= 0 else f"{diff_val:.1f}"
                c.setFillColor(colors.HexColor("#15803d") if diff_val >= 0 else colors.HexColor("#dc2626"))
                c.setFont("Helvetica-Bold", 7.5)
                c.drawString(COL['diff'], y, diff_str)
                y -= 0.41*cm

    else:
        # ── Non-degree detail pages — grouped by qualification status ──────────
        COL_ND = {
            'course':   1.7*cm,
            'inst':     9.0*cm,
            'location': 17.0*cm,
            'category': 20.5*cm,
            'chance':   24.0*cm,
            'min':      26.5*cm,
            'subj':     27.6*cm,
        }
        QUAL_COLORS_ND = {
            'Strongly Qualifies':    colors.HexColor("#065f46"),
            'Comfortably Qualifies': colors.HexColor("#15803d"),
            'Meets Minimum':         colors.HexColor("#1d4ed8"),
        }

        def draw_nd_headers(y_pos):
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(SLATE)
            c.drawString(COL_ND['course'],   y_pos, "PROGRAMME")
            c.drawString(COL_ND['inst'],     y_pos, "INSTITUTION")
            c.drawString(COL_ND['location'], y_pos, "LOCATION")
            c.drawString(COL_ND['category'], y_pos, "CATEGORY")
            c.drawString(COL_ND['chance'],   y_pos, "LIKELIHOOD")
            c.drawString(COL_ND['min'],      y_pos, "MIN")
            c.drawString(COL_ND['subj'],     y_pos, "SUBJECT REQS")
            y_pos -= 0.1*cm
            c.setStrokeColor(colors.HexColor("#cbd5e1"))
            c.line(1.5*cm, y_pos, W - 1.5*cm, y_pos)
            return y_pos - 0.38*cm

        for ql_label in ['Strongly Qualifies', 'Comfortably Qualifies', 'Meets Minimum']:
            ql_matches = [m for m in matches if m.get('qual_label') == ql_label]
            if not ql_matches:
                continue
            y = new_page(f"{ql_label} — {len(ql_matches)} programmes")
            ql_col = QUAL_COLORS_ND.get(ql_label, SLATE)
            c.setFillColor(ql_col)
            c.rect(1.5*cm, y - 0.55*cm, W - 3*cm, 0.5*cm, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 9.5)
            c.drawString(2.0*cm, y - 0.36*cm, f"{ql_label.upper()}  ({len(ql_matches)} programmes)")
            y -= 0.95*cm
            y = draw_nd_headers(y)
            for i, m in enumerate(ql_matches):
                if y < 2.0*cm:
                    y = new_page(f"{ql_label} (continued)")
                    y = draw_nd_headers(y)
                if i % 2 == 0:
                    c.setFillColor(LIGHT)
                    c.rect(1.5*cm, y - 0.22*cm, W - 3*cm, 0.36*cm, fill=1, stroke=0)
                c.setFont("Helvetica", 7.5)
                c.setFillColor(colors.black)
                cn = m['course'].name
                c.drawString(COL_ND['course'], y, (cn[:38] + '…') if len(cn) > 40 else cn)
                iname = m['institution'].name
                c.drawString(COL_ND['inst'], y, (iname[:24] + '…') if len(iname) > 26 else iname)
                location = (getattr(m['institution'], 'location', '') or '—')[:14]
                c.drawString(COL_ND['location'], y, location)
                cat = m['course'].category.name[:14] if m['course'].category else '—'
                c.drawString(COL_ND['category'], y, cat)
                chance_abbr = {'High Likelihood': 'High Like.', 'Likely': 'Likely'}.get(m['chance'], m['chance'])
                c.setFillColor(CHANCE_COLORS.get(m['chance'], colors.grey))
                c.setFont("Helvetica-Bold", 7.5)
                c.drawString(COL_ND['chance'], y, chance_abbr)
                c.setFont("Helvetica", 7.5)
                c.setFillColor(colors.black)
                c.drawString(COL_ND['min'], y, str(m['cutoff'])[:4])
                reqs = m['course'].subject_requirements or []
                req_str = '  |  '.join(
                    f"{r.get('subjects_str','')}: {r.get('min_grade','')}" for r in reqs
                ) if reqs else '—'
                if len(req_str) > 28:
                    req_str = req_str[:26] + '…'
                c.drawString(COL_ND['subj'], y, req_str)
                y -= 0.41*cm

    c.save()
    return response


# ── Share Result ────────────────────────────────────────────────────────────

@login_required
def share_result_create(request):
    """AJAX POST — snapshot current session into a SharedResult; return share URL."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    pathway = request.session.get('career_pathway', '')
    if not pathway:
        return JsonResponse({'ok': False, 'error': 'No results in session.'}, status=400)

    cluster_pts_single  = float(request.session.get('career_cluster_pts_single', 0) or 0)
    cluster_points_json = request.session.get('career_cluster_points', {})

    matches, _, _, _, _, _ = _build_career_matches(request)
    top_courses = [
        {
            'course':       m['course'].name,
            'institution':  m['institution'].name,
            'tier':         m.get('tier', ''),
            'chance':       m.get('chance', ''),
            'cutoff':       str(m.get('cutoff', '')),
        }
        for m in matches[:5]
    ]

    sr = SharedResult.objects.create(
        user=request.user,
        pathway=pathway,
        cluster_points_json=cluster_points_json or {},
        cluster_pts_single=cluster_pts_single,
        total_matches=len(matches),
        top_courses_json=top_courses,
    )
    share_url = request.build_absolute_uri(sr.get_absolute_url())
    return JsonResponse({'ok': True, 'url': share_url, 'token': str(sr.token)})


def shared_result_view(request, token):
    """Public page — no login required. Displays a shared career result snapshot."""
    from django.shortcuts import get_object_or_404

    sr = get_object_or_404(SharedResult, token=token)
    if sr.is_expired:
        return render(request, 'career/shared_result_expired.html', {'sr': sr})

    SharedResult.objects.filter(pk=sr.pk).update(view_count=models.F('view_count') + 1)
    sr.refresh_from_db(fields=['view_count'])

    return render(request, 'career/shared_result.html', {
        'sr': sr,
        'share_url': request.build_absolute_uri(request.path),
    })