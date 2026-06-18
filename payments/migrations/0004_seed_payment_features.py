from django.db import migrations

FEATURES = [
    ("view_cluster_points",   "View Cluster Points",       0,   False),
    ("view_eligible_courses", "View Eligible Courses",      0,   False),
    ("premium_career_report", "Premium Career Report",     50,   True),
    ("advanced_analysis",     "Advanced Career Analysis", 149,   True),
]


def seed(apps, schema_editor):
    PaymentFeature = apps.get_model("payments", "PaymentFeature")
    for feature, label, price, is_enabled in FEATURES:
        PaymentFeature.objects.get_or_create(
            feature=feature,
            defaults={"label": label, "price": price, "is_enabled": is_enabled},
        )


def unseed(apps, schema_editor):
    PaymentFeature = apps.get_model("payments", "PaymentFeature")
    PaymentFeature.objects.filter(feature__in=[f[0] for f in FEATURES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0003_paymentfeature"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
