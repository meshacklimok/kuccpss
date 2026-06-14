"""
Management command: categorize_degrees

Adds CourseCategory objects to the Degree CourseType and assigns every
degree course to the appropriate category based on keyword matching of
the course name.

Categories mirror the TVET Diploma taxonomy where applicable.

Run:
    conda run python manage.py categorize_degrees
    conda run python manage.py categorize_degrees --dry-run
"""

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, CourseCategory, CourseType


# ── Category keyword rules ────────────────────────────────────────────────────
# List of (category_name, [keywords...]). First match wins.
# Keywords are matched case-insensitively against the course name.
CATEGORY_RULES = [
    ("Health Sciences", [
        "medicine", "nursing", "pharmacy", "pharmacology", "clinical", "dental",
        "dentistry", "optometry", "physiotherapy", "occupational therapy",
        "nutrition", "dietetics", "public health", "health", "medical",
        "radiology", "orthopedic", "midwifery", "biomedical", "epidemiology",
        "anesthesia", "pathology", "prosthetics", "orthotics",
    ]),
    ("Agriculture & Food Sciences", [
        "agriculture", "agricultural", "agribusiness", "food science",
        "food technology", "veterinary", "animal science", "fisheries",
        "aquaculture", "dairy", "crop", "horticulture", "forestry",
        "range management", "agronomy", "soil science", "plant science",
        "animal production", "wildlife", "farm",
    ]),
    ("Engineering & Technology", [
        "engineering", "electrical", "electronic", "mechanical", "civil",
        "structural", "chemical", "manufacturing", "industrial", "automotive",
        "aeronautical", "aerospace", "petroleum", "mining", "materials",
        "geospatial", "surveying", "textile", "instrumentation", "automation",
        "renewable energy", "mechatronics",
    ]),
    ("Computing & ICT", [
        "computer science", "computer", "computing", "information technology",
        "information systems", "software", "cyber security", "cybersecurity",
        "data science", "artificial intelligence", "machine learning",
        "network", "telecommunications", "it ", " it)", "ict", "informatics",
    ]),
    ("Business & Commerce", [
        "business", "commerce", "accounting", "accountancy", "finance",
        "financial", "economics", "marketing", "management", "entrepreneurship",
        "banking", "insurance", "actuarial", "supply chain", "purchasing",
        "procurement", "logistics", "operations", "human resource",
        "project management", "strategic", "international trade",
    ]),
    ("Education", [
        "education", "teaching", "pedagogy", "curriculum", "educational",
        "early childhood", "special needs education", "teacher",
    ]),
    ("Law", [
        "law", "legal", "jurisprudence",
    ]),
    ("Media & Communications", [
        "media", "communication", "journalism", "public relations",
        "broadcasting", "film", "cinematography", "animation", "graphics",
        "design", "publishing", "print", "digital media",
    ]),
    ("Built Environment", [
        "architecture", "construction", "quantity surveying", "real estate",
        "building", "urban planning", "physical planning", "interior design",
        "landscape", "spatial planning",
    ]),
    ("Hospitality & Tourism", [
        "hospitality", "hotel", "tourism", "catering", "culinary", "travel",
        "events management", "recreation",
    ]),
    ("Natural Sciences", [
        "physics", "chemistry", "biology", "mathematics", "statistics",
        "botany", "zoology", "biochemistry", "microbiology", "science",
        "ecology", "earth science", "meteorology", "geology", "geography",
        "astronomy", "marine science", "conservation", "environment",
        "natural resource",
    ]),
    ("Social Sciences", [
        "sociology", "psychology", "anthropology", "political science",
        "international relations", "development studies", "gender",
        "community development", "counselling", "counseling", "social work",
        "criminology", "peace", "conflict", "security studies",
        "population studies", "demography",
    ]),
    ("Arts & Humanities", [
        "arts", "humanities", "history", "philosophy", "religion", "theology",
        "linguistics", "language", "literature", "music", "drama",
        "fine arts", "creative arts", "performing arts", "kiswahili",
        "french", "arabic", "chinese", "journalism", "intercultural",
        "biblical", "ministry", "church",
    ]),
    ("Transport & Logistics", [
        "transport", "maritime", "aviation", "logistics", "shipping",
        "nautical", "piloting",
    ]),
    ("Environment & Natural Resources", [
        "environmental", "climate", "renewable", "water resource",
        "resource management",
    ]),
]


def classify(name: str) -> str:
    """Return category name for the given course name."""
    lower = name.lower()
    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', lower):
                return category
    return "General"


class Command(BaseCommand):
    help = "Add categories to the Degree CourseType and assign courses."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        prefix = "[DRY RUN] " if dry else ""

        self.stdout.write("=" * 60)
        self.stdout.write(f"{prefix}categorize_degrees")
        self.stdout.write("=" * 60)

        with transaction.atomic():
            ct = CourseType.objects.get(name="Degree")
            courses = list(Course.objects.filter(course_type=ct))
            self.stdout.write(f"Total degree courses: {len(courses)}")

            # Classify all courses first to discover needed categories
            cat_to_courses: dict[str, list[Course]] = {}
            for c in courses:
                cat = classify(c.name)
                cat_to_courses.setdefault(cat, []).append(c)

            self.stdout.write("\nCategory breakdown:")
            for cat, cs in sorted(cat_to_courses.items(), key=lambda x: -len(x[1])):
                self.stdout.write(f"  {cat:40s} {len(cs):4d} courses")

            if dry:
                self.stdout.write("\n[dry-run] no DB changes.")
                transaction.set_rollback(True)
                return

            # Ensure categories exist (handle slug collisions by prefixing with type slug)
            from django.utils.text import slugify
            cat_objects: dict[str, CourseCategory] = {}
            for cat_name in cat_to_courses:
                obj = CourseCategory.objects.filter(name=cat_name, course_type=ct).first()
                if obj:
                    cat_objects[cat_name] = obj
                    continue
                # Build a collision-safe slug: degree-<cat>
                base_slug = slugify(f"degree-{cat_name}")
                slug = base_slug
                n = 1
                while CourseCategory.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{n}"
                    n += 1
                obj = CourseCategory(name=cat_name, course_type=ct, slug=slug)
                obj.save()
                cat_objects[cat_name] = obj
                self.stdout.write(self.style.SUCCESS(f"  Created category: {cat_name} (slug={slug!r})"))

            # Assign courses
            updated = 0
            for cat_name, cs in cat_to_courses.items():
                cat_obj = cat_objects[cat_name]
                Course.objects.filter(pk__in=[c.pk for c in cs]).update(category=cat_obj)
                updated += len(cs)

            self.stdout.write(self.style.SUCCESS(
                f"\nAssigned {updated} courses across {len(cat_objects)} categories."
            ))
