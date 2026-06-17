# clusterpoints/services.py
from math import sqrt
from types import SimpleNamespace
from django.db import transaction
from .models import Cluster, ClusterCalculationResult, UserKCSEResult, SubjectResult, Subject

# KUCCPS uses raw subject marks internally (not the 1-12 grade points).
# Scale: grade_points × 7  (A=84, A-=77, B+=70 … E=7)
# Formula: 48 × sqrt((core_marks / 400) × (aggregate / 84))
GRADE_PTS_TO_MARKS = {p: p * 7 for p in range(1, 13)}


def calculate_clusters_anonymous(named_points: dict) -> list:
    """
    Same algorithm as calculate_all_clusters but runs entirely in memory —
    no DB writes. Accepts {subject_name: points} and returns SimpleNamespace
    objects whose attributes match the ClusterCalculationResult API used in
    the calculator template (cluster, cluster_points, pk=None).
    """
    working = named_points.copy()
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
    aggregate_total = sum(agg)

    clusters = (
        Cluster.objects
        .filter(subject_groups__isnull=False)
        .distinct()
        .prefetch_related('subject_groups__subjects')
    )

    results = []
    for cluster in clusters:
        slots = sorted(cluster.subject_groups.all(), key=lambda sg: sg.priority)
        used = set()
        core = []
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
                used.add(best_name)
            else:
                core.append(0)
                any_unfilled = True

        while len(core) < 4:
            core.append(0)

        raw_core = sum(core[:4])
        if any_unfilled or raw_core == 0 or aggregate_total == 0:
            weighted = 0.0
        else:
            core_marks = sum(GRADE_PTS_TO_MARKS.get(p, p * 7) for p in core[:4])
            weighted = round(min(48 * sqrt((core_marks / 400) * (aggregate_total / 84)), 48.0), 3)

        results.append(SimpleNamespace(
            cluster=cluster,
            cluster_points=weighted,
            core_subject_total=raw_core,
            aggregate_total=aggregate_total,
            pk=None,
        ))

    results.sort(key=lambda r: r.cluster.number or 0)
    return results


def calculate_all_clusters(kcse_result: UserKCSEResult):
    """
    Calculate cluster points for all 20 master calculation clusters.

    Algorithm:
    1. Aggregate total = Mathematics + best(English/Kiswahili) + next 5 best subjects (max 84)
    2. For each cluster, select exactly 4 subjects using priority-ordered SubjectGroup slots:
       - Walk slots in priority order (1→4)
       - From each slot's subject list, pick the highest-scoring subject not yet used
       - Never repeat a subject across slots
    3. cluster_points = 48 × sqrt((core_marks / 400) × (aggregate / 84))
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
    working = points_dict.copy()

    agg_subjects = []

    # Mathematics (compulsory)
    if 'Mathematics' in working:
        agg_subjects.append(working.pop('Mathematics'))

    # Best language (non-best language returns to pool)
    lang_scores = {lang: working.pop(lang) for lang in ['English', 'Kiswahili'] if lang in working}
    if lang_scores:
        best_lang = max(lang_scores, key=lambda k: lang_scores[k])
        agg_subjects.append(lang_scores[best_lang])
        for lang, pts in lang_scores.items():
            if lang != best_lang:
                working[lang] = pts

    # Next 5 best remaining
    agg_subjects += sorted(working.values(), reverse=True)[:5]

    aggregate_total = sum(agg_subjects)

    # ── Step 2: Calculate cluster points ──────────────────────────
    clusters = (
        Cluster.objects
        .filter(subject_groups__isnull=False)
        .distinct()
        .prefetch_related('subject_groups__subjects')
    )

    cluster_results = []

    with transaction.atomic():
        for cluster in clusters:
            slots = sorted(cluster.subject_groups.all(), key=lambda sg: sg.priority)

            used_names = set()
            core_points = []
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
                core_marks = sum(GRADE_PTS_TO_MARKS.get(p, p * 7) for p in core_points[:4])
                weighted = round(min(48 * sqrt((core_marks / 400) * (aggregate_total / 84)), 48.0), 3)

            result, _ = ClusterCalculationResult.objects.update_or_create(
                user=kcse_result.user,
                kcse_result=kcse_result,
                cluster=cluster,
                defaults={
                    'cluster_points':      weighted,
                    'core_subject_total':  raw_core_total,
                    'aggregate_total':     aggregate_total,
                    'weighted_calculation': weighted,
                }
            )

            subj_objs = [all_subjects_by_name[n] for n in subjects_used if n in all_subjects_by_name]
            result.subjects_used.set(subj_objs)

            cluster_results.append(result)

    cluster_results.sort(key=lambda r: r.cluster.number or 0)
    return cluster_results
