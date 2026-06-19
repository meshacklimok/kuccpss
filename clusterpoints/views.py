# clusterpoints/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

from .forms import KCSEForm
from clusters.models import Subject
from .models import UserKCSEResult, SubjectResult, ClusterCalculationResult
from .services import calculate_all_clusters, calculate_clusters_anonymous

# KCSE mean grade bands (based on 7-subject aggregate max 84)
_GRADE_BANDS = [
    (81, 84, 'A'),
    (74, 80, 'A-'),
    (67, 73, 'B+'),
    (60, 66, 'B'),
    (53, 59, 'B-'),
    (46, 52, 'C+'),
    (39, 45, 'C'),
    (32, 38, 'C-'),
    (25, 31, 'D+'),
    (18, 24, 'D'),
    (11, 17, 'D-'),
    (7,  10, 'E'),
]

def _mean_grade(total):
    if total is None:
        return None
    for lo, hi, grade in _GRADE_BANDS:
        if lo <= total <= hi:
            return grade
    return 'E'


def _pathway_recommendation(total):
    """Return pathway label, description and styling for a given aggregate total."""
    if not total:
        return None
    if total >= 60:
        return {'label': 'Degree Programmes', 'badge': 'B+ and above',
                'desc': 'Your aggregate qualifies you for competitive university degree programmes.',
                'color_class': 'card-accent-blue', 'text_color': 'var(--primary-light)',
                'icon': 'fa-graduation-cap', 'btn': 'Explore Degree Courses', 'pathway': 'degree'}
    elif total >= 46:
        return {'label': 'Degree or Diploma', 'badge': 'C+ to B',
                'desc': 'You qualify for diploma programmes and may be competitive for select degree courses.',
                'color_class': 'card-accent-purple', 'text_color': 'var(--purple)',
                'icon': 'fa-route', 'btn': 'Find Your Path', 'pathway': 'degree'}
    elif total >= 32:
        return {'label': 'KMTC / TVET Diploma', 'badge': 'C to C-',
                'desc': 'Medical, technical, and vocational diploma programmes are well within your reach.',
                'color_class': 'card-accent-green', 'text_color': 'var(--accent)',
                'icon': 'fa-stethoscope', 'btn': 'Explore KMTC & TVET', 'pathway': 'kmtc'}
    else:
        return {'label': 'TVET Certificate & Artisan', 'badge': 'D+ and below',
                'desc': 'Certificate, Craft, and Artisan programmes open strong skill-based career paths.',
                'color_class': 'card-accent-orange', 'text_color': '#f97316',
                'icon': 'fa-tools', 'btn': 'Browse Certificate Courses', 'pathway': 'tvet'}


def _compute_aggregate(named: dict) -> int:
    """Compute the 7-subject aggregate (max 84) from {subject_name: points}."""
    working = named.copy()
    agg = []
    if 'Mathematics' in working:
        agg.append(working.pop('Mathematics'))
    langs = {l: working.pop(l) for l in ['English', 'Kiswahili'] if l in working}
    if langs:
        best = max(langs, key=langs.get)
        agg.append(langs[best])
        for l, p in langs.items():
            if l != best:
                working[l] = p
    agg += sorted(working.values(), reverse=True)[:5]
    return sum(agg)


# =====================================================
# DASHBOARD VIEW
# =====================================================
@login_required
def dashboard(request):
    """
    Display the latest KCSE result and cluster points for the logged-in user.
    """
    kcse_result = UserKCSEResult.objects.filter(user=request.user).order_by("-created_at").first()
    cluster_results = []

    if kcse_result:
        cluster_results = kcse_result.cluster_results.select_related("cluster").order_by("-cluster_points")

    return render(request, "clusterpoints/dashboard.html", {
        "kcse_result": kcse_result,
        "cluster_results": cluster_results,
    })


# =====================================================
# KCSE CALCULATOR VIEW
# =====================================================
def kcse_calculator_view(request):
    from predictor.services import predict_all_for_student
    form = KCSEForm(request.POST or None)
    results = []
    total_points = None
    kcse_result = None
    predicted_groups = []

    if request.method == "POST":
        if form.is_valid():
            points_dict = form.get_points_dict()  # {subject_id: points}
            subject_ids = [int(s) for s in points_dict.keys()]
            subjects_map = {s.id: s for s in Subject.objects.filter(id__in=subject_ids)}

            # Build {name: points} — needed by both paths
            named_points = {
                subjects_map[int(s)].name: pts
                for s, pts in points_dict.items()
                if int(s) in subjects_map
            }

            if request.user.is_authenticated:
                # ── Authenticated: persist to DB ──────────────────────────
                with transaction.atomic():
                    UserKCSEResult.objects.filter(user=request.user).delete()
                    kcse_result = UserKCSEResult.objects.create(
                        user=request.user,
                        created_at=timezone.now(),
                    )
                    SubjectResult.objects.bulk_create([
                        SubjectResult(
                            kcse_result=kcse_result,
                            subject=subjects_map[int(s)],
                            points=pts,
                        )
                        for s, pts in points_dict.items()
                        if int(s) in subjects_map
                    ])
                    kcse_result.recalc_total_points()
                    total_points = kcse_result.total_points
                    results = calculate_all_clusters(kcse_result)
                messages.success(request, "KCSE results saved and cluster points calculated!")

            else:
                # ── Guest: compute in memory, stash in session ─────────────
                results = calculate_clusters_anonymous(named_points)
                total_points = _compute_aggregate(named_points)
                request.session['guest_calc'] = {
                    'named_points': named_points,
                    'total_points': total_points,
                }
                request.session['guest_cluster_map'] = {
                    r.cluster.kuccps_number: float(r.cluster_points)
                    for r in results
                    if r.cluster and r.cluster.kuccps_number is not None
                }

            # ── Build cluster scores dict and run predictor ────────────────
            cluster_scores = {
                r.cluster.number: float(r.cluster_points)
                for r in results
                if r.cluster and r.cluster.number
            }
            if cluster_scores:
                predicted_groups = predict_all_for_student(cluster_scores, top_per_cluster=9999)

        else:
            messages.error(request, "Please correct the errors below.")

    # ── Build accordion context (same pattern as degree_calculate) ────────────
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
    _GM = {
        'II':  {'label': 'Sciences',                    'color': '#059669', 'icon': 'bi-beaker'},
        'III': {'label': 'Humanities',                  'color': '#0891b2', 'icon': 'bi-book-fill'},
        'IV':  {'label': 'Technical & Applied',         'color': '#d97706', 'icon': 'bi-tools'},
        'V':   {'label': 'Languages, Business & Music', 'color': '#db2777', 'icon': 'bi-music-note'},
    }
    compulsory_fields = []
    _gmap = {g: [] for g, _ in _GC if g != 'I'}
    for _s in Subject.objects.all().order_by('group', 'name'):
        _e = (_s, form[f'subject_{_s.id}'], _ICONS.get(_s.name, 'bi-journal'))
        if _s.name in _COMP:
            compulsory_fields.append(_e)
        elif _s.group in _gmap:
            _gmap[_s.group].append(_e)
    optional_groups = [(_GM[g], _gmap[g]) for g, _ in _GC if g != 'I' and _gmap.get(g)]

    return render(request, "clusterpoints/calculator.html", {
        "form": form,
        "results": results,
        "total_points": total_points,
        "mean_grade": _mean_grade(total_points),
        "grade_bands": _GRADE_BANDS,
        "kcse_result": kcse_result,
        "is_guest": not request.user.is_authenticated,
        "pathway_rec": _pathway_recommendation(total_points),
        "predicted_groups": predicted_groups,
        "compulsory_fields": compulsory_fields,
        "optional_groups": optional_groups,
    })


# =====================================================
# EXPORT CLUSTER RESULT AS PDF
# =====================================================
@login_required
def export_cluster_pdf(request, result_id):
    """
    Export a specific cluster calculation result to PDF.
    """
    try:
        result = ClusterCalculationResult.objects.get(id=result_id, user=request.user)
    except ClusterCalculationResult.DoesNotExist:
        messages.error(request, "Cluster result not found.")
        return redirect("clusterpoints:calculator")

    # PDF response
    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="cluster_result_{result_id}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Title
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, height - 2*cm, "KCSE Cluster Points Result")

    # User info
    p.setFont("Helvetica", 12)
    user_email = result.user.email if result.user else "Guest"
    p.drawString(2*cm, height - 3*cm, f"User: {user_email}")
    p.drawString(2*cm, height - 4*cm, f"Cluster: {result.cluster.name}")
    p.drawString(2*cm, height - 5*cm, f"Cluster Points: {result.cluster_points}")
    p.drawString(2*cm, height - 6*cm, f"Core Subject Total: {result.core_subject_total}")
    p.drawString(2*cm, height - 7*cm, f"Aggregate Total: {result.aggregate_total}")
    p.drawString(2*cm, height - 8*cm, f"Weighted Calculation: {result.weighted_calculation}")

    # Subjects used
    p.drawString(2*cm, height - 9*cm, "Subjects Used:")
    y_pos = height - 10*cm
    for subj in result.subjects_used.all():
        p.drawString(3*cm, y_pos, f"- {subj.name}")
        y_pos -= 0.5*cm
        if y_pos < 2*cm:
            p.showPage()
            y_pos = height - 2*cm

    # Footer on last page
    p.setFont("Helvetica", 7)
    p.setFillColorRGB(0.58, 0.63, 0.69)
    p.drawCentredString(width/2, 1.5*cm, "careernext.co.ke  |  CareerNext — Empowering Kenyan Students")
    p.drawCentredString(width/2, 1*cm, "Apply officially at kuccps.ac.ke")
    p.showPage()
    p.save()
    return response


# =====================================================
# ELIGIBLE COURSES VIEW
# =====================================================
def eligible_courses_view(request):
    from .eligibility import get_eligible_courses, get_eligible_courses_from_map
    from courses.models import CourseType

    is_guest = not request.user.is_authenticated

    if is_guest:
        cluster_map = request.session.get('guest_cluster_map')
        total_points = request.session.get('guest_calc', {}).get('total_points')
        if not cluster_map:
            messages.info(request, "Enter your KCSE results first to see your eligible courses.")
            return redirect("clusterpoints:calculator")
        all_results = get_eligible_courses_from_map(cluster_map)
        kcse_result = None
        saved_ids = []
    else:
        kcse_result = UserKCSEResult.objects.filter(
            user=request.user
        ).order_by("-created_at").first()
        total_points = kcse_result.total_points if kcse_result else None

        if not kcse_result:
            messages.info(request, "Enter your KCSE results first to see your eligible courses.")
            return redirect("clusterpoints:calculator")

        all_results = get_eligible_courses(request.user, kcse_result)
        from accounts.models import SavedCourse
        saved_ids = list(
            SavedCourse.objects.filter(user=request.user).values_list('course_id', flat=True)
        )

    # Filtering
    status_filter = request.GET.get("status", "")
    type_filter = request.GET.get("type", "")
    query = request.GET.get("q", "")

    filtered = all_results
    if status_filter:
        filtered = [r for r in filtered if r["status"] == status_filter]
    if type_filter:
        filtered = [r for r in filtered if r["course"].course_type.slug == type_filter]
    if query:
        filtered = [r for r in filtered if query.lower() in r["course"].name.lower()]

    eligible_count = sum(1 for r in all_results if r["status"] == "eligible")
    nearly_count   = sum(1 for r in all_results if r["status"] == "nearly")
    not_elig_count = sum(1 for r in all_results if r["status"] == "not_eligible")

    course_types = CourseType.objects.all()

    return render(request, "clusterpoints/eligible_courses.html", {
        "results": filtered,
        "kcse_result": kcse_result,
        "total_points": total_points,
        "mean_grade": _mean_grade(total_points),
        "eligible_count": eligible_count,
        "nearly_count": nearly_count,
        "not_eligible_count": not_elig_count,
        "status_filter": status_filter,
        "type_filter": type_filter,
        "query": query,
        "course_types": course_types,
        "saved_ids": saved_ids,
        "is_guest": is_guest,
    })


# =====================================================
# ADMIN ANALYTICS VIEW
# =====================================================
@login_required
def admin_analytics(request):
    """
    Show admin dashboard for clusterpoints analytics.
    """
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("clusterpoints:calculator")

    total_users = UserKCSEResult.objects.values("user").distinct().count()
    total_results = UserKCSEResult.objects.count()
    total_clusters_calculated = ClusterCalculationResult.objects.count()

    return render(request, "clusterpoints/admin_analytics.html", {
        "total_users": total_users,
        "total_results": total_results,
        "total_clusters_calculated": total_clusters_calculated
    })