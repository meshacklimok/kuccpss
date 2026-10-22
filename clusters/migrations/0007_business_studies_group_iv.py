from django.db import migrations, models


def move_business_studies(apps, schema_editor, new_group='IV', old_group='V'):
    Subject = apps.get_model('clusters', 'Subject')
    Subject.objects.filter(name='Business Studies', group=old_group).update(group=new_group)


def restore_business_studies(apps, schema_editor):
    move_business_studies(apps, schema_editor, new_group='V', old_group='IV')


class Migration(migrations.Migration):

    dependencies = [
        ('clusters', '0006_db_index_cleanup'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subject',
            name='group',
            field=models.CharField(
                blank=True,
                choices=[
                    ('I', 'Group I – Compulsory'),
                    ('II', 'Group II – Sciences'),
                    ('III', 'Group III – Humanities'),
                    ('IV', 'Group IV – Technical & Applied'),
                    ('V', 'Group V – Languages & Music'),
                ],
                default='',
                help_text='KUCCPS subject group (I–V)',
                max_length=4,
            ),
        ),
        migrations.RunPython(move_business_studies, restore_business_studies),
    ]
