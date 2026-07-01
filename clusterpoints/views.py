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
        best = max(langs, key=lambda k: langs[k])
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
        cluster_results = kcse_result.cluster_results.select_related("cluster").order_by("-cluster_points")  # type: ignore[attr-defined]

    return render(request, "clusterpoints/dashboard.html", {
        "kcse_result": kcse_result,
        "cluster_results": cluster_results,
    })


# =====================================================
# KCSE CALCULATOR VIEW
# =====================================================
def kcse_calculator_view(request):
    from predictor.services import predict_all_for_student
    from career.models import CareerSubmission, SubmissionLockConfig

    # ── Submission lock gate (authenticated users only) ──────────────────────
    lock_cfg = SubmissionLockConfig.get_for_feature(CareerSubmission.FEATURE_CALCULATOR)
    existing_sub = None
    if request.user.is_authenticated and lock_cfg and lock_cfg.is_enabled:
        existing_sub = CareerSubmission.objects.filter(
            user=request.user, feature=CareerSubmission.FEATURE_CALCULATOR
        ).first()
        if existing_sub:
            if existing_sub.status == CareerSubmission.STATUS_PENDING and timezone.now() >= existing_sub.lock_at:
                existing_sub.status = CareerSubmission.STATUS_LOCKED
                existing_sub.save(update_fields=['status'])
            if existing_sub.status == CareerSubmission.STATUS_LOCKED and request.method == 'POST':
                # Official resubmit bypass: admin flips allow_official_resubmit when KNEC releases
                # real results — lets a user who estimated via calculator enter real grades once
                # via Upload/Paste/Manual (the calculator form itself stays blocked).
                is_official_path = request.POST.get('entry_method') in ('upload', 'paste', 'manual')
                if is_official_path and lock_cfg.allow_official_resubmit and existing_sub.method == CareerSubmission.METHOD_CALCULATE:
                    pass  # allow through; will overwrite submission with official data
                else:
                    return redirect('clusterpoints:calculator')

    form = KCSEForm(request.POST or None)

    # Pre-fill form from pending saved grades on GET
    if request.method == 'GET' and existing_sub and existing_sub.status == CareerSubmission.STATUS_PENDING:
        subjects_qs = Subject.objects.all()
        name_to_id = {s.name: s.pk for s in subjects_qs}
        initial = {
            f'subject_{name_to_id[name]}': pts
            for name, pts in existing_sub.grades_json.items()
            if name in name_to_id
        }
        form = KCSEForm(initial=initial)

    results = []
    total_points = None
    kcse_result = None
    predicted_groups = []

    # ── Restore guest session after sign-up redirect ──────────────────────────
    if (request.method == 'GET'
            and request.GET.get('restore')
            and request.user.is_authenticated):
        guest_calc = request.session.get('guest_calc')
        if guest_calc:
            named_points = guest_calc.get('named_points', {})
            if named_points:
                subjects_qs = Subject.objects.all()
                name_to_id  = {s.name: s.pk for s in subjects_qs}
                id_to_subj  = {s.pk: s for s in subjects_qs}
                points_dict = {name_to_id[n]: p for n, p in named_points.items() if n in name_to_id}
                with transaction.atomic():
                    UserKCSEResult.objects.filter(user=request.user).delete()
                    kcse_result = UserKCSEResult.objects.create(user=request.user, created_at=timezone.now())
                    SubjectResult.objects.bulk_create([
                        SubjectResult(kcse_result=kcse_result, subject=id_to_subj[sid], points=pts)
                        for sid, pts in points_dict.items() if sid in id_to_subj
                    ])
                    kcse_result.recalc_total_points()
                    total_points = kcse_result.total_points
                    results = calculate_all_clusters(kcse_result)
                request.session.pop('guest_calc', None)
                request.session.pop('guest_cluster_map', None)
                messages.success(request, "Your KCSE results have been saved!")
                cluster_scores = {
                    r.cluster.number: float(r.cluster_points)
                    for r in results if r.cluster and r.cluster.number
                }
                predicted_groups = predict_all_for_student(cluster_scores, top_per_cluster=5) if cluster_scores else []

    # ── Load existing saved results on GET (e.g. after payment unlock) ──────────
    if request.method == 'GET' and request.user.is_authenticated and not results:
        _saved = UserKCSEResult.objects.filter(user=request.user).order_by('-created_at').first()
        if _saved:
            kcse_result = _saved
            total_points = kcse_result.total_points
            results = list(kcse_result.cluster_results.select_related('cluster').order_by('-cluster_points'))  # type: ignore[attr-defined]
            if results:
                _cs = {r.cluster.number: float(r.cluster_points) for r in results if r.cluster and r.cluster.number}
                if _cs:
                    predicted_groups = predict_all_for_student(_cs, top_per_cluster=5)

    if request.method == "POST":
        if form.is_valid():
            points_dict = form.get_points_dict()  # {subject_id: points}
            subject_ids = [int(s) for s in points_dict.keys()]
            subjects_map = {s.pk: s for s in Subject.objects.filter(id__in=subject_ids)}  # type: ignore[misc]

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
                # Bust the eligible-courses cache so the new grades take effect immediately
                from django.core.cache import cache as _cache
                _cache.delete(f"elig_user_{request.user.pk}_{kcse_result.pk}")
                messages.success(request, "KCSE results saved and cluster points calculated!")
                try:
                    from analytics.utils import log_event as _log_event
                    _log_event(request, 'calculator_run', {
                        'mean_grade': _mean_grade(total_points),
                        'total_points': total_points,
                        'auth': True,
                    })
                except Exception:
                    pass

                # Save/reset the grace-period submission record
                if lock_cfg and lock_cfg.is_enabled:
                    from datetime import timedelta
                    CareerSubmission.objects.update_or_create(
                        user=request.user,
                        feature=CareerSubmission.FEATURE_CALCULATOR,
                        defaults={
                            'grades_json': named_points,
                            'status': CareerSubmission.STATUS_PENDING,
                            'lock_at': timezone.now() + timedelta(minutes=lock_cfg.lock_minutes),
                            'unlocked_by_payment': None,  # new session requires new payment
                        },
                    )
                    existing_sub = CareerSubmission.objects.filter(
                        user=request.user, feature=CareerSubmission.FEATURE_CALCULATOR
                    ).first()

            else:
                # ── Guest: compute in memory, stash in session, then gate ──
                results = calculate_clusters_anonymous(named_points)
                total_points = _compute_aggregate(named_points)
                try:
                    from analytics.utils import log_event as _log_event
                    _log_event(request, 'calculator_run', {
                        'mean_grade': _mean_grade(total_points),
                        'total_points': total_points,
                        'auth': False,
                    })
                except Exception:
                    pass
                request.session['guest_calc'] = {
                    'named_points': named_points,
                    'total_points': total_points,
                }
                request.session['guest_cluster_map'] = {
                    r.cluster.kuccps_number: float(r.cluster_points)
                    for r in results
                    if r.cluster and r.cluster.kuccps_number is not None
                }
                from django.urls import reverse as _rev
                return redirect(_rev('accounts:register') + '?next=/clusterpoints/calculator/?restore=1')

            # ── Build cluster scores dict and run predictor ────────────────
            cluster_scores = {
                r.cluster.number: float(r.cluster_points)
                for r in results
                if r.cluster and r.cluster.number
            }
            if cluster_scores:
                predicted_groups = predict_all_for_student(cluster_scores, top_per_cluster=5)

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
        _e = (_s, form[f'subject_{_s.pk}'], _ICONS.get(_s.name, 'bi-journal'))  # type: ignore[misc]
        if _s.name in _COMP:
            compulsory_fields.append(_e)
        elif _s.group in _gmap:
            _gmap[_s.group].append(_e)
    optional_groups = [(_GM[g], _gmap[g]) for g, _ in _GC if g != 'I' and _gmap.get(g)]

    # Top-5 courses per cluster for the results section
    cluster_courses_map = {}   # {cluster_id: [Course, ...]}
    cluster_course_counts = {} # {cluster_id: int}
    if results:
        from courses.models import Course as _Course
        cluster_ids = [r.cluster.id for r in results if r.cluster]
        _all_courses = (
            _Course.objects
            .filter(cluster_id__in=cluster_ids, course_type__name__iexact='Degree')
            .select_related('course_type')
            .order_by('cluster_id', 'name')
        )
        for _c in _all_courses:
            cid = _c.cluster_id  # type: ignore[attr-defined]
            cluster_course_counts[cid] = cluster_course_counts.get(cid, 0) + 1
            lst = cluster_courses_map.setdefault(cid, [])
            if len(lst) < 5:
                lst.append(_c)

        # Attach to each result so the template needs no extra queries
        for _r in results:
            cid = _r.cluster.id if _r.cluster else None
            _r.top_courses = cluster_courses_map.get(cid, [])  # type: ignore[attr-defined]
            _r.course_count = cluster_course_counts.get(cid, 0)  # type: ignore[attr-defined]

    # Grace-period banner data for the template
    sub_banner = None
    if existing_sub and existing_sub.status == CareerSubmission.STATUS_PENDING and results:
        from django.urls import reverse
        sub_banner = {
            'seconds_remaining': existing_sub.seconds_remaining(),
            'lock_at_iso': existing_sub.lock_at.isoformat(),
            'feature': CareerSubmission.FEATURE_CALCULATOR,
            'edit_url': reverse('clusterpoints:calculator'),
        }

    from payments.services import has_paid_for_current_session, is_feature_enabled, price_for_feature
    _gate_feature = "view_cluster_points"
    _gate_enabled = is_feature_enabled(_gate_feature)
    _is_locked = (
        bool(results)
        and request.user.is_authenticated
        and _gate_enabled
        and not has_paid_for_current_session(request.user, CareerSubmission.FEATURE_CALCULATOR, _gate_feature)
    )

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
        "cluster_courses_map": cluster_courses_map,
        "cluster_course_counts": cluster_course_counts,
        "sub_banner": sub_banner,
        "is_results_locked": _is_locked,
        "gate_feature": _gate_feature,
        "gate_price": price_for_feature(_gate_feature),
    })


# =====================================================
# EXPORT ALL CLUSTER RESULTS AS PDF
# =====================================================
@login_required
def export_cluster_pdf(request):
    """Export all 20 cluster results for user's latest KCSE result — styled report."""
    from reportlab.lib import colors as rc

    kcse_result = UserKCSEResult.objects.filter(
        user=request.user
    ).order_by('-created_at').first()

    if not kcse_result:
        messages.error(request, "No KCSE results found. Please use the calculator first.")
        return redirect("clusterpoints:calculator")

    cluster_results = list(
        kcse_result.cluster_results.select_related('cluster').order_by('cluster__number')  # type: ignore[attr-defined]
    )

    try:
        from analytics.utils import log_download as _log_download
        _log_download(request, 'cluster_pdf', object_id=kcse_result.pk)
    except Exception:
        pass

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="careernext_cluster_points_quick.pdf"'

    p = canvas.Canvas(response, pagesize=A4)  # type: ignore[arg-type]
    W, H = A4

    # Brand colour palette
    NAVY    = rc.HexColor("#1e3a8a")
    TEAL    = rc.HexColor("#0e7490")
    EMERALD = rc.HexColor("#059669")
    AMBER   = rc.HexColor("#d97706")
    PURPLE  = rc.HexColor("#7c3aed")
    SLATE   = rc.HexColor("#475569")
    LIGHT   = rc.HexColor("#f0f9ff")
    WHITE   = rc.white

    page_num = [0]

    def draw_page():
        page_num[0] += 1
        if page_num[0] > 1:
            p.showPage()
        # ── Header ──────────────────────────────────────────────────────────
        p.setFillColor(NAVY)
        p.rect(0, H - 2.0*cm, W, 2.0*cm, fill=1, stroke=0)
        p.setFillColor(TEAL)
        p.rect(0, H - 2.1*cm, W, 0.12*cm, fill=1, stroke=0)
        p.setFillColor(WHITE)
        p.setFont("Helvetica-Bold", 13)
        p.drawString(1.5*cm, H - 1.2*cm, "CareerNext — KCSE Cluster Points Report")
        p.setFont("Helvetica-Oblique", 7.5)
        p.setFillColor(rc.HexColor("#93c5fd"))
        p.drawString(1.5*cm, H - 1.72*cm, "Your Journey Begins Here")
        p.setFont("Helvetica", 8)
        p.setFillColor(rc.HexColor("#bfdbfe"))
        p.drawRightString(W - 1.5*cm, H - 1.3*cm, f"careernext.co.ke   |   Page {page_num[0]}")
        # ── Footer ──────────────────────────────────────────────────────────
        p.setFillColor(TEAL)
        p.rect(0, 1.35*cm, W, 0.08*cm, fill=1, stroke=0)
        p.setFillColor(NAVY)
        p.rect(0, 0, W, 1.35*cm, fill=1, stroke=0)
        p.setFillColor(WHITE)
        p.setFont("Helvetica-Bold", 7.5)
        p.drawCentredString(W / 2, 0.82*cm, "careernext.co.ke  —  Your Journey Begins Here")
        p.setFont("Helvetica", 6.5)
        p.setFillColor(rc.HexColor("#93c5fd"))
        p.drawCentredString(W / 2, 0.45*cm,
            "Apply officially at kuccps.net  |  For guidance only — verify all details before applying")
        return H - 2.5*cm

    y = draw_page()

    user_name = getattr(request.user, 'full_name', None) or request.user.email
    mg = _mean_grade(kcse_result.total_points)

    # Grade badge colour
    if mg and mg[0] == 'A':
        grade_col = PURPLE
    elif mg and mg[0] == 'B':
        grade_col = EMERALD
    elif mg and mg[0] == 'C':
        grade_col = AMBER
    else:
        grade_col = rc.HexColor("#dc2626")

    # ── Student profile card ─────────────────────────────────────────────────
    p.setFillColor(LIGHT)
    p.roundRect(1.2*cm, y - 2.6*cm, W - 2.4*cm, 2.4*cm, 6, fill=1, stroke=0)
    p.setFillColor(TEAL)
    p.rect(1.2*cm, y - 2.6*cm, 0.35*cm, 2.4*cm, fill=1, stroke=0)

    p.setFillColor(NAVY)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(1.9*cm, y - 0.65*cm, (user_name or '')[:50])
    p.setFillColor(SLATE)
    p.setFont("Helvetica", 9)
    p.drawString(1.9*cm, y - 1.15*cm, f"Generated: {timezone.now().strftime('%d %B %Y')}")
    p.drawString(1.9*cm, y - 1.62*cm, f"KCSE Aggregate Total: {kcse_result.total_points} / 84")
    p.drawString(1.9*cm, y - 2.08*cm, f"Mean Grade: {mg or '—'}")

    # Grade badge (right side of card)
    p.setFillColor(grade_col)
    p.roundRect(W - 4.0*cm, y - 2.35*cm, 2.4*cm, 1.9*cm, 8, fill=1, stroke=0)
    p.setFillColor(WHITE)
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(W - 2.8*cm, y - 1.45*cm, mg or '—')
    p.setFont("Helvetica", 6.5)
    p.drawCentredString(W - 2.8*cm, y - 1.9*cm, "KCSE Grade")
    p.setFont("Helvetica", 5.5)
    p.drawCentredString(W - 2.8*cm, y - 2.2*cm, "visit www.careernext.co.ke")

    y -= 3.1*cm

    # ── Section heading ──────────────────────────────────────────────────────
    p.setFillColor(NAVY)
    p.setFont("Helvetica-Bold", 9.5)
    p.drawString(1.5*cm, y, "ALL 20 KUCCPS CLUSTER SCORES")
    p.setFillColor(SLATE)
    p.setFont("Helvetica", 7.5)
    p.drawString(1.5*cm, y - 0.4*cm,
        f"Calculated {len(cluster_results)} clusters   |   Maximum per cluster: 48 pts")
    y -= 0.82*cm

    # ── Colour legend ────────────────────────────────────────────────────────
    for lx, lc, lt in [
        (1.5*cm,  EMERALD, "Strong (36–48 pts)"),
        (6.0*cm,  NAVY,    "Moderate (24–35 pts)"),
        (11.2*cm, AMBER,   "Below 24 pts"),
    ]:
        p.setFillColor(lc)
        p.roundRect(lx, y - 0.2*cm, 0.18*cm, 0.18*cm, 2, fill=1, stroke=0)
        p.setFillColor(SLATE)
        p.setFont("Helvetica", 7)
        p.drawString(lx + 0.28*cm, y - 0.12*cm, lt)
    y -= 0.52*cm

    # ── Cluster grid — 2 columns ─────────────────────────────────────────────
    COL_W  = (W - 3.2*cm) / 2
    CELL_H = 1.05*cm
    GAP    = 0.12*cm
    col_x  = [1.5*cm, 1.5*cm + COL_W + 0.2*cm]

    def score_col_bg(pts):
        if pts >= 36:
            return EMERALD, rc.HexColor("#d1fae5")
        if pts >= 24:
            return NAVY, rc.HexColor("#dbeafe")
        return AMBER, rc.HexColor("#fef3c7")

    row_offset = 0
    for i, r in enumerate(cluster_results):
        col = i % 2
        if col == 0 and i > 0:
            row_offset += 1

        # Page break at the start of each new row pair
        if col == 0 and (y - row_offset * (CELL_H + GAP) - CELL_H) < 1.7*cm:
            y = draw_page()
            row_offset = 0

        cell_y = y - row_offset * (CELL_H + GAP)
        x = col_x[col]
        pts = float(r.cluster_points)
        sc, bg = score_col_bg(pts)

        # Card background
        p.setFillColor(bg)
        p.roundRect(x, cell_y - CELL_H, COL_W - 0.1*cm, CELL_H, 4, fill=1, stroke=0)
        # Left colour stripe
        p.setFillColor(sc)
        p.rect(x, cell_y - CELL_H, 0.22*cm, CELL_H, fill=1, stroke=0)

        knum  = r.cluster.kuccps_number if r.cluster else '?'
        cname = (r.cluster.name if r.cluster else 'Unknown')[:30]

        p.setFillColor(NAVY)
        p.setFont("Helvetica-Bold", 7.5)
        p.drawString(x + 0.38*cm, cell_y - 0.32*cm, f"Cluster {knum}")
        p.setFillColor(SLATE)
        p.setFont("Helvetica", 6.8)
        p.drawString(x + 0.38*cm, cell_y - 0.63*cm, cname)

        # Score badge
        p.setFillColor(sc)
        p.roundRect(x + COL_W - 2.6*cm, cell_y - 0.88*cm, 2.3*cm, 0.72*cm, 4, fill=1, stroke=0)
        p.setFillColor(WHITE)
        p.setFont("Helvetica-Bold", 8.5)
        p.drawCentredString(x + COL_W - 1.45*cm, cell_y - 0.55*cm, f"{pts:.1f} / 48")

    # ── Disclaimer block ─────────────────────────────────────────────────────
    # Reserve space at bottom of last page
    disclaimer_y = 2.2*cm
    p.setFillColor(rc.HexColor("#f8fafc"))
    p.roundRect(1.2*cm, disclaimer_y - 0.7*cm, W - 2.4*cm, 0.7*cm, 4, fill=1, stroke=0)
    p.setStrokeColor(rc.HexColor("#cbd5e1"))
    p.roundRect(1.2*cm, disclaimer_y - 0.7*cm, W - 2.4*cm, 0.7*cm, 4, fill=0, stroke=1)
    p.setFillColor(SLATE)
    p.setFont("Helvetica-Oblique", 6)
    p.drawCentredString(W / 2, disclaimer_y - 0.28*cm,
        "Disclaimer: These cluster points are calculated for guidance purposes only. "
        "Always confirm official cutoffs at kuccps.net before applying.")
    p.setFont("Helvetica", 6)
    p.drawCentredString(W / 2, disclaimer_y - 0.54*cm,
        "Use our engine to discover all courses you qualify for: www.careernext.co.ke")

    p.save()
    return response


# =====================================================
# FULL RESULTS PDF (cluster scores + eligible courses)
# =====================================================
@login_required
def export_full_results_pdf(request):
    """
    Comprehensive PDF: student profile, all cluster scores, eligible degree
    courses (eligible then nearly-there), and a next-steps action plan.
    """
    from reportlab.lib import colors as rc
    from .eligibility import get_eligible_courses

    kcse_result = UserKCSEResult.objects.filter(
        user=request.user
    ).order_by('-created_at').first()

    if not kcse_result:
        messages.error(request, "No KCSE results found. Please use the calculator first.")
        return redirect("clusterpoints:calculator")

    cluster_results = list(
        kcse_result.cluster_results.select_related('cluster').order_by('cluster__number')  # type: ignore[attr-defined]
    )
    eligible_list = get_eligible_courses(request.user, kcse_result)
    eligible = sorted([r for r in eligible_list if r['status'] == 'eligible'],
                      key=lambda x: x['gap'])          # smallest positive gap first (+0.1 → +40)
    nearly   = sorted([r for r in eligible_list if r['status'] == 'nearly'],
                      key=lambda x: x['gap'], reverse=True)  # closest to cutoff first (0 → -50)

    try:
        from analytics.utils import log_download as _log_download
        _log_download(request, 'career_pdf', object_id=kcse_result.pk)
    except Exception:
        pass

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="careernext_full_report.pdf"'

    p = canvas.Canvas(response, pagesize=A4)  # type: ignore[arg-type]
    W, H = A4

    NAVY    = rc.HexColor("#1e3a8a")
    TEAL    = rc.HexColor("#0e7490")
    EMERALD = rc.HexColor("#059669")
    AMBER   = rc.HexColor("#d97706")
    PURPLE  = rc.HexColor("#7c3aed")
    SLATE   = rc.HexColor("#475569")
    LIGHT   = rc.HexColor("#f0f9ff")
    RED     = rc.HexColor("#dc2626")
    WHITE   = rc.white

    page_num = [0]

    def new_page():
        page_num[0] += 1
        if page_num[0] > 1:
            p.showPage()
        p.setFillColor(NAVY)
        p.rect(0, H - 2.0*cm, W, 2.0*cm, fill=1, stroke=0)
        p.setFillColor(TEAL)
        p.rect(0, H - 2.1*cm, W, 0.12*cm, fill=1, stroke=0)
        p.setFillColor(WHITE)
        p.setFont("Helvetica-Bold", 13)
        p.drawString(1.5*cm, H - 1.2*cm, "CareerNext — KCSE Full Results Report")
        p.setFont("Helvetica-Oblique", 7.5)
        p.setFillColor(rc.HexColor("#93c5fd"))
        p.drawString(1.5*cm, H - 1.72*cm, "Your Journey Begins Here")
        p.setFont("Helvetica", 8)
        p.setFillColor(rc.HexColor("#bfdbfe"))
        p.drawRightString(W - 1.5*cm, H - 1.3*cm, f"Page {page_num[0]}  |  careernext.co.ke")
        p.setFillColor(TEAL)
        p.rect(0, 1.35*cm, W, 0.08*cm, fill=1, stroke=0)
        p.setFillColor(NAVY)
        p.rect(0, 0, W, 1.35*cm, fill=1, stroke=0)
        p.setFillColor(WHITE)
        p.setFont("Helvetica-Bold", 7.5)
        p.drawCentredString(W / 2, 0.82*cm, "careernext.co.ke  —  Your Journey Begins Here")
        p.setFont("Helvetica", 6.5)
        p.setFillColor(rc.HexColor("#93c5fd"))
        p.drawCentredString(W / 2, 0.45*cm,
            "For guidance only — verify all details on the official KUCCPS portal (kuccps.net) before applying")
        return H - 2.5*cm

    # ── PAGE 1: Student profile + cluster scores grid ─────────────────────────
    y = new_page()

    user_name = getattr(request.user, 'full_name', None) or request.user.email
    mg = _mean_grade(kcse_result.total_points)

    if mg and mg[0] == 'A':
        grade_col = PURPLE
    elif mg and mg[0] == 'B':
        grade_col = EMERALD
    elif mg and mg[0] == 'C':
        grade_col = AMBER
    else:
        grade_col = RED

    # Student profile card
    p.setFillColor(LIGHT)
    p.roundRect(1.2*cm, y - 2.6*cm, W - 2.4*cm, 2.4*cm, 6, fill=1, stroke=0)
    p.setFillColor(TEAL)
    p.rect(1.2*cm, y - 2.6*cm, 0.35*cm, 2.4*cm, fill=1, stroke=0)
    p.setFillColor(NAVY)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(1.9*cm, y - 0.65*cm, (user_name or '')[:55])
    p.setFillColor(SLATE)
    p.setFont("Helvetica", 9)
    p.drawString(1.9*cm, y - 1.15*cm, f"Generated: {timezone.now().strftime('%d %B %Y')}")
    p.drawString(1.9*cm, y - 1.62*cm, f"KCSE Aggregate: {kcse_result.total_points} / 84")
    p.drawString(1.9*cm, y - 2.08*cm, f"Mean Grade: {mg or '—'}")
    # Summary counts (right side)
    p.setFillColor(EMERALD)
    p.setFont("Helvetica-Bold", 10)
    p.drawRightString(W - 1.9*cm, y - 0.65*cm, f"{len(eligible)} Eligible Courses")
    p.setFillColor(AMBER)
    p.drawRightString(W - 1.9*cm, y - 1.15*cm, f"{len(nearly)} Nearly There")
    p.setFillColor(SLATE)
    p.setFont("Helvetica", 8)
    p.drawRightString(W - 1.9*cm, y - 1.62*cm, "Visit www.careernext.co.ke")
    # Mean grade badge
    p.setFillColor(grade_col)
    p.roundRect(W - 4.2*cm, y - 2.35*cm, 2.0*cm, 1.5*cm, 6, fill=1, stroke=0)
    p.setFillColor(WHITE)
    p.setFont("Helvetica-Bold", 15)
    p.drawCentredString(W - 3.2*cm, y - 1.55*cm, mg or '—')
    p.setFont("Helvetica", 6)
    p.drawCentredString(W - 3.2*cm, y - 1.9*cm, "KCSE Grade")
    p.setFont("Helvetica", 5)
    p.drawCentredString(W - 3.2*cm, y - 2.18*cm, "careernext.co.ke")

    y -= 3.2*cm

    # Cluster scores heading + legend
    p.setFillColor(NAVY)
    p.setFont("Helvetica-Bold", 9.5)
    p.drawString(1.5*cm, y, "ALL CLUSTER SCORES")
    p.setFillColor(SLATE)
    p.setFont("Helvetica", 7.5)
    p.drawString(1.5*cm, y - 0.4*cm,
        f"{len(cluster_results)} clusters calculated  |  Maximum per cluster: 48 pts")
    y -= 0.82*cm

    for lx, lc, lt in [
        (1.5*cm,  EMERALD, "Strong (36–48 pts)"),
        (6.0*cm,  NAVY,    "Moderate (24–35 pts)"),
        (11.2*cm, AMBER,   "Below 24 pts"),
    ]:
        p.setFillColor(lc)
        p.roundRect(lx, y - 0.2*cm, 0.18*cm, 0.18*cm, 2, fill=1, stroke=0)
        p.setFillColor(SLATE)
        p.setFont("Helvetica", 7)
        p.drawString(lx + 0.28*cm, y - 0.12*cm, lt)
    y -= 0.52*cm

    COL_W  = (W - 3.2*cm) / 2
    CELL_H = 1.05*cm
    GAP    = 0.12*cm
    col_x  = [1.5*cm, 1.5*cm + COL_W + 0.2*cm]

    def _score_col_bg(pts):
        if pts >= 36:
            return EMERALD, rc.HexColor("#d1fae5")
        if pts >= 24:
            return NAVY, rc.HexColor("#dbeafe")
        return AMBER, rc.HexColor("#fef3c7")

    row_offset = 0
    for i, r in enumerate(cluster_results):
        col = i % 2
        if col == 0 and i > 0:
            row_offset += 1
        if col == 0 and (y - row_offset * (CELL_H + GAP) - CELL_H) < 1.7*cm:
            y = new_page()
            row_offset = 0
        cell_y = y - row_offset * (CELL_H + GAP)
        x      = col_x[col]
        pts    = float(r.cluster_points)
        sc, bg = _score_col_bg(pts)

        p.setFillColor(bg)
        p.roundRect(x, cell_y - CELL_H, COL_W - 0.1*cm, CELL_H, 4, fill=1, stroke=0)
        p.setFillColor(sc)
        p.rect(x, cell_y - CELL_H, 0.22*cm, CELL_H, fill=1, stroke=0)
        knum  = r.cluster.kuccps_number if r.cluster else '?'
        cname = (r.cluster.name if r.cluster else 'Unknown')[:30]
        p.setFillColor(NAVY)
        p.setFont("Helvetica-Bold", 7.5)
        p.drawString(x + 0.38*cm, cell_y - 0.32*cm, f"Cluster {knum}")
        p.setFillColor(SLATE)
        p.setFont("Helvetica", 6.8)
        p.drawString(x + 0.38*cm, cell_y - 0.63*cm, cname)
        p.setFillColor(sc)
        p.roundRect(x + COL_W - 2.6*cm, cell_y - 0.88*cm, 2.3*cm, 0.72*cm, 4, fill=1, stroke=0)
        p.setFillColor(WHITE)
        p.setFont("Helvetica-Bold", 8.5)
        p.drawCentredString(x + COL_W - 1.45*cm, cell_y - 0.55*cm, f"{pts:.1f} / 48")

    # ── PAGE 2+: Eligible courses ─────────────────────────────────────────────
    y = new_page()

    p.setFillColor(NAVY)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(1.5*cm, y, "ELIGIBLE DEGREE COURSES")
    p.setFillColor(SLATE)
    p.setFont("Helvetica", 7.5)
    p.drawString(1.5*cm, y - 0.4*cm,
        f"{len(eligible)} eligible  |  {len(nearly)} nearly there (within 5 pts)  |  www.careernext.co.ke")
    y -= 0.9*cm

    def _draw_course_section(title, accent, courses, section_y):
        """Draw one section (Eligible or Nearly There) and return updated y."""
        if not courses:
            return section_y

        # Section banner
        p.setFillColor(accent)
        p.rect(1.5*cm, section_y - 0.55*cm, W - 3.0*cm, 0.55*cm, fill=1, stroke=0)
        p.setFillColor(WHITE)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(1.7*cm, section_y - 0.36*cm,
            f"{title}  ({len(courses)} courses)")
        section_y -= 0.82*cm

        # Column headers
        p.setFillColor(SLATE)
        p.setFont("Helvetica-Bold", 7)
        p.drawString(1.7*cm,  section_y, "COURSE NAME")
        p.drawString(9.5*cm,  section_y, "CLUSTER")
        p.drawString(13.5*cm, section_y, "CUTOFF")
        p.drawString(15.5*cm, section_y, "YOUR PTS")
        p.drawString(17.5*cm, section_y, "GAP")
        section_y -= 0.1*cm
        p.setStrokeColor(rc.HexColor("#cbd5e1"))
        p.line(1.5*cm, section_y, W - 1.5*cm, section_y)
        section_y -= 0.42*cm

        for item in courses:
            if section_y < 3.0*cm:
                section_y = new_page()
                section_y -= 0.3*cm

            course     = item['course']
            gap        = item['gap']
            cluster_lbl = (
                f"C{course.cluster.kuccps_number} — {course.cluster.name[:16]}"
                if course.cluster else "—"
            )
            insts = item.get('institutions', [])
            inst_str = ", ".join(i.name[:18] for i in insts[:3])
            if len(insts) > 3:
                inst_str += f" +{len(insts) - 3} more"

            p.setFillColor(rc.black)
            p.setFont("Helvetica", 7.5)
            p.drawString(1.7*cm,  section_y, course.name[:52])
            p.drawString(9.5*cm,  section_y, cluster_lbl[:26])
            p.drawString(13.5*cm, section_y, f"{item['cutoff']:.1f}")
            p.drawString(15.5*cm, section_y, f"{item['user_points']:.1f}")
            gap_col = EMERALD if gap >= 0 else AMBER
            p.setFillColor(gap_col)
            p.setFont("Helvetica-Bold", 7.5)
            p.drawString(17.5*cm, section_y, f"{'+'if gap>=0 else ''}{gap:.1f}")
            p.setFillColor(SLATE)
            p.setFont("Helvetica", 6.5)
            p.drawString(1.7*cm, section_y - 0.3*cm, inst_str[:80])
            section_y -= 0.72*cm

        return section_y - 0.3*cm

    if eligible:
        y = _draw_course_section("ELIGIBLE — You Qualify", EMERALD, eligible, y)

    if nearly:
        if y < 4.0*cm:
            y = new_page()
        else:
            y -= 0.4*cm
        y = _draw_course_section("NEARLY THERE — Within 5 pts of Cutoff", AMBER, nearly, y)

    if not eligible and not nearly:
        p.setFillColor(SLATE)
        p.setFont("Helvetica", 9)
        p.drawString(1.5*cm, y, "No matching degree courses found based on 2024 cutoff data.")

    # ── Next steps ────────────────────────────────────────────────────────────
    if y < 6.5*cm:
        y = new_page()
    else:
        y -= 0.5*cm
        p.setFillColor(TEAL)
        p.rect(1.5*cm, y, W - 3.0*cm, 0.06*cm, fill=1, stroke=0)
        y -= 0.7*cm

    p.setFillColor(NAVY)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(1.5*cm, y, "WHAT TO DO NEXT")
    y -= 0.6*cm

    steps = [
        ("1", "Discover all courses you qualify for",
         "Use our engine at www.careernext.co.ke — explore every course and institution that matches your scores."),
        ("2", "Save your shortlist",
         "Log in to careernext.co.ke — save your top courses and track your applications in one place."),
        ("3", "Apply during the window",
         "The KUCCPS application window typically opens in May/June. Watch the official portal at kuccps.net."),
        ("4", "Get mentorship",
         "Book a session with a university student or professional at www.careernext.co.ke/mentorship/"),
    ]

    for num, title, desc in steps:
        if y < 3.0*cm:
            y = new_page()
        p.setFillColor(NAVY)
        p.roundRect(1.5*cm, y - 0.44*cm, 0.44*cm, 0.44*cm, 3, fill=1, stroke=0)
        p.setFillColor(WHITE)
        p.setFont("Helvetica-Bold", 9)
        p.drawCentredString(1.72*cm, y - 0.29*cm, num)
        p.setFillColor(NAVY)
        p.setFont("Helvetica-Bold", 8.5)
        p.drawString(2.2*cm, y - 0.18*cm, title)
        p.setFillColor(SLATE)
        p.setFont("Helvetica", 8)
        p.drawString(2.2*cm, y - 0.42*cm, desc[:88])
        y -= 0.76*cm

    p.save()
    return response


# =====================================================
# ELIGIBLE COURSES VIEW
# =====================================================
def eligible_courses_view(request):
    import logging
    from .eligibility import (
        get_eligible_courses, get_eligible_courses_from_map,
        get_eligible_courses_by_mean_grade, COURSE_TYPE_MAP,
    )
    from courses.models import CourseType
    from django.core.cache import cache

    _log = logging.getLogger(__name__)
    is_guest = not request.user.is_authenticated

    # Determine which pathway to show — prefer career engine session, default to Degree
    career_pathway = request.session.get('career_pathway', 'Degree')
    is_degree = (career_pathway == 'Degree')

    if is_degree:
        # ── Degree path: cluster-point-based eligibility ──────────────────────
        if is_guest:
            cluster_map = request.session.get('guest_cluster_map')
            total_points = request.session.get('guest_calc', {}).get('total_points')
            if not cluster_map:
                messages.info(request, "Enter your KCSE results first to see your eligible courses.")
                return redirect("clusterpoints:calculator")
            cache_key = f"elig_guest_{request.session.session_key}"
            all_results = cache.get(cache_key)
            if all_results is None:
                try:
                    all_results = get_eligible_courses_from_map(cluster_map)
                    cache.set(cache_key, all_results, 600)
                except Exception as exc:
                    _log.error("eligible_courses_from_map failed for guest session=%s: %s",
                               request.session.session_key, exc, exc_info=True)
                    messages.warning(request, "We had trouble loading your eligible courses. Please try again in a moment.")
                    return redirect("clusterpoints:calculator")
            kcse_result = None
            saved_ids = []
        else:
            kcse_result = UserKCSEResult.objects.filter(user=request.user).order_by("-created_at").first()
            total_points = kcse_result.total_points if kcse_result else None
            if not kcse_result:
                messages.info(request, "Enter your KCSE results first to see your eligible courses.")
                return redirect("clusterpoints:calculator")
            cache_key = f"elig_user_{request.user.pk}_{kcse_result.pk}"
            all_results = cache.get(cache_key)
            if all_results is None:
                try:
                    all_results = get_eligible_courses(request.user, kcse_result)
                    cache.set(cache_key, all_results, 600)
                except Exception as exc:
                    _log.error("get_eligible_courses failed for user=%s kcse=%s: %s",
                               request.user.pk, kcse_result.pk, exc, exc_info=True)
                    messages.warning(request, "We had trouble loading your eligible courses. Please try again in a moment.")
                    return redirect("clusterpoints:calculator")
            from accounts.models import SavedCourse
            saved_ids = list(SavedCourse.objects.filter(user=request.user).values_list('course_id', flat=True))

        course_types = CourseType.objects.filter(name__iexact='Degree')

    else:
        # ── Non-degree path: mean-grade-based eligibility ─────────────────────
        mean_grade = request.session.get('career_mean_grade', '')

        # Fall back to computing from cluster calculator total_points
        if not mean_grade:
            if is_guest:
                _tp = request.session.get('guest_calc', {}).get('total_points')
            else:
                _kcse = UserKCSEResult.objects.filter(user=request.user).order_by("-created_at").first()
                _tp = _kcse.total_points if _kcse else None
            mean_grade = _mean_grade(_tp) if _tp else ''

        if not mean_grade:
            messages.info(request, "Enter your KCSE results first to see your eligible courses.")
            return redirect("clusterpoints:calculator")

        kcse_result = None if is_guest else UserKCSEResult.objects.filter(user=request.user).order_by("-created_at").first()
        total_points = kcse_result.total_points if kcse_result else None

        cache_key = f"elig_nd_{career_pathway}_{mean_grade}_{'g' if is_guest else request.user.pk}"
        all_results = cache.get(cache_key)
        if all_results is None:
            try:
                all_results = get_eligible_courses_by_mean_grade(career_pathway, mean_grade)
                cache.set(cache_key, all_results, 600)
            except Exception as exc:
                _log.error("get_eligible_courses_by_mean_grade failed pathway=%s grade=%s: %s",
                           career_pathway, mean_grade, exc, exc_info=True)
                messages.warning(request, "We had trouble loading your eligible courses. Please try again in a moment.")
                return redirect("clusterpoints:calculator")

        saved_ids = []
        if not is_guest:
            from accounts.models import SavedCourse
            saved_ids = list(SavedCourse.objects.filter(user=request.user).values_list('course_id', flat=True))

        type_names = COURSE_TYPE_MAP.get(career_pathway, [])
        course_types = CourseType.objects.filter(name__in=type_names) if type_names else CourseType.objects.none()

    # Filtering (in-memory on the cached list)
    status_filter = request.GET.get("status", "")
    type_filter = request.GET.get("type", "")
    query = request.GET.get("q", "")

    filtered = all_results
    if status_filter:
        filtered = [r for r in filtered if r["status"] == status_filter]
    if type_filter:
        filtered = [r for r in filtered if r["course"].course_type.slug == type_filter]
    if query:
        q_lower = query.lower()
        filtered = [r for r in filtered if q_lower in r["course"].name.lower()]

    eligible_count = sum(1 for r in all_results if r["status"] == "eligible")
    nearly_count   = sum(1 for r in all_results if r["status"] == "nearly")
    not_elig_count = sum(1 for r in all_results if r["status"] == "not_eligible")
    total_found    = eligible_count + nearly_count

    from payments.services import has_paid_for_feature, is_feature_enabled, price_for_feature
    _mn = _mean_grade(total_points)
    _is_locked = (
        not is_guest
        and is_feature_enabled('view_eligible_courses')
        and not has_paid_for_feature(request.user, 'view_eligible_courses')
    )
    _gate_items = [
        f"Every degree, diploma, KMTC, TVET & TTC course you qualify for right now",
        "Eligibility breakdown: Eligible ✓, Nearly There, and Worth Considering",
        "Minimum grade & cluster point requirements for each programme",
        "Institution details — type, location & contact info for each college",
        "Save any course to your personal shortlist with one tap",
        "Filter & search across all your matched courses instantly",
    ]

    return render(request, "clusterpoints/eligible_courses.html", {
        "results": filtered,
        "kcse_result": kcse_result,
        "total_points": total_points,
        "mean_grade": _mn,
        "eligible_count": eligible_count,
        "nearly_count": nearly_count,
        "not_eligible_count": not_elig_count,
        "status_filter": status_filter,
        "type_filter": type_filter,
        "query": query,
        "course_types": course_types,
        "saved_ids": saved_ids,
        "is_guest": is_guest,
        "is_locked": _is_locked,
        "total_count": total_found,
        "gate_feature": "view_eligible_courses",
        "gate_price": price_for_feature("view_eligible_courses"),
        "gate_items": _gate_items,
        "gate_subtext": f"Based on your KCSE score of {total_points} pts ({_mn}) — here's what you qualify for.",
        "active_pathway": career_pathway,
        "is_degree_pathway": is_degree,
    })


# =====================================================
# RECALCULATE VIEW
# =====================================================
@login_required
def recalculate_view(request):
    """
    Reset the submission lock so the user can enter new grades.
    The payment gate will reappear after they submit new grades —
    they need to pay again to see the new results.
    Old grades stay pre-filled in the form so nothing is lost until
    they deliberately submit new ones.
    """
    if request.method != 'POST':
        return redirect('clusterpoints:calculator')
    from career.models import CareerSubmission
    CareerSubmission.objects.filter(
        user=request.user, feature=CareerSubmission.FEATURE_CALCULATOR
    ).delete()
    messages.info(request, "Grade lock removed. Enter your new grades and pay to see results.")
    return redirect('clusterpoints:calculator')


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


# =====================================================
# SHARE CALCULATOR RESULTS
# =====================================================
@login_required
def share_calculator_create(request):
    """AJAX POST — snapshot calculator results into a SharedResult; return share URL."""
    from django.http import JsonResponse
    from career.models import SharedResult

    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    try:
        import json
        body = json.loads(request.body)
        mean_grade      = body.get('mean_grade', '')
        aggregate       = int(body.get('aggregate', 0) or 0)
        cluster_points  = body.get('cluster_points', {})  # {"kuccps_num": score, ...}
        cluster_names   = body.get('cluster_names', {})   # {"kuccps_num": "name", ...}

        if not cluster_points:
            return JsonResponse({'ok': False, 'error': 'No cluster results to share.'}, status=400)

        scores = {k: float(v) for k, v in cluster_points.items() if float(v or 0) > 0}
        best_score = max(scores.values(), default=0)

        top5 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
        top_courses_json = [
            {
                'cluster_num':  k,
                'cluster_name': cluster_names.get(k, f'Cluster {k}'),
                'score':        str(round(v, 1)),
                'mean_grade':   mean_grade,
                'aggregate':    str(aggregate),
            }
            for k, v in top5
        ]

        sr = SharedResult.objects.create(
            user=request.user,
            pathway='Calculator',
            cluster_points_json={k: float(v) for k, v in cluster_points.items()},
            cluster_pts_single=round(best_score, 1),
            total_matches=aggregate,
            top_courses_json=top_courses_json,
        )
        share_url = request.build_absolute_uri(sr.get_absolute_url())
        try:
            from analytics.utils import log_event as _log_event
            _log_event(request, 'calculator_share', {'pathway': 'Calculator'})
        except Exception:
            pass
        return JsonResponse({'ok': True, 'url': share_url})
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error('share_calculator_create error: %s', exc, exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Failed to create share link. Please try again.'}, status=500)