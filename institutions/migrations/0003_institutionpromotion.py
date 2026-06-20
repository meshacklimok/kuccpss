from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("institutions", "0002_add_abbreviation"),
    ]

    operations = [
        migrations.CreateModel(
            name="InstitutionPromotion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("institution", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="promotion",
                    to="institutions.institution",
                )),
                ("tier", models.CharField(
                    choices=[("featured", "Featured Partner"), ("scholarship", "Scholarship Alert")],
                    default="featured",
                    max_length=20,
                )),
                ("tagline", models.CharField(blank=True, max_length=200, help_text="Short marketing message shown on the platform")),
                ("banner_image", models.ImageField(blank=True, null=True, upload_to="institution_banners/")),
                ("scholarship_title", models.CharField(blank=True, max_length=200)),
                ("scholarship_description", models.TextField(blank=True)),
                ("scholarship_amount", models.CharField(blank=True, max_length=100, help_text="e.g. Full tuition, KES 50,000")),
                ("scholarship_deadline", models.DateField(blank=True, null=True)),
                ("scholarship_link", models.URLField(blank=True, null=True, help_text="External apply/learn-more link")),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("contact_name", models.CharField(blank=True, max_length=100)),
                ("contact_email", models.EmailField(blank=True, max_length=254)),
                ("contact_phone", models.CharField(blank=True, max_length=50)),
                ("notes", models.TextField(blank=True, help_text="Internal notes about this partnership deal")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Institution Promotion",
                "verbose_name_plural": "Institution Promotions",
                "ordering": ["end_date"],
            },
        ),
    ]
