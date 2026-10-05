# clusterpoints/services.py
from math import sqrt
from types import SimpleNamespace
from django.db import transaction
from django.utils import timezone
from clusters.models import Cluster, Subject
from .models import ClusterCalculationResult, UserKCSEResult, SubjectResult

# Grade points (1-12) → midpoint raw marks out of 100
# Based on KCSE grade boundaries: A=80-100 (mid 90), A-=75-79 (mid 77), B+=70-74 (mid 72.5), etc.
GRADE_MIDPOINT_MARKS = {
    12: 90.2,   # A
    11: 77.5,   # A-
    10: 71.0,   # B+
    9:  66.0,   # B
    8:  60.0,   # B-
    7:  56.0,   # C+
    6:  50.0,   # C
    5:  46.0,   # C-
    4:  40.0,   # D+
    3:  36.0,   # D
    2:  31.0,   # D-
    1:  14.0,   # E
}


def _weighted_cp(core_pts: list[int], aggregate_total: int) -> float:
    """48 × sqrt((core_midpoint_marks / 400) × (aggregate / 84)), capped at 48."""
    core_marks = sum(GRADE_MIDPOINT_MARKS.get(p, p * 7.5) for p in core_pts[:4])
    return round(min(48 * sqrt((core_marks / 400) * (aggregate_total / 84)), 48.0), 3)


def compute_aggregate_total(named_points: dict[str, int]) -> int:
    """
    KCSE aggregate (max 84): Mathematics + best(English, Kiswahili) + next 5 best
    subjects. The non-best language returns to the subject pool (not discarded)
    before picking the top 5. See CLAUDE.md rule #2 — this is the single canonical
    implementation; every other call site (clusterpoints/models.py, clusterpoints/views.py,
    career/models.py) imports this function rather than reimplementing it.
    """
    return sum(p for _, p in aggregate_subjects(named_points))


def aggregate_subjects(named_points: dict[str, int]) -> list[tuple[str, int]]:
    """The (subject, points) pairs that make up the aggregate, in selection order."""
    working = named_points.copy()
    agg = []
    if 'Mathematics' in working:
        agg.append(('Mathematics', working.pop('Mathematics')))
    langs = {l: working.pop(l) for l in ['English', 'Kiswahili'] if l in working}
    if langs:
        best = max(langs, key=lambda k: langs[k])
        agg.append((best, langs[best]))
        for l, p in langs.items():
            if l != best:
                working[l] = p
    agg += sorted(working.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return agg


def calculate_clusters_anonymous(named_points: dict[str, int]) -> list:
    """
    Same algorithm as calculate_all_clusters but runs entirely in memory —
    no DB writes. Accepts {subject_name: points} and returns SimpleNamespace
    objects whose attributes match the ClusterCalculationResult API used in
    the calculator template (cluster, cluster_points, pk=None).
    """
    aggregate_total = compute_aggregate_total(named_points)

    clusters = (
        Cluster.objects.kuccps()
        .prefetch_related('subject_groups__subjects')
    )

    results = []
    for cluster in clusters:
        slots = sorted(cluster.subject_groups.all(), key=lambda sg: sg.priority)  # type: ignore[attr-defined]
        used = set()
        core: list[int] = []
        core_subjects: list[tuple[str, int] | None] = []
        any_unfilled = False

        for slot in slots:
            if len(core) >= 4:
                break
            best_name, best_pts = None, -1
            for subj in slot.subjects.all():
                if subj.name not in used and subj.name in named_points:
                    pts = named_points[subj.name]
                    if pts > best_pts:
                        best_pts, best_name = pts, subj.name
            if best_name:
                core.append(best_pts)
                core_subjects.append((best_name, best_pts))
                used.add(best_name)
            else:
                core.append(0)
                core_subjects.append(None)
                any_unfilled = True

        while len(core) < 4:
            core.append(0)

        raw_core = sum(core[:4])
        if any_unfilled or raw_core == 0 or aggregate_total == 0:
            weighted = 0.0
        else:
            weighted = _weighted_cp(core[:4], aggregate_total)

        results.append(SimpleNamespace(
            cluster=cluster,
            cluster_points=weighted,
            core_subject_total=raw_core,
            core_subjects=core_subjects,
            aggregate_total=aggregate_total,
            pk=None,
        ))

    results.sort(key=lambda r: r.cluster.number or 0)
    return results


def calculate_all_clusters(kcse_result: UserKCSEResult):
    """
    Calculate cluster points for all 18 KUCCPS clusters (rows 101–118).

    Algorithm:
    1. Aggregate total = Mathematics + best(English/Kiswahili) + next 5 best subjects (max 84)
    2. For each cluster, select exactly 4 subjects using priority-ordered SubjectGroup slots:
       - Walk slots in priority order (1→4)
       - From each slot's subject list, pick the highest-scoring subject not yet used
       - Never repeat a subject across slots
    3. cluster_points = 48 × sqrt((core_midpoint_marks / 400) × (aggregate / 84))
    """

    if not kcse_result.pk:
        raise ValueError("KCSE result must be saved before calculating clusters.")

    # Map subject name → points for this student (select_related avoids N+1 per subject)
    points_dict = {
        sr.subject.name: sr.points
        for sr in SubjectResult.objects.filter(kcse_result=kcse_result).select_related('subject')
    }

    # Pre-load all Subject objects once so the M2M .set() inside the loop is 1 query, not 20
    all_subjects_by_name = {s.name: s for s in Subject.objects.all()}

    # ── Step 1: Aggregate total (max 84) ──────────────────────────
    aggregate_total = compute_aggregate_total(points_dict)

    # ── Step 2: Calculate cluster points ──────────────────────────
    clusters = (
        Cluster.objects.kuccps()
        .prefetch_related('subject_groups__subjects')
    )

    cluster_results = []

    # Upsert all 18 results in a handful of bulk queries instead of an
    # update_or_create + M2M .set() round-trip per cluster (~90 queries).
    existing = {
        r.cluster_id: r
        for r in ClusterCalculationResult.objects.filter(
            user=kcse_result.user, kcse_result=kcse_result,
        )
    }
    to_create, to_update, subjects_by_result = [], [], []
    now = timezone.now()

    with transaction.atomic():
        for cluster in clusters:
            slots = sorted(cluster.subject_groups.all(), key=lambda sg: sg.priority)  # type: ignore[attr-defined]

            used_names = set()
            core_points: list[int] = []
            subjects_used = []
            any_slot_unfilled = False

            for slot in slots:
                if len(core_points) >= 4:
                    break

                best_name = None
                best_pts = -1
                for subj in slot.subjects.all():
                    if subj.name not in used_names and subj.name in points_dict:
                        pts = points_dict[subj.name]
                        if pts > best_pts:
                            best_pts = pts
                            best_name = subj.name

                if best_name is not None:
                    core_points.append(best_pts)
                    used_names.add(best_name)
                    subjects_used.append(best_name)
                else:
                    core_points.append(0)
                    any_slot_unfilled = True

            while len(core_points) < 4:
                core_points.append(0)

            raw_core_total = sum(core_points[:4])

            if any_slot_unfilled or raw_core_total == 0 or aggregate_total == 0:
                weighted = 0.0
            else:
                weighted = _weighted_cp(core_points[:4], aggregate_total)

            result = existing.get(cluster.pk)
            if result is None:
                result = ClusterCalculationResult(user=kcse_result.user, kcse_result=kcse_result)
                to_create.append(result)
            else:
                to_update.append(result)
            result.cluster = cluster  # reuse loaded instance — avoids a lazy fetch in the sort below
            result.cluster_points = weighted
            result.core_subject_total = raw_core_total
            result.aggregate_total = aggregate_total
            result.weighted_calculation = weighted
            result.updated_at = now  # bulk_update skips auto_now

            subj_objs = [all_subjects_by_name[n] for n in subjects_used if n in all_subjects_by_name]
            subjects_by_result.append((result, subj_objs))

            cluster_results.append(result)

        if to_update:
            ClusterCalculationResult.objects.bulk_update(
                to_update,
                ['cluster_points', 'core_subject_total', 'aggregate_total',
                 'weighted_calculation', 'updated_at'],
            )
        if to_create:
            ClusterCalculationResult.objects.bulk_create(to_create)  # Postgres returns PKs

        Through = ClusterCalculationResult.subjects_used.through
        Through.objects.filter(
            clustercalculationresult_id__in=[r.pk for r in cluster_results]
        ).delete()
        Through.objects.bulk_create([
            Through(clustercalculationresult_id=r.pk, subject_id=s.pk)
            for r, subjs in subjects_by_result for s in subjs
        ])

    cluster_results.sort(key=lambda r: r.cluster.number or 0)
    return cluster_results
