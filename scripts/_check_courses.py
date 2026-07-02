import django, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuccpss.settings')
django.setup()

from career.models import Course as C1, CourseCategory as Cat
from courses.models import Course as C2

print('=== career.Course categories ===')
for cat in Cat.objects.all():
    count = C1.objects.filter(category=cat).count()
    print(f'  {cat.name!r}: {count} courses')

print('\n=== career.Course (all, first 30) ===')
for c in C1.objects.select_related('category', 'cluster')[:30]:
    print(f'  [{c.pk}] {c.name!r}  cat={c.category.name}  cluster={c.cluster_id}')
print(f'  Total: {C1.objects.count()}')

print('\n=== courses.Course with cluster (first 20) ===')
for c in C2.objects.filter(cluster__isnull=False).select_related('cluster')[:20]:
    print(f'  [{c.pk}] {c.name!r}  Cluster {c.cluster.number}: {c.cluster.name}')
print(f'  Total with cluster: {C2.objects.filter(cluster__isnull=False).count()}')
print(f'  Total courses.Course: {C2.objects.count()}')
