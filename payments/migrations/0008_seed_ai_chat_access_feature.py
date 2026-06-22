from django.db import migrations


def seed_ai_chat_access(apps, schema_editor):
    PaymentFeature = apps.get_model('payments', 'PaymentFeature')
    PaymentFeature.objects.get_or_create(
        feature='ai_chat_access',
        defaults={
            'label': 'AI Chat Top-Up',
            'price': 50,       # default KES 50 — change freely in Admin → Payments → Payment Features
            'is_enabled': True,
        },
    )


def remove_ai_chat_access(apps, schema_editor):
    PaymentFeature = apps.get_model('payments', 'PaymentFeature')
    PaymentFeature.objects.filter(feature='ai_chat_access').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0007_add_ai_chat_access_feature'),
    ]

    operations = [
        migrations.RunPython(seed_ai_chat_access, remove_ai_chat_access),
    ]
