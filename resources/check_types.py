import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuccpss.settings')
sys.path.insert(0, r'c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss')
django.setup()

from courses.models import CourseType, Course, CourseOffering
from institutions.models import InstitutionType, Institution

print('=== CourseTypes ===')
for ct in CourseType.objects.all().order_by('name'):
    c = Course.objects.filter(course_type=ct).count()
    o = CourseOffering.objects.filter(course__course_type=ct).count()
    print(f'  {ct.name:35s} slug={ct.slug:30s} courses={c:4d}  offerings={o:5d}')

print()
print('=== InstitutionTypes ===')
for it in InstitutionType.objects.all().order_by('name'):
    n = Institution.objects.filter(institution_type=it).count()
    print(f'  {it.name:30s}  institutions={n}')
