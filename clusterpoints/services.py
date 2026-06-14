# clusterpoints/services.py
from math import sqrt
from django.db import transaction
from .models import Cluster, ClusterCalculationResult, UserKCSEResult, SubjectResult, Subject


def calculate_all_clusters(kcse_result: UserKCSEResult):
    """
    Calculate cluster points for all 20 master calculation clusters.

    Algorithm:
    1. Aggregate total = Mathematics + best(English/Kiswahili) + next 5 best subjects (max 84)
    2. For each cluster, select exactly 4 subjects using priority-ordered SubjectGroup slots:
       - Walk slots in priority order (1→4)
       - From each slot's subject list, pick the highest-scoring subject not yet used
       - Never repeat a subject across slots
    3. cluster_points = 48 × sqrt( (core_total/48) × (aggregate_total/84) )
    """

    if not kcse_result.pk:
        raise ValueError("KCSE result must be saved before calculating clusters.")

    # Map subject name → points for this student
    points_dict = {sr.subject.name: sr.points for sr in SubjectResult.objects.filter(kcse_result=kcse_result)}

    # ── Step 1: Aggregate total (max 84) ──────────────────────────
    working = points_dict.copy()

    agg_subjects = []

    # Mathematics (compulsory)
    if 'Mathematics' in working:
        agg_subjects.append(working.pop('Mathematics'))

    # Best language (non-best language returns to pool for step 3)
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
    # Only process clusters that have SubjectGroups defined (the 20 master clusters)
    clusters = (
        Cluster.objects
        .filter(subject_groups__isnull=False)
        .distinct()
        .prefetch_related('subject_groups__subjects')
    )

    cluster_results = []

    with transaction.atomic():
        for cluster in clusters:
            slots = cluster.subject_groups.prefetch_related('subjects').order_by('priority')

            used_names = set()
            core_points = []
            subjects_used = []
            any_slot_unfilled = False

            for slot in slots:
                if len(core_points) >= 4:
                    break

                # Best subject from this slot not already used AND actually taken by student
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
                    # Student took none of the required subjects in this slot
                    core_points.append(0)
                    any_slot_unfilled = True

            # Pad to 4 if fewer slots defined
            while len(core_points) < 4:
                core_points.append(0)

            raw_core_total = sum(core_points[:4])

            # If any required slot had no qualifying subject, the cluster is 0
            if any_slot_unfilled or raw_core_total == 0 or aggregate_total == 0:
                weighted = 0.0
            else:
                weighted = 48 * sqrt((raw_core_total / 48) * (aggregate_total / 84))
                weighted = round(min(weighted, 48.0), 3)

            # Persist result
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

            # Track which subjects were used
            subj_objs = Subject.objects.filter(name__in=subjects_used)
            result.subjects_used.set(subj_objs)

            cluster_results.append(result)

    # Sort by cluster number (101→120) so results display in the defined order:
    # 1=Law, 2=Business, 3=Comms, 4=Geosciences, 5=Engineering … 13=Medicine … 18=Music … 20=Religious
    cluster_results.sort(key=lambda r: r.cluster.number or 0)
    return cluster_results
