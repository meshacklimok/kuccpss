from __future__ import annotations

from django.shortcuts import render
from django.core.paginator import Paginator

from courses.models import CourseOffering, CourseType
from .services import (
    predict_cutoff, eligibility,
    TREND_ICON, TREND_COLOR, TREND_TIP,
    COURSE_TO_CALC, COURSE_TO_KUCCPS, KUCCPS_NAMES,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _cluster_scores_from_request(request) -> dict[int, float]:
    """Pull cluster scores (calc numbers 101–120) from DB (auth) or session (guest)."""
    scores = {}

    if request.user.is_authenticated:
        from clusterpoints.models import UserKCSEResult
        latest = UserKCSEResult.objects.filter(user=request.user).order_by("-created_at").first()
        if latest:
            for cr in latest.cluster_results.select_related("cluster").all():  # type: ignore[attr-defined]
                if cr.cluster and cr.cluster.number:
                    scores[cr.cluster.number] = float(cr.cluster_points)
    else:
        guest = request.session.get("guest_calc", {})
        named = guest.get("named_points", {})
        if named:
            from clusterpoints.services import calculate_clusters_anonymous
            results = calculate_clusters_anonymous(named)
            for r in results:
                if r.cluster and r.cluster.number:
                    scores[r.cluster.number] = float(r.cluster_points)

    return scores


def _all_offerings_with_pred(query="", kuccps_cluster=None, course_type_slug="",
                              student_scores: dict | None = None,
                              status_filter: str = ""):
    """Return enriched rows with prediction data, KUCCPS cluster numbers, and eligibility."""
    qs = (
        CourseOffering.objects
        .select_related("course", "institution", "course__cluster", "course__course_type")
        .exclude(cutoff_points__isnull=True)
        .order_by("course__name", "institution__name")
    )

    if query:
        qs = qs.filter(course__name__icontains=query)
    if kuccps_cluster:
        # filter by sub-group cluster numbers that map to this KUCCPS cluster
        from .services import CALC_TO_COURSE
        course_cluster_nums = CALC_TO_COURSE.get(kuccps_cluster + 100, [])
        if course_cluster_nums:
            qs = qs.filter(course__cluster__number__in=course_cluster_nums)
        else:
            return []
    if course_type_slug:
        qs = qs.filter(course__course_type__slug=course_type_slug)

    rows = []
    for o in qs:
        pred = predict_cutoff(o.cutoff_points)
        if pred is None:
            continue

        # Resolve KUCCPS cluster number (1–20) from sub-group cluster number
        course_cluster_num = o.course.cluster.number if o.course.cluster else None
        kuccps_num = COURSE_TO_KUCCPS.get(course_cluster_num) if course_cluster_num else None
        kuccps_name = KUCCPS_NAMES.get(kuccps_num, "") if kuccps_num else ""

        score = None
        elig  = None
        if student_scores and o.course.cluster:
            calc_num = COURSE_TO_CALC.get(o.course.cluster.number)
            if calc_num and calc_num in student_scores:
                score = student_scores[calc_num]
                elig  = eligibility(score, pred)

        pred["trend_icon"]  = TREND_ICON[pred["trend"]]
        pred["trend_color"] = TREND_COLOR[pred["trend"]]
        pred["trend_tip"]   = TREND_TIP[pred["trend"]]

        row = {
            "offering":    o,
            "course":      o.course,
            "institution": o.institution,
            "pred":        pred,
            "score":       score,
            "elig":        elig,
            "kuccps_num":  kuccps_num,
            "kuccps_name": kuccps_name,
        }

        # Apply eligibility filter
        if status_filter and elig:
            if elig["key"].lower() != status_filter.lower():
                continue
        elif status_filter and not elig:
            continue

        rows.append(row)
    return rows


# ── Standalone predictor page ─────────────────────────────────────────────────

def predictor_index(request):
    query            = request.GET.get("q", "").strip()
    cluster_param    = request.GET.get("cluster", "").strip()
    course_type_slug = request.GET.get("type", "").strip()
    status_filter    = request.GET.get("status", "").strip()

    kuccps_cluster = int(cluster_param) if cluster_param.isdigit() else None

    student_scores = _cluster_scores_from_request(request)

    rows = _all_offerings_with_pred(
        query=query,
        kuccps_cluster=kuccps_cluster,
        course_type_slug=course_type_slug,
        student_scores=student_scores or None,
        status_filter=status_filter,
    )

    # Eligibility counts (over unfiltered rows that have elig)
    all_rows_for_counts = rows if not status_filter else _all_offerings_with_pred(
        query=query, kuccps_cluster=kuccps_cluster, course_type_slug=course_type_slug,
        student_scores=student_scores or None, status_filter="",
    )
    elig_counts = {}
    if student_scores:
        for r in all_rows_for_counts:
            if r["elig"]:
                lbl = r["elig"]["key"]
                elig_counts[lbl] = elig_counts.get(lbl, 0) + 1

    paginator = Paginator(rows, 30)
    page_obj  = paginator.get_page(request.GET.get("page", 1))

    # Build 20-cluster list for dropdown
    kuccps_clusters = [{"number": n, "name": KUCCPS_NAMES[n]} for n in range(1, 21)]
    course_types    = CourseType.objects.all()
    has_scores   = bool(student_scores)
    _key_to_label = {
        "HighLikelihood": "High Likelihood",
        "Likely":         "Likely",
        "Borderline":     "Borderline",
        "Unlikely":       "Unlikely",
    }
    status_label = _key_to_label.get(status_filter, status_filter)

    return render(request, "predictor/index.html", {
        "page_obj":         page_obj,
        "query":            query,
        "cluster_num":      cluster_param,
        "course_type_slug": course_type_slug,
        "status_filter":    status_filter,
        "status_label":     status_label,
        "kuccps_clusters":  kuccps_clusters,
        "course_types":     course_types,
        "has_scores":       has_scores,
        "student_scores":   student_scores,
        "total_count":      paginator.count,
        "elig_counts":      elig_counts,
    })
