"""
Fix course type mixing across Level 3 / Level 4 / Level 5.

Migrations:
  A. Level 4 "Craft Certificate in X"  → Level 3
  B. Level 4 "Certificate in X"        → Level 5
  C. Level 3 "Certificate in X"        → Level 5
  D. Level 3 "Artisan Certificate in X" → Level 4
  E. Level 3 "Artisan in X"            → Level 4

For each: if a course with the same name already exists in the target type,
merge offerings (skip duplicates) then delete the source course.
Otherwise just update course_type.
"""
import django, os, sys, re
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kuccpss.settings")
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()

from django.db import transaction
from courses.models import Course, CourseOffering, CourseType

ct3 = CourseType.objects.get(name="TVET Craft Certificate (Level 3)")
ct4 = CourseType.objects.get(name="TVET Artisan Certificate (Level 4)")
ct5 = CourseType.objects.get(name="TVET Certificate (Level 5)")

def merge_or_move(src_course, target_type):
    """Move src_course to target_type; merge if a same-named course already exists there."""
    dup = Course.objects.filter(course_type=target_type, name__iexact=src_course.name).first()
    offerings = list(CourseOffering.objects.filter(course=src_course))
    if dup:
        merged = 0
        deleted = 0
        for off in offerings:
            exists = CourseOffering.objects.filter(course=dup, institution=off.institution).exists()
            if not exists:
                off.course = dup
                off.save()
                merged += 1
            else:
                off.delete()
                deleted += 1
        src_course.delete()
        return f"MERGED into [{dup.pk}] ({merged} merged, {deleted} dup-deleted)"
    else:
        src_course.course_type = target_type
        src_course.save()
        return f"MOVED ({len(offerings)} offerings kept)"

total_moved = 0
total_merged = 0

with transaction.atomic():

    # A. Level 4 "Craft Certificate in X" → Level 3
    print("=== A: Level 4 Craft Certificate → Level 3 ===")
    for c in list(Course.objects.filter(course_type=ct4, name__iregex=r"^Craft (Certificate|in)\b")):
        result = merge_or_move(c, ct3)
        print(f"  [{c.pk}] {c.name}: {result}")
        total_moved += 1

    # B. Level 4 "Certificate in X" → Level 5
    print("\n=== B: Level 4 Certificate in X → Level 5 ===")
    for c in list(Course.objects.filter(course_type=ct4, name__iregex=r"^Certificate\b")):
        result = merge_or_move(c, ct5)
        print(f"  [{c.pk}] {c.name}: {result}")
        total_moved += 1

    # C. Level 3 "Certificate in X" → Level 5
    print("\n=== C: Level 3 Certificate in X → Level 5 ===")
    for c in list(Course.objects.filter(course_type=ct3, name__iregex=r"^Certificate\b")):
        result = merge_or_move(c, ct5)
        print(f"  [{c.pk}] {c.name}: {result}")
        total_moved += 1

    # D. Level 3 "Artisan Certificate in X" → Level 4
    print("\n=== D: Level 3 Artisan Certificate → Level 4 ===")
    for c in list(Course.objects.filter(course_type=ct3, name__iregex=r"^Artisan Certificate\b")):
        result = merge_or_move(c, ct4)
        print(f"  [{c.pk}] {c.name}: {result}")
        total_moved += 1

    # E. Level 3 "Artisan in X" → Level 4
    print("\n=== E: Level 3 Artisan in X → Level 4 ===")
    for c in list(Course.objects.filter(course_type=ct3, name__iregex=r"^Artisan in\b")):
        result = merge_or_move(c, ct4)
        print(f"  [{c.pk}] {c.name}: {result}")
        total_moved += 1

print(f"\nTotal courses processed: {total_moved}")

# Final counts
print("\n=== Final counts ===")
for ct in [ct3, ct4, ct5]:
    c = Course.objects.filter(course_type=ct).count()
    o = CourseOffering.objects.filter(course__course_type=ct).count()
    print(f"  {ct.name}: {c} courses, {o} offerings")
