from courses.models import Course
from .models import ClusterCalculationResult, UserKCSEResult

CURRENT_YEAR = "2024"
NEARLY_ELIGIBLE_GAP = 5.0


def get_eligible_courses(user, kcse_result: UserKCSEResult):
    """
    Compare user's cluster points against course cutoff points.

    Returns a list of dicts:
        {
            "course": Course,
            "status": "eligible" | "nearly" | "not_eligible",
            "user_points": float,
            "cutoff": float,
            "gap": float,          # positive = above cutoff
            "institutions": [...],
        }
    """
    # Build a map of cluster_id → user's cluster_points
    cluster_map = {
        r.cluster_id: r.cluster_points
        for r in ClusterCalculationResult.objects.filter(
            kcse_result=kcse_result
        ).select_related("cluster")
    }

    courses = (
        Course.objects
        .filter(cluster__isnull=False)
        .select_related("cluster", "course_type", "category")
        .prefetch_related("institutions")
    )

    results = []
    for course in courses:
        if not course.cutoff_points:
            continue

        # Pick the most recent available cutoff year
        cutoff = (
            course.cutoff_points.get(CURRENT_YEAR)
            or course.cutoff_points.get(
                max((k for k in course.cutoff_points if course.cutoff_points[k] is not None),
                    default=None)
            )
        )
        if cutoff is None:
            continue

        cutoff = float(cutoff)
        user_pts = float(cluster_map.get(course.cluster_id, 0.0))
        gap = round(user_pts - cutoff, 2)

        if gap >= 0:
            status = "eligible"
        elif abs(gap) <= NEARLY_ELIGIBLE_GAP:
            status = "nearly"
        else:
            status = "not_eligible"

        results.append({
            "course": course,
            "status": status,
            "user_points": round(user_pts, 2),
            "cutoff": cutoff,
            "gap": gap,
            "institutions": list(course.institutions.all()),
        })

    # Sort: eligible first, then nearly, then not_eligible; within each, highest gap first
    order = {"eligible": 0, "nearly": 1, "not_eligible": 2}
    results.sort(key=lambda x: (order[x["status"]], -x["gap"]))
    return results
