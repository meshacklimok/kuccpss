"""
CareerNext Load Test
====================
Run against your staging/production URL:

    pip install locust
    locust -f scripts/locustfile.py --host https://careernext.co.ke

Then open http://localhost:8089 in your browser.

Start with:  50 users, ramp 5/sec  → watch response times
Then try:   200 users, ramp 10/sec → find the knee of the curve
Then try:   500 users, ramp 20/sec → find the break point

Realistic peak: KUCCPS release day (October/March) — mostly mobile students
entering grades and checking eligible courses.
"""
from locust import HttpUser, task, between
import random


# ── Realistic grade distributions (A=12, A-=11, B+=10 … E=1) ──────────────
GRADES = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'E']

OPTIONAL_SUBJECTS = [
    'history', 'geography', 'cre', 'ire', 'hrfe', 'business_studies',
    'agriculture', 'home_science', 'art', 'comp', 'music', 'french', 'german',
    'arabic', 'aviation', 'drawing', 'electricity', 'metalwork', 'woodwork',
    'building', 'power_mechanics', 'farming', 'animal_husbandry',
]


def _grade():
    # Weight towards middle grades — realistic Kenyan KCSE distribution
    return random.choices(
        GRADES,
        weights=[2, 4, 7, 10, 12, 14, 15, 13, 11, 8, 3, 1],
        k=1,
    )[0]


def _calc_payload():
    """Build a realistic calculator form submission."""
    subjects = random.sample(OPTIONAL_SUBJECTS, 5)
    return {
        'csrfmiddlewaretoken': 'test',
        'maths': _grade(),
        'english': _grade(),
        'kiswahili': _grade(),
        f'{subjects[0]}': _grade(),
        f'{subjects[1]}': _grade(),
        f'{subjects[2]}': _grade(),
        f'{subjects[3]}': _grade(),
        f'{subjects[4]}': _grade(),
    }


class StudentUser(HttpUser):
    """
    Simulates a typical Form 4 leaver on their phone:
    1. Hits the home page
    2. Goes to the calculator
    3. Submits grades
    4. Views eligible courses
    5. Browses a course list or institution
    6. Returns to calculator (common — students tweak grades)
    """
    wait_time = between(2, 8)  # realistic think time: 2–8 seconds between actions

    def on_start(self):
        """Get a CSRF token from the home page before doing anything."""
        self.client.get('/', name='Home')

    @task(3)
    def view_home(self):
        self.client.get('/', name='Home')

    @task(5)
    def view_calculator(self):
        self.client.get('/clusterpoints/', name='Calculator GET')

    @task(8)
    def submit_calculator(self):
        """The heaviest operation — POST with grades."""
        with self.client.get('/clusterpoints/', catch_response=True, name='Calculator GET') as r:
            # Extract CSRF from cookie
            csrf = r.cookies.get('csrftoken', 'dummy')
        payload = _calc_payload()
        payload['csrfmiddlewaretoken'] = csrf
        self.client.post(
            '/clusterpoints/',
            data=payload,
            name='Calculator POST',
            catch_response=True,
        )

    @task(6)
    def view_eligible_courses(self):
        """Hits the cached eligible courses page — fast if cache warm."""
        self.client.get('/clusterpoints/eligible-courses/', name='Eligible Courses')

    @task(4)
    def view_course_list(self):
        self.client.get('/courses/', name='Course Types List')

    @task(3)
    def view_degree_courses(self):
        self.client.get('/courses/degree/', name='Degree Courses')

    @task(2)
    def search_courses(self):
        q = random.choice(['medicine', 'engineering', 'education', 'nursing', 'law', 'ict'])
        self.client.get(f'/courses/degree/?q={q}', name='Course Search (HTMX)',
                        headers={'HX-Request': 'true'})

    @task(2)
    def view_institutions(self):
        self.client.get('/institutions/', name='Institution Types')

    @task(2)
    def view_universities(self):
        self.client.get('/institutions/university/', name='Universities')

    @task(1)
    def view_careers(self):
        self.client.get('/career/', name='Career Home')


class PowerUser(HttpUser):
    """
    Simulates a mentor or parent who uses the tool intensively —
    runs the calculator multiple times comparing different grades.
    10% of traffic.
    """
    wait_time = between(1, 3)
    weight = 1  # 1 power user for every 9 regular students

    @task(5)
    def hammer_calculator(self):
        with self.client.get('/clusterpoints/', catch_response=True, name='[Power] Calc GET') as r:
            csrf = r.cookies.get('csrftoken', 'dummy')
        payload = _calc_payload()
        payload['csrfmiddlewaretoken'] = csrf
        self.client.post('/clusterpoints/', data=payload, name='[Power] Calc POST')

    @task(3)
    def view_eligible_fast(self):
        self.client.get('/clusterpoints/eligible-courses/', name='[Power] Eligible')

    @task(2)
    def search_repeatedly(self):
        for q in ['medicine', 'law', 'engineering']:
            self.client.get(f'/courses/degree/?q={q}', name='[Power] Search',
                            headers={'HX-Request': 'true'})
