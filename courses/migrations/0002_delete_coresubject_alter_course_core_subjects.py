from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clusters", "0002_subject_subjectgroup_alter_cluster_options_and_more"),
        ("courses", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(
            name="CoreSubject",
        ),
        migrations.RemoveField(model_name="course", name="core_subjects"),
        migrations.AddField(
            model_name="course",
            name="core_subjects",
            field=models.ManyToManyField(
                blank=True, related_name="courses", to="clusters.subject"
            ),
        ),
    ]
