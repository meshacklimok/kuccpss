from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clusters', '0002_subject_subjectgroup_alter_cluster_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='group',
            field=models.CharField(
                blank=True,
                choices=[
                    ('I',   'Group I – Compulsory'),
                    ('II',  'Group II – Sciences'),
                    ('III', 'Group III – Humanities'),
                    ('IV',  'Group IV – Technical & Applied'),
                    ('V',   'Group V – Languages, Business & Music'),
                ],
                default='',
                help_text='KUCCPS subject group (I–V)',
                max_length=4,
            ),
        ),
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['group'], name='clusters_su_group_idx'),
        ),
    ]
