from .models import ClusterCalculationResult, UserKCSEResult

CURRENT_YEAR = "2024"
NEARLY_ELIGIBLE_GAP = 5.0


def _build_results_from_cluster_map(cluster_map: dict) -> list:
    """
    Shared logic for both authenticated and guest eligible-course lookups.
    cluster_map: {kuccps_number (int): cluster_points (float)}
    """
    from courses.models import CourseOffering

    offerings = (
        CourseOffering.objects
        .filter(cutoff_points__isnull=False, course__cluster__isnull=False)
        .select_related(
            "course", "course__cluster",
            "course__course_type", "course__category",
            "institution",
        )
    )

    course_data: dict = {}
    for offering in offerings:
        if not offering.cutoff_points:
            continue
        cp = offering.cutoff_points
        cutoff_val = cp.get(CURRENT_YEAR) or cp.get(
            max((k for k in cp if cp[k] is not None), default=None)
        )
        if cutoff_val is None:
            continue

        cutoff_val = float(cutoff_val)
        course = offering.course
        knum = course.cluster.kuccps_number if course.cluster else None
        if knum is None:
            continue

        user_pts = cluster_map.get(knum, 0.0)
        cid = course.pk

        if cid not in course_data:
            course_data[cid] = {
                "course": course,
                "min_cutoff": cutoff_val,
                "user_pts": user_pts,
                "institutions": [offering.institution],
            }
        else:
            if cutoff_val < course_data[cid]["min_cutoff"]:
                course_data[cid]["min_cutoff"] = cutoff_val
            if len(course_data[cid]["institutions"]) < 5:
                course_data[cid]["institutions"].append(offering.institution)

    results = []
    for data in course_data.values():
        cutoff = data["min_cutoff"]
        user_pts = data["user_pts"]
        gap = round(user_pts - cutoff, 2)
        if gap >= 0:
            status = "eligible"
        elif abs(gap) <= NEARLY_ELIGIBLE_GAP:
            status = "nearly"
        else:
            status = "not_eligible"
        results.append({
            "course": data["course"],
            "status": status,
            "user_points": round(user_pts, 2),
            "cutoff": cutoff,
            "gap": gap,
            "institutions": data["institutions"],
        })

    order = {"eligible": 0, "nearly": 1, "not_eligible": 2}
    results.sort(key=lambda x: (order[x["status"]], -x["gap"]))
    return results


def get_eligible_courses_from_map(cluster_map: dict) -> list:
    """Guest / session-based eligible courses — no DB user required."""
    return _build_results_from_cluster_map(cluster_map)


def get_eligible_courses(user, kcse_result: UserKCSEResult):
    """Build cluster_map from DB and delegate to shared logic."""
    cluster_map: dict[int, float] = {}
    for r in ClusterCalculationResult.objects.filter(
        kcse_result=kcse_result
    ).select_related("cluster"):
        knum = r.cluster.kuccps_number if r.cluster else None
        if knum is not None:
            cluster_map[knum] = float(r.cluster_points)
    return _build_results_from_cluster_map(cluster_map)


