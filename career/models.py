from django.db import models
from django.conf import settings
from typing import List, Dict

# =====================================================
# KCSE Subjects and Grades
# =====================================================
class KCSEGrade(models.Model):
    subject_name = models.CharField(max_length=50)
    grade = models.CharField(max_length=3)  # e.g., A, A-, B+, C

    def __str__(self):
        return f"{self.subject_name}: {self.grade}"


# =====================================================
# Course Categories
# =====================================================
class CourseCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)  
    # Degree, Diploma, Certificate, TVET, TTC, KMTC
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# =====================================================
# Universities
# =====================================================
class University(models.Model):
    name = models.CharField(max_length=150, unique=True)
    county = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# =====================================================
# Courses
# =====================================================

def get_default_course_category():
    category, created = CourseCategory.objects.get_or_create(name="Degree")
    return category.id
class Course(models.Model):
    name = models.CharField(max_length=150)
    category = models.ForeignKey(
        CourseCategory,
        on_delete=models.CASCADE,
        related_name="courses",
        default=get_default_course_category 
    )
    cluster_subjects = models.ManyToManyField('clusters.Subject', blank=True, related_name='career_courses')
    description = models.TextField(blank=True, null=True)
    recommended_fields = models.TextField(blank=True, null=True)
    career_paths = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.category.name})"


# =====================================================
# Course Cutoff Points (per university)
# =====================================================
class CourseCutoff(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="cutoffs")
    university = models.ForeignKey(University, on_delete=models.CASCADE, related_name="cutoffs")
    cutoff_points = models.FloatField()  # Cluster points for degree, mean grade for diploma/KMTC
    year = models.PositiveIntegerField(default=2026)

    def __str__(self):
        return f"{self.course.name} - {self.university.name} ({self.cutoff_points})"


# =====================================================
# Historical Cutoff Trends
# =====================================================
class CourseCutoffHistory(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="cutoff_history")
    university = models.ForeignKey(University, on_delete=models.CASCADE, related_name="cutoff_history")
    year = models.PositiveIntegerField()
    cutoff_points = models.FloatField()

    def __str__(self):
        return f"{self.course.name} - {self.university.name} ({self.year})"


# =====================================================
# TVET Categories
# =====================================================
class TVETCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)  # Certificate, Diploma, Artisan

    def __str__(self):
        return self.name


# =====================================================
# TVET Courses
# =====================================================
class TVETCourse(models.Model):
    name = models.CharField(max_length=150)
    category = models.ForeignKey(TVETCategory, on_delete=models.CASCADE, related_name="tvet_courses")
    min_mean_grade = models.CharField(max_length=3, blank=True, null=True)
    required_subjects = models.ManyToManyField('clusters.Subject', blank=True, related_name='tvet_courses')
    description = models.TextField(blank=True, null=True)
    career_paths = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.category.name})"


# =====================================================
# KMTC Courses and Campuses
# =====================================================
class KMTCampus(models.Model):
    name = models.CharField(max_length=150, unique=True)
    county = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name


class KMTCourse(models.Model):
    name = models.CharField(max_length=150)
    min_mean_grade = models.CharField(max_length=3)
    required_subjects = models.ManyToManyField('clusters.Subject', blank=True, related_name='kmt_courses')
    campuses = models.ManyToManyField(KMTCampus, blank=True)
    description = models.TextField(blank=True, null=True)
    career_paths = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# =====================================================
# TTC Courses and Colleges
# =====================================================
class TTCCollege(models.Model):
    name = models.CharField(max_length=150, unique=True)
    county = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name


class TTCCourse(models.Model):
    name = models.CharField(max_length=150)
    min_mean_grade = models.CharField(max_length=3)
    required_subjects = models.ManyToManyField('clusters.Subject', blank=True, related_name='ttc_courses')
    colleges = models.ManyToManyField(TTCCollege, blank=True)
    description = models.TextField(blank=True, null=True)
    career_paths = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# =====================================================
# Student Course Match (AI Engine Output)
# =====================================================
class StudentCourseMatch(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)
    tvet_course = models.ForeignKey(TVETCourse, on_delete=models.CASCADE, null=True, blank=True)
    kmc_course = models.ForeignKey(KMTCourse, on_delete=models.CASCADE, null=True, blank=True)
    ttc_course = models.ForeignKey(TTCCourse, on_delete=models.CASCADE, null=True, blank=True)
    university = models.ForeignKey(University, on_delete=models.SET_NULL, null=True, blank=True)
    admission_chance = models.CharField(max_length=50, blank=True, null=True)  # LOW, MEDIUM, HIGH, VERY HIGH
    match_score = models.FloatField(default=0)  # AI recommendation score
    recommended_by_ai = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        target_course = self.course or self.tvet_course or self.kmc_course or self.ttc_course
        return f"{target_course}"


# =====================================================
# AI Recommendations
# =====================================================
class AIRecommendation(models.Model):
    advice_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AI Advice ({self.created_at.strftime('%Y-%m-%d')})"


# =====================================================
# Career Insights (Job demand, salary, fields)
# =====================================================
class CareerInsight(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="career_insights", null=True, blank=True)
    tvet_course = models.ForeignKey(TVETCourse, on_delete=models.CASCADE, related_name="career_insights", null=True, blank=True)
    kmc_course = models.ForeignKey(KMTCourse, on_delete=models.CASCADE, related_name="career_insights", null=True, blank=True)
    ttc_course = models.ForeignKey(TTCCourse, on_delete=models.CASCADE, related_name="career_insights", null=True, blank=True)
    demand_level = models.CharField(max_length=50, blank=True, null=True)  # HIGH, MEDIUM, LOW
    average_salary = models.CharField(max_length=50, blank=True, null=True)
    career_fields = models.TextField(blank=True, null=True)

    def __str__(self):
        target_course = self.course or self.tvet_course or self.kmc_course or self.ttc_course
        return f"Career Insights: {target_course}"


# =====================================================
# Career Profile (for career guidance section)
# =====================================================
class CareerProfile(models.Model):
    DEMAND_CHOICES = [
        ("very_high", "Very High"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    title = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    description = models.TextField()
    duties = models.TextField(blank=True, help_text="Key duties and responsibilities")
    skills_required = models.TextField(blank=True, help_text="Skills needed for this career")
    educational_pathway = models.TextField(blank=True, help_text="Steps to enter this career")
    job_opportunities = models.TextField(blank=True, help_text="Where you can work")
    average_salary = models.CharField(max_length=100, blank=True, help_text="e.g. KSh 50,000 – 150,000/month")
    demand_level = models.CharField(max_length=20, choices=DEMAND_CHOICES, default="medium")
    future_outlook = models.TextField(blank=True, help_text="Future growth prospects")
    icon = models.CharField(max_length=50, blank=True, help_text="FontAwesome icon class")
    image = models.ImageField(upload_to="career_profile_images/", blank=True, null=True)
    career_tags = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated tags used for quiz matching, e.g. science,health,biology"
    )
    related_courses = models.ManyToManyField(
        "courses.Course", blank=True, related_name="career_profiles"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.title)
            slug = base
            counter = 1
            while CareerProfile.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_tags_list(self):
        return [t.strip() for t in self.career_tags.split(",") if t.strip()]

    def get_demand_color(self):
        colors = {
            "very_high": "success",
            "high": "primary",
            "medium": "warning",
            "low": "secondary",
        }
        return colors.get(self.demand_level, "secondary")


# =====================================================
# Career Assessment Quiz
# =====================================================
class QuizQuestion(models.Model):
    CATEGORY_CHOICES = [
        ("interest", "Interests"),
        ("strength", "Strengths"),
        ("personality", "Personality"),
        ("values", "Values"),
    ]

    text = models.CharField(max_length=300)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="interest")
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text


class QuizOption(models.Model):
    question = models.ForeignKey(
        QuizQuestion, on_delete=models.CASCADE, related_name="options"
    )
    text = models.CharField(max_length=200)
    career_tags = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated career tags this option maps to, e.g. science,engineering"
    )
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.question.text[:40]} → {self.text}"

    def get_tags_list(self):
        return [t.strip() for t in self.career_tags.split(",") if t.strip()]


class QuizSubmission(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="quiz_submissions", null=True, blank=True
    )
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Quiz by {self.user or self.session_key} on {self.created_at.date()}"


class QuizAnswer(models.Model):
    submission = models.ForeignKey(
        QuizSubmission, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    option = models.ForeignKey(QuizOption, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("submission", "question")

    def __str__(self):
        return f"{self.question.text[:40]} → {self.option.text}"

# =====================================================
# Cluster points mapping
# =====================================================
CLUSTER_GRADE_POINTS = {
    "A": 12,
    "A-": 11,
    "B+": 10,
    "B": 9,
    "B-": 8,
    "C+": 7,
    "C": 6,
    "C-": 5,
    "D+": 4,
    "D": 3,
    "D-": 2,
    "E": 1,
}

# =====================================================
# Mean grade mapping for diploma / KMTC / TVET
# =====================================================
MEAN_GRADE_POINTS = {
    "A": 12,
    "A-": 11,
    "B+": 10,
    "B": 9,
    "B-": 8,
    "C+": 7,
    "C": 6,
    "C-": 5,
    "D+": 4,
    "D": 3,
    "D-": 2,
    "E": 1,
}


# =====================================================
# 1. Calculate Cluster Points for Degree Courses
# =====================================================
def calculate_cluster_points(kcse_grades: Dict[str, str], cluster_subjects: List[str]) -> float:
    """
    kcse_grades: {'Mathematics': 'A', 'Physics': 'B+' ...}
    cluster_subjects: ['Mathematics', 'Physics', 'Biology']
    returns total cluster points
    """
    points = 0
    for subject in cluster_subjects:
        grade = kcse_grades.get(subject)
        if grade:
            points += CLUSTER_GRADE_POINTS.get(grade, 0)
    return points


# =====================================================
# 2. Calculate Mean Grade for Diploma / KMTC / TVET
# =====================================================
def calculate_mean_grade(kcse_grades: Dict[str, str]) -> float:
    """
    Returns the mean grade points across all subjects
    """
    total = 0
    count = 0
    for grade in kcse_grades.values():
        total += MEAN_GRADE_POINTS.get(grade, 0)
        count += 1
    if count == 0:
        return 0
    return total / count


# =====================================================
# 3. Predict Admission Chance
# =====================================================
def predict_admission_chance(student_points: float, cutoff: float) -> str:
    diff = student_points - cutoff
    if diff >= 3:
        return "VERY HIGH"
    elif diff >= 1:
        return "HIGH"
    elif diff >= 0:
        return "MEDIUM"
    else:
        return "LOW"


# =====================================================
# 4. Match Student to Degree Courses
# =====================================================
def match_degree_courses(kcse_grades: Dict[str, str]) -> List[StudentCourseMatch]:
    matches = []
    for course in Course.objects.filter(category__name="Degree"):
        cluster_subjects = [s.name for s in course.cluster_subjects.all()]
        cluster_points = calculate_cluster_points(kcse_grades, cluster_subjects)
        cutoffs = course.cutoffs.all()
        for cutoff in cutoffs:
            admission = predict_admission_chance(cluster_points, cutoff.cutoff_points)
            match_score = cluster_points / cutoff.cutoff_points * 100  # simple AI score
            match = StudentCourseMatch(
                course=course,
                university=cutoff.university,
                admission_chance=admission,
                match_score=match_score
            )
            matches.append(match)
    # Rank by match_score descending
    matches.sort(key=lambda x: x.match_score, reverse=True)
    return matches


# =====================================================
# 5. Match Student to Diploma Courses
# =====================================================
def match_diploma_courses(kcse_grades: Dict[str, str]) -> List[StudentCourseMatch]:
    mean_grade = calculate_mean_grade(kcse_grades)
    matches = []
    for course in Course.objects.filter(category__name="Diploma"):
        cutoffs = course.cutoffs.all()
        for cutoff in cutoffs:
            admission = predict_admission_chance(mean_grade, cutoff.cutoff_points)
            match_score = mean_grade / cutoff.cutoff_points * 100
            match = StudentCourseMatch(
                course=course,
                university=cutoff.university,
                admission_chance=admission,
                match_score=match_score
            )
            matches.append(match)
    matches.sort(key=lambda x: x.match_score, reverse=True)
    return matches


# =====================================================
# 6. Match Student to TVET Courses
# =====================================================
def match_tvet_courses(kcse_grades: Dict[str, str], category_name: str) -> List[StudentCourseMatch]:
    mean_grade = calculate_mean_grade(kcse_grades)
    matches = []
    tvet_category = TVETCategory.objects.get(name=category_name)
    courses = TVETCourse.objects.filter(category=tvet_category)
    for course in courses:
        # Optional: check if required subjects are met
        admission = "HIGH" if mean_grade >= MEAN_GRADE_POINTS.get(course.min_mean_grade, 0) else "LOW"
        match_score = mean_grade / MEAN_GRADE_POINTS.get(course.min_mean_grade, 1) * 100
        match = StudentCourseMatch(
            tvet_course=course,
            admission_chance=admission,
            match_score=match_score
        )
        matches.append(match)
    matches.sort(key=lambda x: x.match_score, reverse=True)
    return matches


# =====================================================
# 7. Match Student to KMTC Courses
# =====================================================
def match_kmtc_courses(kcse_grades: Dict[str, str]) -> List[StudentCourseMatch]:
    mean_grade = calculate_mean_grade(kcse_grades)
    matches = []
    courses = KMTCourse.objects.all()
    for course in courses:
        admission = "HIGH" if mean_grade >= MEAN_GRADE_POINTS.get(course.min_mean_grade, 0) else "LOW"
        match_score = mean_grade / MEAN_GRADE_POINTS.get(course.min_mean_grade, 1) * 100
        match = StudentCourseMatch(
            kmc_course=course,
            admission_chance=admission,
            match_score=match_score
        )
        matches.append(match)
    matches.sort(key=lambda x: x.match_score, reverse=True)
    return matches


# =====================================================
# 8. Match Student to TTC Courses
# =====================================================
def match_ttc_courses(kcse_grades: Dict[str, str]) -> List[StudentCourseMatch]:
    mean_grade = calculate_mean_grade(kcse_grades)
    matches = []
    courses = TTCCourse.objects.all()
    for course in courses:
        admission = "HIGH" if mean_grade >= MEAN_GRADE_POINTS.get(course.min_mean_grade, 0) else "LOW"
        match_score = mean_grade / MEAN_GRADE_POINTS.get(course.min_mean_grade, 1) * 100
        match = StudentCourseMatch(
            ttc_course=course,
            admission_chance=admission,
            match_score=match_score
        )
        matches.append(match)
    matches.sort(key=lambda x: x.match_score, reverse=True)
    return matches


# =====================================================
# 9. Generate AI Recommendation
# =====================================================
def generate_ai_recommendation(matches: List[StudentCourseMatch]) -> AIRecommendation:
    if not matches:
        text = "No suitable courses found based on the provided KCSE results."
    else:
        top_courses = matches[:5]
        text = "Based on your KCSE results, the top recommended courses are:\n"
        for match in top_courses:
            course_name = (match.course or match.tvet_course or match.kmc_course or match.ttc_course).name
            text += f"• {course_name} (Admission Chance: {match.admission_chance}, Score: {int(match.match_score)}%)\n"
    ai = AIRecommendation(advice_text=text)
    ai.save()
    return ai


# =====================================================
# 10. Full Career Guidance Engine
# =====================================================
def career_guidance_engine(kcse_grades: Dict[str, str], pathway: str, tvet_category: str = None):
    """
    pathway: "Degree", "Diploma", "KMTC", "TVET", "TTC"
    tvet_category: required if pathway is TVET
    Returns: top matches + AI recommendation
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
        raise ValueError("Invalid pathway selected")
    
    ai = generate_ai_recommendation(matches)
    return matches, ai