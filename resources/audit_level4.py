"""Full audit of TVET Artisan Certificate (Level 4) courses and offerings."""
import django, os, sys, re
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kuccpss.settings")
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()

from courses.models import Course, CourseOffering, CourseType
from institutions.models import InstitutionType

ct = CourseType.objects.get(name="TVET Artisan Certificate (Level 4)")
courses = list(Course.objects.filter(course_type=ct).order_by("name"))
offerings = CourseOffering.objects.filter(course__course_type=ct)

print(f"=== TVET Artisan Certificate (Level 4) Audit ===")
print(f"Total courses:   {len(courses)}")
print(f"Total offerings: {offerings.count()}")

# 1. Courses with no offerings
no_offerings = [c for c in courses if c.offerings.count() == 0]
print(f"\n--- Courses with ZERO offerings: {len(no_offerings)} ---")
for c in no_offerings:
    print(f"  [{c.pk}] {c.name}")

# 2. Courses with wrong-type names (should all start with Artisan)
bad_name_re = re.compile(r"^(Diploma|Certificate|Craft|Grade|Bachelor|Master|Higher)", re.I)
odd_names = [c for c in courses if bad_name_re.match(c.name)]
print(f"\n--- Courses with wrong-type names: {len(odd_names)} ---")
for c in odd_names:
    print(f"  [{c.pk}] {c.name}  ({c.offerings.count()} offerings)")

# 3. Duplicate names
from collections import Counter
name_counts = Counter(c.name.lower() for c in courses)
dupes = {n: cnt for n, cnt in name_counts.items() if cnt > 1}
print(f"\n--- Duplicate course names: {len(dupes)} ---")
for name, cnt in sorted(dupes.items()):
    for c in [x for x in courses if x.name.lower() == name]:
        print(f"  [{c.pk}] {c.name}  ({c.offerings.count()} offerings)")

# 4. Offerings at non-TVET institutions
print(f"\n--- Offerings at non-TVET institutions ---")
wrong = []
for off in offerings.select_related("institution__institution_type"):
    it = off.institution.institution_type
    if it and "tvet" not in it.name.lower():
        wrong.append((off, it.name))
print(f"  Count: {len(wrong)}")
for off, itype in wrong[:20]:
    print(f"  {off.course.name[:50]} @ {off.institution.name} [{itype}]")

# 5. Full list
print(f"\n--- All courses (offerings | name) ---")
for c in courses:
    n = c.offerings.count()
    flag = " *** NO OFFERINGS ***" if n == 0 else ""
    print(f"  {n:>4}  {c.name}{flag}")
