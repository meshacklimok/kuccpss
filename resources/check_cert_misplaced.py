"""Find CRAFT/ARTISAN sections in the certificate PDF that were seeded under wrong type."""
import django, os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kuccpss.settings")
sys.path.insert(0, r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss")
django.setup()

from courses.models import Course, CourseType

cert_type = CourseType.objects.get(name="TVET Certificate (Level 5)")
misplaced = Course.objects.filter(course_type=cert_type).filter(
    name__iregex=r"^(Craft|Artisan)\b"
)
print(f"Courses under Certificate type that start with Craft/Artisan: {misplaced.count()}")
for c in misplaced:
    print(f"  [{c.pk}] {c.name}  (offerings: {c.offerings.count()})")
