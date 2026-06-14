import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuccpss.settings')
sys.path.insert(0, r'c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss')
django.setup()

from courses.models import CourseType, Course

for ct_name in ['TVET Diploma (Level 6)', 'TVET Certificate (Level 5)',
                'TVET Artisan Certificate (Level 4)', 'TVET Craft Certificate (Level 3)']:
    ct = CourseType.objects.get(name=ct_name)
    print(f'\n=== {ct_name} ===')
    for c in Course.objects.filter(course_type=ct).order_by('name')[:20]:
        print(f'  {c.name}')
    total = Course.objects.filter(course_type=ct).count()
    print(f'  ... ({total} total)')
