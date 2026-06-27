from .models import ClusterCalculationResult, UserKCSEResult

CURRENT_YEAR = "2024"
NEARLY_ELIGIBLE_GAP = 5.0
NEARLY_ELIGIBLE_GRADE_GAP = 2  # grade points below minimum still shown as "nearly"

GRADE_POINTS = {
    'A': 12, 'A-': 11, 'B+': 10, 'B': 9, 'B-': 8,
    'C+': 7, 'C': 6, 'C-': 5, 'D+': 4, 'D': 3, 'D-': 2, 'E': 1,
}

PATHWAY_DEFAULT_MIN_GRADE = {
    'Diploma':      'C-',
    'Certificate':  'D+',
    'KMTC':         'C',
    'TTC':          'C-',
    'Artisan':      'D',
    'Short Course': 'E',
}

COURSE_TYPE_MAP = {
    'Diploma':      ['TVET Diploma (Level 6)'],
    'Certificate':  ['TVET Certificate (Level 5)'],
    'KMTC':         ['KMTC'],
    'TTC':          ['TTC'],
    'Artisan':      ['TVET Artisan Certificate (Level 4)', 'TVET Craft Certificate (Level 3)'],
    'Short Course': ['TVET Short Course', 'TVET Trade Test', 'TVET Professional', 'TVET Proficiency'],
}


def _build_results_from_cluster_map(cluster_map: dict) -> list:
    """
    Shared logic for both authenticated and guest eligible-course lookups.
    cluster_map: {kuccps_number (int): cluster_points (float)}
    """
    from courses.models import CourseOffering

    offerings = (
        CourseOffering.objects
        .filter(
            cutoff_points__isnull=False,
            course__cluster__isnull=False,
            course__course_type__name__iexact='Degree',
        )
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


def get_eligible_courses_by_mean_grade(pathway: str, mean_grade: str) -> list:
    """
    Eligibility for non-degree pathways (Diploma, KMTC, TTC, Certificate, etc.)
    based on mean grade comparison against course minimum_mean_grade.
    """
    from courses.models import CourseOffering

    student_pts = GRADE_POINTS.get(mean_grade, 0)
    type_names = COURSE_TYPE_MAP.get(pathway, [])
    default_min = PATHWAY_DEFAULT_MIN_GRADE.get(pathway, 'E')

    if not type_names or not mean_grade:
        return []

    offerings = (
        CourseOffering.objects
        .filter(course__course_type__name__in=type_names)
        .select_related(
            'course', 'course__course_type', 'course__category', 'course__cluster',
            'institution',
        )
    )

    course_data: dict = {}
    for offering in offerings:
        course = offering.course
        cid = course.pk
        min_grade = (course.minimum_mean_grade or '').strip() or default_min
        min_pts = GRADE_POINTS.get(min_grade, 0)

        if cid not in course_data:
            course_data[cid] = {
                'course': course,
                'min_grade': min_grade,
                'min_pts': min_pts,
                'institutions': [offering.institution],
            }
        else:
            if min_pts < course_data[cid]['min_pts']:
                course_data[cid]['min_grade'] = min_grade
                course_data[cid]['min_pts'] = min_pts
            if len(course_data[cid]['institutions']) < 5:
                course_data[cid]['institutions'].append(offering.institution)

    results = []
    for data in course_data.values():
        diff = student_pts - data['min_pts']
        if diff >= 0:
            status = 'eligible'
        elif abs(diff) <= NEARLY_ELIGIBLE_GRADE_GAP:
            status = 'nearly'
        else:
            status = 'not_eligible'

        results.append({
            'course': data['course'],
            'status': status,
            'user_points': mean_grade,
            'cutoff': data['min_grade'],
            'gap': diff,
            'institutions': data['institutions'],
            'is_grade': True,
        })

    order = {'eligible': 0, 'nearly': 1, 'not_eligible': 2}
    results.sort(key=lambda x: (order[x['status']], -x['gap']))
    return results


