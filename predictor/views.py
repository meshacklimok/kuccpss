from __future__ import annotations

from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import HttpResponse

from courses.models import CourseOffering, CourseType
from .services import (
    predict_cutoff, eligibility, predict_all_for_student,
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
            for cr in latest.cluster_results.select_related("cluster").all():
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


# ── Quick PDF (1–2 pages: scores + eligibility table) ────────────────────────

def quick_pdf(request):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors

    student_scores = _cluster_scores_from_request(request)
    if not student_scores:
        return HttpResponse(
            "No cluster scores found. Please calculate your KCSE cluster points first.",
            status=400,
        )

    groups = predict_all_for_student(student_scores, top_per_cluster=5)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="kuccpss_eligibility.pdf"'

    c = canvas.Canvas(response, pagesize=A4)
    W, H = A4

    def header(page_num):
        c.setFillColor(colors.HexColor("#1e3a8a"))
        c.rect(0, H - 2*cm, W, 2*cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(1.5*cm, H - 1.3*cm, "KUCCPSS — Predicted 2026 Eligibility Report")
        c.setFont("Helvetica", 9)
        c.drawRightString(W - 1.5*cm, H - 1.3*cm, f"Page {page_num}")
        c.setFillColor(colors.black)

    def footer():
        c.setFont("Helvetica-Oblique", 7.5)
        c.setFillColor(colors.HexColor("#64748b"))
        c.drawCentredString(W / 2, 0.7*cm,
            "For guidance only. Based on 2021–2024 data. Verify cutoffs on the official KUCCPS portal before applying.")
        c.setFillColor(colors.black)

    STATUS_COLOR = {
        "HighLikelihood": colors.HexColor("#16a34a"),
        "Likely":         colors.HexColor("#4ade80"),
        "Borderline":     colors.HexColor("#f97316"),
        "Unlikely":       colors.HexColor("#dc2626"),
    }

    page = 1
    header(page)
    footer()

    y = H - 3*cm
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#1e3a8a"))
    c.drawString(1.5*cm, y, "YOUR CLUSTER SCORES vs PREDICTED 2026 CUTOFFS")
    y -= 0.6*cm

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawString(1.5*cm, y,
        "Method: 70% Weighted Moving Average + 30% latest year (backtested on 720 KUCCPS courses, MAE 1.63 pts).")
    y -= 0.8*cm

    for group in groups:
        kuccps_num    = group["kuccps_num"]
        cluster_name  = group["cluster_name"]
        student_score = group["student_score"]
        rows          = group["rows"]

        if y < 5*cm:
            c.showPage()
            page += 1
            header(page)
            footer()
            y = H - 3*cm

        cluster_label = (
            f"Cluster {kuccps_num} — {cluster_name}   |   "
            f"Your score: {student_score:.1f} / 48 pts"
        )
        c.setFillColor(colors.HexColor("#e8f0fe"))
        c.rect(1.5*cm, y - 0.45*cm, W - 3*cm, 0.6*cm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#1e3a8a"))
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(1.7*cm, y - 0.2*cm, cluster_label)
        y -= 0.9*cm

        # Column headers
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawString(1.7*cm,  y, "COURSE")
        c.drawString(9.0*cm,  y, "INSTITUTION")
        c.drawString(14.0*cm, y, "LATEST")
        c.drawString(15.8*cm, y, "PRED 2026")
        c.drawString(17.8*cm, y, "RANGE")
        c.drawString(19.8*cm, y, "STATUS")
        y -= 0.05*cm
        c.setStrokeColor(colors.HexColor("#cbd5e1"))
        c.line(1.5*cm, y, W - 1.5*cm, y)
        y -= 0.45*cm

        for row in rows:
            if y < 3.5*cm:
                c.showPage()
                page += 1
                header(page)
                footer()
                y = H - 3*cm

            pred  = row["pred"]
            elig  = row["elig"]
            label = elig["label"] if elig else "—"

            c.setFont("Helvetica", 7.5)
            c.setFillColor(colors.black)
            c.drawString(1.7*cm,  y, row["course"].name[:44])
            c.drawString(9.0*cm,  y, row["institution"].name[:26])
            c.drawString(14.0*cm, y, f"{pred['latest_cutoff']:.1f}")
            c.drawString(15.8*cm, y, f"{pred['predicted']:.1f}")
            c.drawString(17.8*cm, y, f"{pred['low']:.1f}–{pred['high']:.1f}")

            status_col = STATUS_COLOR.get(label, colors.grey)
            c.setFillColor(status_col)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(19.8*cm, y, label)

            y -= 0.45*cm

        y -= 0.3*cm

    c.save()
    return response


# ── Full placement report PDF (professional, 3 pages) ────────────────────────

def full_report_pdf(request):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors

    student_scores = _cluster_scores_from_request(request)
    if not student_scores:
        return HttpResponse(
            "No cluster scores found. Please calculate your KCSE cluster points first.",
            status=400,
        )

    mean_grade   = None
    total_points = None
    user_label   = "Student"

    if request.user.is_authenticated:
        from clusterpoints.models import UserKCSEResult
        latest = UserKCSEResult.objects.filter(user=request.user).order_by("-created_at").first()
        if latest:
            total_points = latest.total_points
        user_label = request.user.full_name or request.user.email
    else:
        guest        = request.session.get("guest_calc", {})
        total_points = guest.get("total_points")

    from clusterpoints.views import _mean_grade
    if total_points:
        mean_grade = _mean_grade(total_points)

    groups = predict_all_for_student(student_scores, top_per_cluster=6)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="kuccpss_placement_report.pdf"'

    c = canvas.Canvas(response, pagesize=A4)
    W, H = A4

    NAVY  = colors.HexColor("#1e3a8a")
    GREEN = colors.HexColor("#16a34a")
    SLATE = colors.HexColor("#64748b")
    LIGHT = colors.HexColor("#f1f5f9")

    STATUS_COLOR = {
        "HighLikelihood": colors.HexColor("#16a34a"),
        "Likely":         colors.HexColor("#4ade80"),
        "Borderline":     colors.HexColor("#f97316"),
        "Unlikely":       colors.HexColor("#dc2626"),
    }

    page_num = [0]

    def new_page(title=""):
        page_num[0] += 1
        if page_num[0] > 1:
            c.showPage()

        c.setFillColor(NAVY)
        c.rect(0, H - 1.8*cm, W, 1.8*cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(1.5*cm, H - 1.15*cm, "KUCCPSS Placement Report 2026")
        if title:
            c.setFont("Helvetica", 9)
            c.drawString(1.5*cm, H - 1.55*cm, title)
        c.setFont("Helvetica", 9)
        c.drawRightString(W - 1.5*cm, H - 1.15*cm, f"Page {page_num[0]} of 3")

        c.setFillColor(GREEN)
        c.rect(0, H - 1.85*cm, W, 0.08*cm, fill=1, stroke=0)

        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(SLATE)
        c.drawCentredString(W / 2, 0.6*cm,
            "KUCCPSS Predicted Report — For planning purposes only. "
            "Verify all cutoffs on the official KUCCPS portal (kuccps.net) before submitting applications.")
        c.setFillColor(colors.black)
        return H - 2.4*cm

    # ── PAGE 1: Cover / Profile ───────────────────────────────────────────────
    y = new_page("Page 1 — Student KCSE Profile")

    c.setFillColor(LIGHT)
    c.roundRect(1.5*cm, y - 3.5*cm, W - 3*cm, 3.2*cm, 8, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(2*cm, y - 1.1*cm, "KCSE Placement Readiness Report")
    c.setFont("Helvetica", 10)
    c.setFillColor(SLATE)
    c.drawString(2*cm, y - 1.7*cm, f"Prepared for: {user_label}")
    from django.utils import timezone
    c.drawString(2*cm, y - 2.2*cm, f"Generated:    {timezone.now().strftime('%d %B %Y')}")
    c.drawString(2*cm, y - 2.7*cm,
        "Prediction model: 70% WMA + 30% Naive blend (backtested MAE 1.63 pts)")

    if total_points or mean_grade:
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10)
        parts = []
        if total_points: parts.append(f"Aggregate: {total_points} / 84")
        if mean_grade:   parts.append(f"Mean Grade: {mean_grade}")
        c.drawString(2*cm, y - 3.2*cm, "   |   ".join(parts))

    y -= 4.2*cm

    # Cluster scores mini bar-chart — use KUCCPS 1–20 labels
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(NAVY)
    c.drawString(1.5*cm, y, "YOUR CLUSTER SCORES (out of 48)")
    y -= 0.5*cm

    kuccps_list = list(range(1, 21))
    col_w = (W - 3*cm) / 4
    for i, kuccps_n in enumerate(kuccps_list):
        calc_n = kuccps_n + 100
        score  = student_scores.get(calc_n)
        col    = i % 4
        if col == 0 and i > 0:
            y -= 1*cm
        x = 1.5*cm + col * col_w

        bar_w = (score / 48 * (col_w - 0.4*cm)) if score else 0
        c.setFillColor(LIGHT)
        c.rect(x, y - 0.5*cm, col_w - 0.3*cm, 0.3*cm, fill=1, stroke=0)
        c.setFillColor(
            GREEN if score and score >= 36
            else NAVY if score and score >= 24
            else colors.HexColor("#f97316")
        )
        c.rect(x, y - 0.5*cm, bar_w, 0.3*cm, fill=1, stroke=0)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(colors.black)
        label_txt = f"C{kuccps_n}: {score:.1f}" if score else f"C{kuccps_n}: —"
        c.drawString(x, y - 0.9*cm, label_txt)

    y -= 1.8*cm
    c.setFont("Helvetica", 8)
    c.setFillColor(SLATE)
    c.drawString(1.5*cm, y,
        "Green = 36+ pts (Strong)   |   Blue = 24–35 pts (Moderate)   |   Orange = below 24 pts")

    # ── PAGE 2: Predicted Eligibility ─────────────────────────────────────────
    y = new_page("Page 2 — Predicted 2026 Course Eligibility")

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(NAVY)
    c.drawString(1.5*cm, y, "PREDICTED 2026 ELIGIBILITY BY CLUSTER")
    y -= 0.4*cm
    c.setFont("Helvetica", 8)
    c.setFillColor(SLATE)
    c.drawString(1.5*cm, y,
        "Prediction: 70% Weighted Moving Avg + 30% latest year  |  "
        "Latest = most recent actual cutoff  |  Range = confidence band")
    y -= 0.7*cm

    for group in groups:
        if y < 4*cm:
            y = new_page("Page 2 (continued) — Predicted 2026 Course Eligibility")

        kuccps_num    = group["kuccps_num"]
        cluster_name  = group["cluster_name"]
        student_score = group["student_score"]
        rows          = group["rows"]

        c.setFillColor(colors.HexColor("#e8f0fe"))
        c.rect(1.5*cm, y - 0.4*cm, W - 3*cm, 0.55*cm, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(1.7*cm, y - 0.18*cm,
            f"Cluster {kuccps_num} — {cluster_name}   |   "
            f"Your score: {student_score:.1f} / 48 pts")
        y -= 0.75*cm

        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(SLATE)
        c.drawString(1.7*cm,  y, "COURSE")
        c.drawString(8.5*cm,  y, "INSTITUTION")
        c.drawString(13.5*cm, y, "LATEST")
        c.drawString(15.2*cm, y, "PRED 2026")
        c.drawString(17.2*cm, y, "RANGE")
        c.drawString(19.2*cm, y, "STATUS")
        y -= 0.08*cm
        c.setStrokeColor(colors.HexColor("#cbd5e1"))
        c.line(1.5*cm, y, W - 1.5*cm, y)
        y -= 0.4*cm

        for row in rows:
            if y < 3*cm:
                y = new_page("Page 2 (continued) — Predicted 2026 Course Eligibility")
                y -= 0.3*cm

            pred  = row["pred"]
            elig  = row["elig"]
            label = elig["label"] if elig else "—"

            c.setFont("Helvetica", 7.5)
            c.setFillColor(colors.black)
            c.drawString(1.7*cm,  y, row["course"].name[:44])
            c.drawString(8.5*cm,  y, row["institution"].name[:28])
            c.drawString(13.5*cm, y, f"{pred['latest_cutoff']:.1f}")
            c.drawString(15.2*cm, y, f"{pred['predicted']:.1f}")
            c.drawString(17.2*cm, y, f"{pred['low']:.1f}–{pred['high']:.1f}")

            c.setFillColor(STATUS_COLOR.get(label, SLATE))
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(19.2*cm, y, label)
            y -= 0.42*cm

        y -= 0.25*cm

    # ── PAGE 3: Legend, Action Plan, Disclaimer ───────────────────────────────
    y = new_page("Page 3 — How to Use This Report")

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(NAVY)
    c.drawString(1.5*cm, y, "UNDERSTANDING YOUR RESULTS")
    y -= 0.7*cm

    status_guide = [
        ("High Likelihood", STATUS_COLOR["HighLikelihood"],
         "Your score exceeds even the high-end estimate. Strong candidate — apply with confidence."),
        ("Likely",          STATUS_COLOR["Likely"],
         "Your score is above the predicted cutoff. Solid chance — include in your top choices."),
        ("Borderline",      STATUS_COLOR["Borderline"],
         "Your score falls within the confidence band. Possible — use as a strategic second choice."),
        ("Unlikely",        STATUS_COLOR["Unlikely"],
         "Your score is below the predicted low. Very competitive — consider as a long-shot only."),
    ]

    for lbl, col, desc in status_guide:
        c.setFillColor(col)
        c.roundRect(1.5*cm, y - 0.45*cm, 2.2*cm, 0.5*cm, 4, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(2.6*cm, y - 0.22*cm, lbl)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 8.5)
        c.drawString(4.0*cm, y - 0.22*cm, desc)
        y -= 0.7*cm

    y -= 0.3*cm
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(NAVY)
    c.drawString(1.5*cm, y, "HOW PREDICTIONS ARE CALCULATED")
    y -= 0.5*cm
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.black)
    pred_explanation = [
        "Formula: 70% × WMA + 30% × latest year's actual cutoff.",
        "WMA (4 years): 40% × 2024 + 30% × 2023 + 20% × 2022 + 10% × 2021.",
        "Backtested on 720 KUCCPS courses — lowest Mean Absolute Error (1.63 pts) "
        "of 7 methods tested including Linear Trend, Holt's Exponential Smoothing, "
        "and Naive forecasting.",
    ]
    for line in pred_explanation:
        # Wrap long lines
        words = line.split()
        cur, wrapped = "", []
        for w in words:
            test = f"{cur} {w}".strip()
            if c.stringWidth(test, "Helvetica", 8.5) < (W - 4*cm):
                cur = test
            else:
                wrapped.append(cur)
                cur = w
        if cur:
            wrapped.append(cur)
        for wl in wrapped:
            c.drawString(1.7*cm, y, wl)
            y -= 0.42*cm
        y -= 0.1*cm

    y -= 0.3*cm
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(NAVY)
    c.drawString(1.5*cm, y, "RECOMMENDED NEXT STEPS")
    y -= 0.55*cm

    steps = [
        "1. Log in to the KUCCPS student portal (students.kuccps.net) when it opens.",
        "2. Choose 3 degree programmes — list your strongest High Likelihood/Likely course first.",
        "3. Add at least one safe fallback choice (a Likely course in a lower-cutoff programme).",
        "4. Select up to 3 KMTC and 3 TVET options as alternative pathways.",
        "5. Use the KUCCPSS Eligible Courses page to cross-check official cutoffs as they are released.",
        "6. Return to KUCCPSS when 2025 data is published — predictions will auto-improve.",
    ]
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.black)
    for step in steps:
        c.drawString(1.7*cm, y, step)
        y -= 0.48*cm

    y -= 0.3*cm
    c.setFillColor(LIGHT)
    c.roundRect(1.5*cm, y - 2.5*cm, W - 3*cm, 2.3*cm, 6, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#92400e"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(2*cm, y - 0.5*cm, "IMPORTANT DISCLAIMER")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    disclaimer = (
        "This report is generated for planning purposes only. Predicted cutoff points are estimated "
        "using a weighted average and linear trend of historical KUCCPS data from 2021 to 2024. "
        "Actual 2026 cutoffs depend on cohort performance, institutional capacity, and KUCCPS "
        "policy — factors that cannot be predicted with certainty. KUCCPSS accepts no liability "
        "for placement outcomes based on this report. Always verify current cutoff points on the "
        "official KUCCPS portal at kuccps.net before submitting your course choices."
    )
    words = disclaimer.split()
    line, lines_out = "", []
    for w in words:
        test = f"{line} {w}".strip()
        if c.stringWidth(test, "Helvetica", 8) < (W - 4.5*cm):
            line = test
        else:
            lines_out.append(line)
            line = w
    if line:
        lines_out.append(line)
    dy = y - 1.0*cm
    for lo in lines_out:
        c.drawString(2*cm, dy, lo)
        dy -= 0.38*cm

    c.save()
    return response
