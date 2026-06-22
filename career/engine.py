# career/engine.py
from typing import Dict, List, Tuple
from .models import (
    StudentCourseMatch,
    match_degree_courses,
    match_diploma_courses,
    match_tvet_courses,
    match_kmtc_courses,
    match_ttc_courses,
    generate_ai_recommendation,
)


def career_guidance_engine(
    kcse_grades: Dict[str, str],
    pathway: str,
    tvet_category: str = None,
) -> Tuple[List[StudentCourseMatch], object]:
    """
    pathway: "Degree", "Diploma", "KMTC", "TVET", "TTC"
    kcse_grades: {subject_name: grade_letter}  e.g. {"Mathematics": "A", "Physics": "B+"}

    Degree path uses midpoint-marks cluster points formula (clusterpoints/services._weighted_cp).
    All other paths use mean grade comparison.
    """
    if pathway == "Degree":
        matches = match_degree_courses(kcse_grades)
    elif pathway == "Diploma":
        matches = match_diploma_courses(kcse_grades)
    elif pathway == "KMTC":
        matches = match_kmtc_courses(kcse_grades)
    elif pathway == "TVET":
        if not tvet_category:
            raise ValueError("TVET pathway requires a category (Certificate, Diploma, Artisan)")
        matches = match_tvet_courses(kcse_grades, tvet_category)
    elif pathway == "TTC":
        matches = match_ttc_courses(kcse_grades)
    else:
        raise ValueError(f"Invalid pathway: {pathway}")

    ai = generate_ai_recommendation(matches)
    return matches, ai
