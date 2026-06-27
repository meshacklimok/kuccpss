"""
Backfill missing fields on courses.Course:
  - minimum_mean_grade  (by course type defaults for Degree/Diploma)
  - duration            (by course type)
  - career_outcomes     (by keyword matching on course name)

Run:
    python manage.py backfill_course_fields
    python manage.py backfill_course_fields --dry-run
    python manage.py backfill_course_fields --type degree
    python manage.py backfill_course_fields --type diploma
    python manage.py backfill_course_fields --type all
"""
from django.core.management.base import BaseCommand


# ─── Per course-type defaults ─────────────────────────────────────────────────
GRADE_DEFAULTS = {
    "degree":   "C+",
    "diploma":  "C",
    "kmtc":     "C-",
    "ttc":      "C",
    "tvet":     "C-",
}

DURATION_DEFAULTS = {
    "degree":               "4 Years",
    "diploma":              "2–3 Years",
    "kmtc":                 "3 Years",
    "ttc":                  "2 Years",
    "tvet diploma":         "2 Years",
    "tvet certificate":     "1–2 Years",
    "tvet craft":           "1 Year",
    "tvet artisan":         "1 Year",
    "tvet professional":    "3 Years",
    "tvet proficiency":     "6 Months",
}

# ─── Career outcome map: keyword → comma-separated career titles ──────────────
# Keys are lowercased substrings of course names.
CAREER_MAP = [
    # Education
    ("education",           "Teacher, Lecturer, Education Officer, Curriculum Developer, School Principal"),
    ("teaching",            "Teacher, Education Officer, Training Coordinator"),
    # Health & Medicine
    ("medicine",            "Doctor, Physician, Medical Officer, Surgeon, General Practitioner"),
    ("nursing",             "Registered Nurse, Ward Manager, Community Health Officer, Nurse Educator"),
    ("pharmacy",            "Pharmacist, Clinical Pharmacist, Drug Safety Officer, Pharmaceutical Rep"),
    ("medical",             "Medical Officer, Clinical Officer, Health Administrator, Lab Technologist"),
    ("health",              "Public Health Officer, Community Health Worker, Health Inspector, Epidemiologist"),
    ("clinical",            "Clinical Officer, Medical Practitioner, Healthcare Consultant"),
    ("dentistry",           "Dentist, Oral Health Officer, Dental Surgeon, Orthodontist"),
    ("optometry",           "Optometrist, Eye Care Specialist, Vision Therapist"),
    ("nutrition",           "Nutritionist, Dietitian, Food Safety Officer, Public Health Specialist"),
    ("physiotherapy",       "Physiotherapist, Rehabilitation Therapist, Sports Physio"),
    ("occupational therapy","Occupational Therapist, Rehabilitation Specialist"),
    ("radiography",         "Radiographer, Medical Imaging Specialist, Radiologist Technician"),
    # Engineering & Technology
    ("engineering",         "Engineer, Project Manager, Technical Consultant, R&D Specialist"),
    ("electrical",          "Electrical Engineer, Power Systems Engineer, Automation Engineer"),
    ("mechanical",          "Mechanical Engineer, Manufacturing Engineer, Production Manager"),
    ("civil",               "Civil Engineer, Structural Engineer, Site Manager, Urban Planner"),
    ("computer science",    "Software Developer, Data Scientist, Systems Analyst, IT Manager"),
    ("information technology","IT Officer, Systems Administrator, Network Engineer, Cybersecurity Analyst"),
    ("software",            "Software Engineer, App Developer, DevOps Engineer, Tech Lead"),
    ("data science",        "Data Analyst, Machine Learning Engineer, Business Intelligence Analyst"),
    ("electronics",         "Electronics Engineer, IoT Specialist, Firmware Developer"),
    ("telecommunication",   "Telecom Engineer, Network Engineer, RF Engineer"),
    ("architecture",        "Architect, Urban Designer, CAD Technician, Project Manager"),
    ("built environment",   "Quantity Surveyor, Urban Planner, Building Inspector, Project Manager"),
    ("quantity survey",     "Quantity Surveyor, Cost Estimator, Project Manager, Contract Manager"),
    ("real estate",         "Property Valuer, Real Estate Agent, Property Manager, Land Economist"),
    # Agriculture & Environment
    ("agriculture",         "Agronomist, Agricultural Officer, Farm Manager, Food Scientist"),
    ("agribusiness",        "Agribusiness Manager, Agricultural Marketer, Farm Investment Analyst"),
    ("food science",        "Food Technologist, Quality Control Officer, Food Safety Inspector"),
    ("horticulture",        "Horticulturist, Floriculture Manager, Landscape Designer"),
    ("animal science",      "Animal Nutritionist, Livestock Officer, Veterinary Technician"),
    ("veterinary",          "Veterinarian, Animal Health Officer, Wildlife Vet"),
    ("forestry",            "Forester, Conservation Officer, Environmental Consultant"),
    ("environmental",       "Environmental Scientist, Ecologist, Conservation Manager"),
    ("fisheries",           "Fisheries Officer, Aquaculture Manager, Marine Biologist"),
    ("wildlife",            "Wildlife Manager, Conservation Scientist, Park Warden"),
    ("soil science",        "Soil Scientist, Agronomist, Environmental Analyst"),
    ("natural resource",    "Resource Manager, Environmental Officer, Conservation Planner"),
    # Business & Economics
    ("economics",           "Economist, Financial Analyst, Policy Analyst, Economic Researcher, Banker"),
    ("finance",             "Financial Analyst, Investment Banker, Accountant, Risk Manager"),
    ("accounting",          "Accountant, Auditor, Finance Manager, Tax Consultant, CPA"),
    ("actuarial",           "Actuary, Risk Analyst, Insurance Underwriter, Data Analyst"),
    ("banking",             "Banker, Credit Analyst, Financial Officer, Branch Manager"),
    ("business",            "Business Manager, Entrepreneur, Operations Manager, Business Analyst"),
    ("commerce",            "Business Development Officer, Trade Analyst, Supply Chain Manager"),
    ("entrepreneurship",    "Entrepreneur, Business Development Manager, Startup Founder"),
    ("marketing",           "Marketing Manager, Brand Manager, Digital Marketer, Sales Manager"),
    ("supply chain",        "Supply Chain Manager, Logistics Officer, Procurement Specialist"),
    ("procurement",         "Procurement Officer, Supply Chain Analyst, Contract Manager"),
    ("logistics",           "Logistics Manager, Supply Chain Coordinator, Freight Manager"),
    ("human resource",      "HR Manager, Talent Acquisition Specialist, Labour Relations Officer"),
    ("management",          "Manager, Operations Officer, Business Analyst, Strategy Consultant"),
    ("hospitality",         "Hotel Manager, Restaurant Manager, Events Manager, Tourism Officer"),
    ("tourism",             "Tourism Officer, Travel Consultant, Hotel Manager, Tour Guide"),
    ("travel",              "Travel Agent, Tour Operator, Tourism Consultant"),
    # Sciences
    ("biology",             "Biologist, Laboratory Analyst, Research Scientist, Conservation Officer"),
    ("biochemistry",        "Biochemist, Laboratory Technologist, Medical Researcher, Pharmacologist"),
    ("chemistry",           "Chemist, Laboratory Scientist, Quality Analyst, Chemical Engineer"),
    ("physics",             "Physicist, Research Scientist, Lab Analyst, Quality Assurance Engineer"),
    ("mathematics",         "Mathematician, Statistician, Data Analyst, Actuary, Financial Modeller"),
    ("statistics",          "Statistician, Data Analyst, Research Officer, Biostatistician"),
    ("geology",             "Geologist, Mining Engineer, Petroleum Geologist, Environmental Consultant"),
    ("geoscience",          "Geoscientist, Hydrogeologist, Environmental Consultant"),
    ("geography",           "Geographer, Urban Planner, GIS Analyst, Environmental Officer"),
    ("meteorology",         "Meteorologist, Climate Analyst, Weather Forecaster"),
    ("astronomy",           "Astronomer, Astrophysicist, Space Scientist"),
    # Law & Social Sciences
    ("law",                 "Lawyer, Advocate, Legal Consultant, Magistrate, Corporate Counsel"),
    ("legal",               "Legal Officer, Compliance Manager, Advocate, Contract Lawyer"),
    ("sociology",           "Social Worker, Community Development Officer, Policy Analyst"),
    ("social work",         "Social Worker, Counsellor, Community Development Officer"),
    ("psychology",          "Psychologist, Counsellor, Human Resource Specialist, Mental Health Officer"),
    ("counselling",         "Counsellor, Psychotherapist, Student Affairs Officer"),
    ("criminology",         "Criminologist, Police Officer, Prison Officer, Probation Officer"),
    ("political science",   "Political Scientist, Policy Analyst, Civil Servant, Diplomat"),
    ("public administration","Public Administrator, Civil Servant, Policy Officer, Government Official"),
    ("development studies", "Development Officer, NGO Programme Manager, Policy Analyst"),
    ("community development","Community Development Officer, Social Welfare Officer, NGO Manager"),
    ("international",       "Diplomat, International Relations Analyst, NGO Programme Manager"),
    # Arts & Communication
    ("communication",       "Communication Officer, PR Specialist, Journalist, Media Manager"),
    ("journalism",          "Journalist, Editor, News Anchor, Media Producer"),
    ("media",               "Media Producer, Content Creator, Broadcaster, PR Officer"),
    ("linguistics",         "Linguist, Language Teacher, Translator, Interpreter"),
    ("literature",          "Writer, Editor, Literary Analyst, Language Teacher"),
    ("fine art",            "Artist, Art Director, Graphic Designer, Gallery Curator"),
    ("design",              "Graphic Designer, UX Designer, Industrial Designer, Art Director"),
    ("music",               "Musician, Music Teacher, Sound Engineer, Music Producer"),
    ("performing arts",     "Performer, Theatre Director, Arts Educator, Events Manager"),
    ("film",                "Film Director, Producer, Cinematographer, Editor"),
    # Religious & Social
    ("theology",            "Pastor, Chaplain, Religious Teacher, Community Leader"),
    ("islamic",             "Islamic Studies Teacher, Imam, Religious Scholar"),
    # Library & Information
    ("library",             "Librarian, Information Manager, Records Officer, Archivist"),
    ("information science", "Information Manager, Data Librarian, Records Manager"),
    # Sports
    ("sports",              "Sports Coach, PE Teacher, Sports Manager, Fitness Trainer"),
    ("recreation",          "Recreation Officer, Sports Coach, Leisure Manager"),
    # Aviation & Maritime
    ("aviation",            "Pilot, Flight Engineer, Air Traffic Controller, Aviation Manager"),
    ("maritime",            "Marine Officer, Ship Captain, Maritime Engineer, Port Manager"),
    ("aeronautical",        "Aeronautical Engineer, Aircraft Technician, Avionics Engineer"),
    # Security
    ("security",            "Security Manager, Intelligence Analyst, Police Officer, Risk Consultant"),
    ("military",            "Military Officer, Defence Analyst, Security Consultant"),
]


def get_course_type_key(name: str) -> str:
    n = name.lower()
    if "degree" in n or "bachelor" in n:
        return "degree"
    if "diploma" in n:
        if "tvet" in n:
            return "tvet diploma"
        return "diploma"
    if "kmtc" in n or "medical training" in n:
        return "kmtc"
    if "ttc" in n or "teacher training" in n:
        return "ttc"
    if "tvet" in n:
        if "craft" in n:
            return "tvet craft"
        if "artisan" in n:
            return "tvet artisan"
        if "professional" in n:
            return "tvet professional"
        if "proficiency" in n:
            return "tvet proficiency"
        if "certificate" in n:
            return "tvet certificate"
        return "tvet"
    return ""


def guess_career_outcomes(course_name: str) -> str:
    n = course_name.lower()
    for keyword, outcomes in CAREER_MAP:
        if keyword in n:
            return outcomes
    return ""


class Command(BaseCommand):
    help = "Backfill minimum_mean_grade, duration, and career_outcomes for Degree/Diploma courses"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print changes without saving")
        parser.add_argument(
            "--type",
            default="all",
            choices=["degree", "diploma", "kmtc", "ttc", "tvet", "all"],
            help="Limit to a specific course type family",
        )
        parser.add_argument(
            "--overwrite", action="store_true",
            help="Overwrite fields that already have values (default: skip filled fields)",
        )

    def handle(self, *args, **options):
        from courses.models import Course

        dry = options["dry_run"]
        overwrite = options["overwrite"]
        type_filter = options["type"]

        courses = Course.objects.select_related("course_type").all()
        if type_filter != "all":
            courses = courses.filter(course_type__name__icontains=type_filter)

        updated_grade = updated_dur = updated_careers = 0
        to_save: list = []

        for course in courses:
            ct_key = get_course_type_key(course.course_type.name)
            changed = False

            # minimum_mean_grade
            if (not course.minimum_mean_grade or overwrite) and ct_key in GRADE_DEFAULTS:
                new_grade = GRADE_DEFAULTS[ct_key]
                if course.minimum_mean_grade != new_grade:
                    if not dry:
                        course.minimum_mean_grade = new_grade
                    updated_grade += 1
                    changed = True

            # duration
            if (not course.duration or overwrite) and ct_key in DURATION_DEFAULTS:
                new_dur = DURATION_DEFAULTS[ct_key]
                if course.duration != new_dur:
                    if not dry:
                        course.duration = new_dur
                    updated_dur += 1
                    changed = True

            # career_outcomes
            if not course.career_outcomes or overwrite:
                outcomes = guess_career_outcomes(course.name)
                if outcomes and course.career_outcomes != outcomes:
                    if not dry:
                        course.career_outcomes = outcomes
                    updated_careers += 1
                    changed = True

            if changed and not dry:
                to_save.append(course)

        if not dry and to_save:
            Course.objects.bulk_update(
                to_save, ["minimum_mean_grade", "duration", "career_outcomes"], batch_size=200
            )

        label = "(DRY RUN) " if dry else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{label}Done:\n"
                f"  minimum_mean_grade filled : {updated_grade}\n"
                f"  duration filled           : {updated_dur}\n"
                f"  career_outcomes filled    : {updated_careers}\n"
                f"  total courses processed   : {courses.count()}"
            )
        )
