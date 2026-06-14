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
from .services import calculate_all_clusters

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
@login_required
@transaction.atomic
def kcse_calculator_view(request):
    """
    KCSE calculator:
    - Save subject results
    - Calculate total points: 1 Math + 1 best language + 5 best other subjects
    - Calculate weighted cluster points
    """
    form = KCSEForm(request.POST or None)
    results = []
    total_points = None
    kcse_result = None

    if request.method == "POST":
        if form.is_valid():
            # Delete previous results for this user
            UserKCSEResult.objects.filter(user=request.user).delete()

            # Create new KCSE result
            kcse_result = UserKCSEResult.objects.create(
                user=request.user,
                created_at=timezone.now()
            )

            # -------------------------------
            # Save SubjectResults
            # -------------------------------
            points_dict = form.get_points_dict()  # {subject_id: points}
            subject_ids = [int(s) for s in points_dict.keys()]
            subjects_qs = Subject.objects.filter(id__in=subject_ids)
            subjects_map = {s.id: s for s in subjects_qs}

            bulk_results = [
                SubjectResult(
                    kcse_result=kcse_result,
                    subject=subjects_map[int(s)],
                    points=points
                )
                for s, points in points_dict.items()
                if int(s) in subjects_map
            ]
            SubjectResult.objects.bulk_create(bulk_results)

            # -------------------------------
            # Recalculate total points (max 84)
            # -------------------------------
            kcse_result.recalc_total_points()
            total_points = kcse_result.total_points

            # -------------------------------
            # Calculate cluster points (20 master clusters, sorted desc)
            # -------------------------------
            results = calculate_all_clusters(kcse_result)

            messages.success(request, "KCSE results saved and cluster points calculated successfully!")


        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, "clusterpoints/calculator.html", {
        "form": form,
        "results": results,
        "total_points": total_points,
        "mean_grade": _mean_grade(total_points),
        "grade_bands": _GRADE_BANDS,
        "kcse_result": kcse_result,
        "form_data": request.POST.dict() if request.method == "POST" else {},
        "grade_choices": form.fields[list(form.fields.keys())[0]].choices if form.fields else [],
        "compulsory_subjects": getattr(form, "compulsory_subjects", []),
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

    p.showPage()
    p.save()
    return response


# =====================================================
# ELIGIBLE COURSES VIEW
# =====================================================
@login_required
def eligible_courses_view(request):
    from .eligibility import get_eligible_courses

    kcse_result = UserKCSEResult.objects.filter(
        user=request.user
    ).order_by("-created_at").first()

    if not kcse_result:
        messages.info(
            request,
            "You haven't entered your KCSE results yet. "
            "Calculate your cluster points first."
        )
        return redirect("clusterpoints:calculator")

    all_results = get_eligible_courses(request.user, kcse_result)

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
        filtered = [
            r for r in filtered
            if query.lower() in r["course"].name.lower()
        ]

    # Counts by status
    eligible_count  = sum(1 for r in all_results if r["status"] == "eligible")
    nearly_count    = sum(1 for r in all_results if r["status"] == "nearly")
    not_elig_count  = sum(1 for r in all_results if r["status"] == "not_eligible")

    from courses.models import CourseType
    course_types = CourseType.objects.all()

    return render(request, "clusterpoints/eligible_courses.html", {
        "results": filtered,
        "kcse_result": kcse_result,
        "eligible_count": eligible_count,
        "nearly_count": nearly_count,
        "not_eligible_count": not_elig_count,
        "status_filter": status_filter,
        "type_filter": type_filter,
        "query": query,
        "course_types": course_types,
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