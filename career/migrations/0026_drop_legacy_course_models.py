# Drops the legacy career course models, superseded by courses.Course /
# CourseOffering (see docs/DECISIONS.md #4). Whole-model deletes, children
# before parents, so each table goes with its M2M tables, indexes and constraints.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("career", "0025_non_degree_submission_lock"),
    ]

    operations = [
        migrations.DeleteModel(name="CareerInsight"),
        migrations.DeleteModel(name="StudentCourseMatch"),
        migrations.DeleteModel(name="AIRecommendation"),
        migrations.DeleteModel(name="CourseCutoff"),
        migrations.DeleteModel(name="CourseCutoffHistory"),
        migrations.DeleteModel(name="Course"),
        migrations.DeleteModel(name="CourseCategory"),
        migrations.DeleteModel(name="University"),
        migrations.DeleteModel(name="TVETCourse"),
        migrations.DeleteModel(name="TVETCategory"),
        migrations.DeleteModel(name="KMTCourse"),
        migrations.DeleteModel(name="KMTCampus"),
        migrations.DeleteModel(name="TTCCourse"),
        migrations.DeleteModel(name="TTCCollege"),
        migrations.DeleteModel(name="KCSEGrade"),
    ]
