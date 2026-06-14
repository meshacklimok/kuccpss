"""
Fix courses wrongly placed under Certificate type.
Moves Craft/* → TVET Craft Certificate (Level 3)
Moves Artisan/* → TVET Artisan Certificate (Level 4)
If a duplicate already exists in the target type, merges offerings then deletes the wrong one.
"""
import django, os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kuccpss.settings")
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()

from django.db import transaction
from courses.models import Course, CourseOffering, CourseType

cert_type  = CourseType.objects.get(name="TVET Certificate (Level 5)")
craft_type = CourseType.objects.get(name="TVET Craft Certificate (Level 3)")
artisan_type = CourseType.objects.get(name="TVET Artisan Certificate (Level 4)")

misplaced = list(Course.objects.filter(course_type=cert_type).filter(
    name__iregex=r"^(Craft|Artisan)\b"
))

print(f"Fixing {len(misplaced)} misplaced courses...\n")

with transaction.atomic():
    for course in misplaced:
        target_type = artisan_type if course.name.lower().startswith("artisan") else craft_type

        # Check if a course with the same name already exists in the target type
        duplicate = Course.objects.filter(
            course_type=target_type,
            name__iexact=course.name,
        ).first()

        if duplicate:
            # Merge offerings: re-point offerings that don't already exist on the duplicate
            offerings = list(CourseOffering.objects.filter(course=course))
            merged = 0
            for off in offerings:
                exists = CourseOffering.objects.filter(
                    course=duplicate, institution=off.institution
                ).exists()
                if not exists:
                    off.course = duplicate
                    off.save()
                    merged += 1
                else:
                    off.delete()
            course.delete()
            print(f"  MERGED '{course.name}' → existing [{duplicate.pk}] in {target_type.name}")
            print(f"    Merged {merged} offerings, deleted duplicates")
        else:
            # Just move the course
            count = course.offerings.count()
            course.course_type = target_type
            course.save()
            print(f"  MOVED  '{course.name}' → {target_type.name}  ({count} offerings)")

print("\nDone.")

# Final counts
for ct in [cert_type, craft_type, artisan_type]:
    c = Course.objects.filter(course_type=ct).count()
    o = CourseOffering.objects.filter(course__course_type=ct).count()
    print(f"  {ct.name}: {c} courses, {o} offerings")
