from django.db import migrations


def seed_banner(apps, schema_editor):
    DeadlineBanner = apps.get_model("resources", "DeadlineBanner")
    DeadlineBanner.objects.get_or_create(
        id=1,
        defaults=dict(
            heading_text="⏰ KUCCPS 2026",
            deadline1_label="KUCCPS Portal Opens — Build Your Shortlist Now",
            deadline1_date="2026-07-03T12:00:00+03:00",
            deadline2_label="KUCCPS Application Closes",
            deadline2_date="2026-08-21T23:59:00+03:00",
        ),
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0008_deadlinebanner"),
    ]

    operations = [
        migrations.RunPython(seed_banner, noop),
    ]
