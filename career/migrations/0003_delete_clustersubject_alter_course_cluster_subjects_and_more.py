from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "career",
            "0002_quizquestion_careerprofile_quizoption_quizsubmission_and_more",
        ),
        ("clusters", "0002_subject_subjectgroup_alter_cluster_options_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ClusterSubject",
        ),
        # course.cluster_subjects
        migrations.RemoveField(model_name="course", name="cluster_subjects"),
        migrations.AddField(
            model_name="course",
            name="cluster_subjects",
            field=models.ManyToManyField(
                blank=True, related_name="career_courses", to="clusters.subject"
            ),
        ),
        # kmtcourse.required_subjects
        migrations.RemoveField(model_name="kmtcourse", name="required_subjects"),
        migrations.AddField(
            model_name="kmtcourse",
            name="required_subjects",
            field=models.ManyToManyField(
                blank=True, related_name="kmt_courses", to="clusters.subject"
            ),
        ),
        # ttccourse.required_subjects
        migrations.RemoveField(model_name="ttccourse", name="required_subjects"),
        migrations.AddField(
            model_name="ttccourse",
            name="required_subjects",
            field=models.ManyToManyField(
                blank=True, related_name="ttc_courses", to="clusters.subject"
            ),
        ),
        # tvetcourse.required_subjects
        migrations.RemoveField(model_name="tvetcourse", name="required_subjects"),
        migrations.AddField(
            model_name="tvetcourse",
            name="required_subjects",
            field=models.ManyToManyField(
                blank=True, related_name="tvet_courses", to="clusters.subject"
            ),
        ),
    ]
