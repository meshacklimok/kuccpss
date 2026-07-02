import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuccpss.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()
from institutions.models import InstitutionType, Institution
from courses.models import CourseType, Course, CourseOffering

print('=== Institution Types ===')
for t in InstitutionType.objects.all():
    print(f'  {t.name}: {t.institutions.count()} institutions')

print()
print('=== TVET Course Types ===')
for ct in CourseType.objects.filter(name__startswith='TVET'):
    cats = ct.categories.count()
    courses = Course.objects.filter(course_type=ct).count()
    print(f'  {ct.name}: {cats} categories, {courses} courses')

print()
total = CourseOffering.objects.filter(course__course_type__name__startswith='TVET').count()
print(f'Total TVET offerings: {total}')

print()
print('=== TVET Diploma Categories ===')
ct = CourseType.objects.get(name='TVET Diploma (Level 6)')
for cat in ct.categories.all():
    n = Course.objects.filter(category=cat).count()
    print(f'  {cat.name}: {n} courses')
