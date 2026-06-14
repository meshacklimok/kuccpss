from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.urls import reverse
from math import sqrt as _sqrt
import re as _re
from .models import (
    TVETCourse, StudentCourseMatch, AIRecommendation, CareerInsight, TVETCategory,
    CareerProfile, QuizQuestion, QuizSubmission, QuizAnswer,
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
    """
    Home page: select pathway (Degree, Diploma, TVET, KMTC, TTC)
    """
    categories = ["Degree", "Diploma", "TVET", "KMTC", "TTC"]
    tvet_categories = TVETCategory.objects.all()
    context = {
        "categories": categories,
        "tvet_categories": tvet_categories
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
def career_profiles_list(request):
    profiles = CareerProfile.objects.all()
    query = request.GET.get("q", "")
    if query:
        profiles = profiles.filter(title__icontains=query)

    demand = request.GET.get("demand", "")
    if demand:
        profiles = profiles.filter(demand_level=demand)

    paginator = Paginator(profiles, 12)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    return render(request, "career/career_profiles.html", {
        "page_obj": page_obj,
        "query": query,
        "active_demand": demand,
        "demand_choices": CareerProfile.DEMAND_CHOICES,
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

    related = CareerProfile.objects.exclude(pk=profile.pk)[:4]
    return render(request, "career/career_profile_detail.html", {
        "profile": profile,
        "is_saved": is_saved,
        "related": related,
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

    return render(request, "career/quiz_results.html", {
        "top_matches": top_matches,
        "tag_scores": tag_scores,
    })


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
        return 'VERY HIGH', 'success'
    if diff >= 0:
        return 'HIGH', 'primary'
    if diff >= -3:
        return 'MEDIUM', 'warning'
    return 'LOW', 'danger'


def _chance_from_grade_diff(diff):
    """Admission chance for mean grade comparison (non-degree)."""
    if diff >= 3:
        return 'VERY HIGH', 'success'
    if diff >= 0:
        return 'HIGH', 'primary'
    if diff >= -2:
        return 'MEDIUM', 'warning'
    return 'LOW', 'danger'


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

        # Build name → points dict
        subjects = Subject.objects.filter(id__in=points_by_id.keys())
        pts_by_name = {s.name: points_by_id[s.id] for s in subjects}

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

        # Cluster points — top-4 fallback (SubjectGroups not yet seeded)
        all_pts = sorted(pts_by_name.values(), reverse=True)
        core_total = min(sum(all_pts[:4]), 48)
        if aggregate_total > 0 and core_total > 0:
            cluster_pts_single = round(48 * _sqrt((core_total / 48) * (aggregate_total / 84)), 2)
        else:
            cluster_pts_single = 0.0

        # Pre-fill every DB cluster with this value
        cluster_ids = list(Cluster.objects.values_list('id', flat=True))
        precomputed = {str(cid): cluster_pts_single for cid in cluster_ids}

        request.session['career_pathway'] = 'Degree'
        request.session['career_degree_method'] = 'calculate'
        request.session['career_precomputed'] = precomputed
        request.session['career_aggregate_total'] = aggregate_total
        request.session['career_cluster_pts_single'] = cluster_pts_single

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
# C. DEGREE: Upload KCSE slip image → OCR via OpenAI Vision
# ─────────────────────────────────────────────
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
                'Enter your grades manually below.'
            )
            return redirect('career:degree_calculate')

        try:
            import base64
            from openai import OpenAI

            # Encode image to base64
            img_bytes = img.read()
            b64 = base64.b64encode(img_bytes).decode('utf-8')
            mime = img.content_type or 'image/jpeg'

            client = OpenAI(api_key=api_key)

            prompt = """You are reading a Kenyan KCSE (secondary school) results slip.
Extract all subject grades visible on the slip.
Return ONLY a JSON object where:
- keys are subject names exactly as they appear on KCSE slips (e.g. "Mathematics", "English", "Kiswahili", "Biology", "Physics", "Chemistry", "History", "Geography", "CRE", "IRE", "Home Science", "Agriculture", "Business Studies", "Computer Studies", "French", "German", "Music", "Art and Design", "Aviation Technology", "Drawing and Design", "Building Construction", "Power Mechanics", "Electricity", "Woodwork", "Metalwork")
- values are the grade string (one of: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E)

Example output:
{"Mathematics": "B+", "English": "A-", "Kiswahili": "B", "Biology": "C+", "Chemistry": "B-"}

If you cannot read a grade clearly, omit that subject.
Return ONLY the JSON object, nothing else."""

            response = client.chat.completions.create(
                model='gpt-4o-mini',
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
                max_tokens=400,
            )

            raw_json = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw_json.startswith('```'):
                raw_json = raw_json.split('```')[1]
                if raw_json.startswith('json'):
                    raw_json = raw_json[4:]
                raw_json = raw_json.strip()

            import json
            extracted = json.loads(raw_json)

            if not extracted:
                raise ValueError('No grades found in image')

            # Map extracted {name: grade_str} to {subject_id: points_int}
            from clusters.models import Subject

            GRADE_STR_TO_PTS = {
                'A': 12, 'A-': 11, 'B+': 10, 'B': 9, 'B-': 8,
                'C+': 7, 'C': 6, 'C-': 5, 'D+': 4, 'D': 3, 'D-': 2, 'E': 1,
            }

            all_subjects = {s.name.lower(): s for s in Subject.objects.all()}
            prefill = {}
            subject_grades_ocr = {}
            matched_names = []
            for subj_name, grade_str in extracted.items():
                grade_str = grade_str.strip().upper()
                pts = GRADE_STR_TO_PTS.get(grade_str)
                if pts is None:
                    continue
                subj_obj = all_subjects.get(subj_name.lower())
                if subj_obj:
                    prefill[str(subj_obj.id)] = pts
                    subject_grades_ocr[subj_obj.name.lower()] = pts
                    matched_names.append(f"{subj_name}: {grade_str}")

            if not prefill:
                raise ValueError('Could not match any extracted subjects to the database')

            request.session['ocr_prefill'] = prefill
            request.session['career_subject_grades'] = subject_grades_ocr
            count = len(prefill)
            messages.success(
                request,
                f'OCR extracted {count} subject grade{"s" if count != 1 else ""}: '
                f'{", ".join(matched_names[:5])}{"..." if count > 5 else ""}. '
                'Review and complete any missing grades below.'
            )
            return redirect('career:degree_calculate')

        except Exception as e:
            messages.warning(
                request,
                f'Could not read grades from image ({e}). Please enter your grades manually.'
            )
            return redirect('career:degree_calculate')

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
        values = [v.strip() for v in re.split(r'[\s,;]+', raw) if v.strip()]

        try:
            degree_type = CourseType.objects.filter(name__icontains='Degree').first()
            if degree_type:
                relevant_ids = list(
                    CourseOffering.objects
                    .filter(course__course_type=degree_type, course__cluster__isnull=False)
                    .values_list('course__cluster_id', flat=True)
                    .distinct()
                )
                clusters = list(Cluster.objects.filter(id__in=relevant_ids).order_by('number'))
            else:
                clusters = list(Cluster.objects.all().order_by('number'))
        except Exception:
            clusters = list(Cluster.objects.all().order_by('number'))

        cluster_points = {}
        for i, cluster in enumerate(clusters):
            try:
                val = max(0.0, min(48.0, float(values[i]))) if i < len(values) else 0.0
            except (ValueError, TypeError):
                val = 0.0
            cluster_points[str(cluster.id)] = val

        valid_vals = [v for v in cluster_points.values() if v > 0]
        if valid_vals:
            single = round(sum(valid_vals) / len(valid_vals), 2)
            request.session['career_pathway'] = 'Degree'
            request.session['career_degree_method'] = 'paste'
            request.session['career_cluster_points'] = cluster_points
            request.session['career_cluster_pts_single'] = single
            return redirect('career:loading_page', pathway='degree')

        messages.error(request, 'No valid cluster points found. Please enter numeric values (e.g. 32.5 28.0 ...).')

    return render(request, 'career/degree_paste.html')


# ─────────────────────────────────────────────
# D. DEGREE: Manual cluster points entry
#    Also serves as the confirm/edit step after Calculate or Upload
# ─────────────────────────────────────────────
def degree_manual(request):
    import re as _re
    from clusters.models import Cluster
    from courses.models import CourseOffering, CourseType

    try:
        degree_type = CourseType.objects.filter(name__icontains='Degree').first()
        if degree_type:
            relevant_ids = list(
                CourseOffering.objects
                .filter(course__course_type=degree_type, course__cluster__isnull=False)
                .values_list('course__cluster_id', flat=True)
                .distinct()
            )
            all_clusters = list(Cluster.objects.filter(id__in=relevant_ids).order_by('number'))
        else:
            all_clusters = list(Cluster.objects.all().order_by('number'))
    except Exception:
        all_clusters = list(Cluster.objects.all().order_by('number'))

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
                first_id = str(grp['subs'][0].id) if grp['subs'] else None
                val = float(precomputed.get(first_id, 0)) if first_id else 0.0
            for c in grp['subs']:
                cluster_points[str(c.id)] = val

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

    use_kcse_form = pathway.lower() in ('diploma', 'certificate')

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
        form = KCSEForm() if use_kcse_form else None

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
        'counties': KENYAN_COUNTIES,
        'tvet_categories': TVET_CATEGORIES,
        'use_kcse_form': use_kcse_form,
        'form': form,
        'compulsory_fields': compulsory_fields,
        'optional_groups': optional_groups,
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

    pathway = request.session.get('career_pathway', '')
    filter_chance = request.GET.get('chance', '')
    search_q = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', 'chance')

    matches = []
    cluster_pts_single = float(request.session.get('career_cluster_pts_single', 0) or 0)
    mean_grade = request.session.get('career_mean_grade', '')
    subject_grades = request.session.get('career_subject_grades', {})  # {lower_name: points_int}

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

                # Skip courses whose subject requirements the student doesn't meet
                if subject_grades and offering.course.subject_requirements:
                    if not _meets_subject_requirements(offering.course.subject_requirements, subject_grades):
                        continue

                cluster = offering.course.cluster
                if cluster and cluster_points_dict:
                    student_pts = float(cluster_points_dict.get(str(cluster.id), cluster_pts_single))
                else:
                    student_pts = cluster_pts_single

                diff = round(student_pts - float(cutoff), 2)
                chance, badge = _chance_from_diff(diff)

                if filter_chance and chance != filter_chance:
                    continue

                matches.append({
                    'offering': offering,
                    'course': offering.course,
                    'institution': offering.institution,
                    'cluster': cluster,
                    'cutoff': cutoff,
                    'student_points': round(student_pts, 1),
                    'diff': diff,
                    'chance': chance,
                    'badge': badge,
                })

    else:
        student_pts = GRADE_POINTS.get(mean_grade, 0)
        type_names = COURSE_TYPE_MAP.get(pathway, [])

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

            default_min = PATHWAY_DEFAULT_MIN_GRADE.get(pathway, 'E')
            for offering in qs:
                course = offering.course

                # Skip courses whose subject requirements the student doesn't meet
                if subject_grades and course.subject_requirements:
                    if not _meets_subject_requirements(course.subject_requirements, subject_grades):
                        continue

                min_grade = (course.minimum_mean_grade or '').strip() or default_min
                min_pts = GRADE_POINTS.get(min_grade, 0)
                diff = student_pts - min_pts
                chance, badge = _chance_from_grade_diff(diff)

                if filter_chance and chance != filter_chance:
                    continue

                matches.append({
                    'offering': offering,
                    'course': course,
                    'institution': offering.institution,
                    'cluster': None,
                    'cutoff': min_grade or '—',
                    'student_points': mean_grade,
                    'diff': diff,
                    'chance': chance,
                    'badge': badge,
                })

    _CHANCE_ORDER = {'VERY HIGH': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    if sort_by == 'chance':
        matches.sort(key=lambda m: (_CHANCE_ORDER.get(m['chance'], 4), -m.get('diff', 0)))
    elif sort_by == 'institution':
        matches.sort(key=lambda m: m['institution'].name)
    elif sort_by == 'course':
        matches.sort(key=lambda m: m['course'].name)

    paginator = Paginator(matches, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'career/career_results_v2.html', {
        'page_obj': page_obj,
        'pathway': pathway,
        'total_count': len(matches),
        'filter_chance': filter_chance,
        'search_q': search_q,
        'sort_by': sort_by,
        'mean_grade': mean_grade,
        'cluster_pts_single': cluster_pts_single,
    })