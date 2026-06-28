from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0006_sessionlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionlog',
            name='country',
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name='sessionlog',
            name='region',
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
    ]
