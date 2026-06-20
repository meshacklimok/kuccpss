from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("career", "0007_growth_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIKnowledgeEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question",   models.CharField(max_length=500)),
                ("answer",     models.TextField(help_text="The verified, factual answer the AI will use")),
                ("keywords",   models.CharField(blank=True, max_length=500, help_text="Comma-separated search words")),
                ("category",   models.CharField(
                    choices=[
                        ("grade_career",    "Grade → Career"),
                        ("interest_career", "Interest → Career"),
                        ("course_info",     "Course Explanation"),
                        ("career_outcome",  "Career Outcomes & Salary"),
                        ("admission",       "University & Admission"),
                        ("comparison",      "Comparisons"),
                        ("decision",        "Decision Help"),
                        ("future_trends",   "Future & Trends"),
                        ("pathway",         "Pathways (Degree/Diploma/TVET)"),
                        ("kuccps",          "KUCCPS Process"),
                        ("general",         "General"),
                    ],
                    default="general",
                    max_length=30,
                )),
                ("is_active",  models.BooleanField(default=True)),
                ("order",      models.PositiveIntegerField(default=0, help_text="Lower = shown first in admin")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name":        "AI Knowledge Entry",
                "verbose_name_plural": "AI Knowledge Base",
                "ordering":            ["category", "order", "id"],
            },
        ),
    ]
