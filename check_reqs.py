import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'kuccpss.settings'
import django; django.setup()
from clusters.models import SubjectGroup, Cluster
from courses.models import Course, CourseType, CourseOffering

# Check SubjectGroup cluster IDs
print("SubjectGroup cluster IDs (sample):")
for sg in SubjectGroup.objects.all()[:5]:
    print(f"  sg.cluster_id={sg.cluster_id}, cluster.name={sg.cluster.name[:40]}, cluster.number={sg.cluster.number}")

print()

# Check what cluster IDs are on degree course offerings
deg = CourseType.objects.filter(name__icontains='Degree').first()
offerings = list(
    CourseOffering.objects
    .filter(course__course_type=deg)
    .select_related('course', 'course__cluster')
    .exclude(cutoff_points__isnull=True)[:20]
)
print("Offering cluster IDs (sample):")
for off in offerings:
    cluster = off.course.cluster
    if cluster:
        print(f"  cluster.id={cluster.id}, cluster.name={cluster.name[:50]}, cluster.number={cluster.number}")
    else:
        print(f"  NO CLUSTER for {off.course.name[:40]}")
