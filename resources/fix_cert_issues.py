"""
Fix two Level 5 certificate mapping issues:
1. Rename 'Kitutu Chache Technical Vocational College' → add 'And' so normalize matches PDF
2. Merge 'Certificate in Co-operative Management (Level 5)' (0 offerings)
   into 'Certificate in Cooperative Management' (10 offerings)
"""
import django, os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kuccpss.settings")
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()

from django.db import transaction
from institutions.models import Institution
from courses.models import Course, CourseOffering, CourseType

with transaction.atomic():
    # --- Fix 1: Kitutu Chache institution name ---
    inst = Institution.objects.get(pk=255)
    old_name = inst.name
    inst.name = "Kitutu Chache Technical And Vocational College"
    inst.save()
    print(f"Renamed institution [{inst.pk}]:")
    print(f"  {old_name!r}")
    print(f"  → {inst.name!r}")

    # --- Fix 2: Merge Co-operative into Cooperative ---
    ct = CourseType.objects.get(name="TVET Certificate (Level 5)")

    src = Course.objects.filter(course_type=ct, pk=1211).first()  # Co-operative (Level 5), 0 offerings
    dst = Course.objects.filter(course_type=ct, name__iexact="Certificate in Cooperative Management").first()

    if src and dst:
        src_count = src.offerings.count()
        dst_count = dst.offerings.count()
        print(f"\nMerging:")
        print(f"  SRC [{src.pk}] {src.name!r}  ({src_count} offerings)")
        print(f"  DST [{dst.pk}] {dst.name!r}  ({dst_count} offerings)")

        # Move any offerings from src → dst (none expected, but be safe)
        for off in CourseOffering.objects.filter(course=src):
            exists = CourseOffering.objects.filter(course=dst, institution=off.institution).exists()
            if not exists:
                off.course = dst
                off.save()
            else:
                off.delete()

        src.delete()
        print(f"  Merged and deleted src. DST now has {dst.offerings.count()} offerings.")
    elif not src:
        print(f"\nSRC course [1211] not found — may already be merged.")
    elif not dst:
        print(f"\nDST 'Certificate in Cooperative Management' not found.")

print("\nDone.")

# Show final counts
ct = CourseType.objects.get(name="TVET Certificate (Level 5)")
c = Course.objects.filter(course_type=ct).count()
from courses.models import CourseOffering
o = CourseOffering.objects.filter(course__course_type=ct).count()
print(f"Certificate Level 5: {c} courses, {o} offerings")
