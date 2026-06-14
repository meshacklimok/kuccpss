# career/engine.py

from typing import Dict, List, Tuple
from .models import StudentCourseMatch, Course, TVETCourse, KMTCourse, TTCCourse

def career_guidance_engine(kcse_grades: Dict[str, str], pathway: str, tvet_category=None) -> Tuple[List[StudentCourseMatch], dict]:
    """
    A dummy career guidance engine.
    Replace this with your real logic.
    Returns:
        matches: List of StudentCourseMatch instances
        ai: dictionary with AI recommendations or insights
    """
    matches: List[StudentCourseMatch] = []
    ai: dict = {"message": "This is a placeholder AI recommendation."}

    # Example logic: fetch courses based on pathway
    if pathway == "Degree":
        courses = Course.objects.all()[:5]  # top 5 for now
        for course in courses:
            match = StudentCourseMatch(course=course, match_score=50, admission_chance="Medium")
            matches.append(match)
    elif pathway == "TVET" and tvet_category:
        courses = TVETCourse.objects.filter(category__name=tvet_category)[:5]
        for course in courses:
            match = StudentCourseMatch(tvet_course=course, match_score=50, admission_chance="Medium")
            matches.append(match)
    # Add similar logic for KMTC, TTC, etc.

    return matches, ai