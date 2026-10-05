"""
Rename the old "KUCCPSS" product name to "CareerNext" in seeded content
(FAQs, success stories, articles, site settings, AI knowledge base, salary
sources), and replace the outdated cluster-points formula in the FAQ.

Only the upper-case brand word is replaced, so lower-case social handles
(e.g. instagram_handle = "kuccpss") and the official "KUCCPS" name are untouched.
"""
import re

from django.db import migrations

BRAND = re.compile(r"\bKUCCPSS\b")
OLD_EMAIL = "info@kuccpss.co.ke"
NEW_EMAIL = "hello@careernext.co.ke"

FORMULA_QUESTION = "How are cluster points calculated?"
FORMULA_ANSWER = (
    "CareerNext uses the KUCCPS weighted formula:\n\n"
    "Cluster Points = 48 × √( (cluster_marks / 400) × (aggregate / 84) )\n\n"
    "Where cluster_marks is the sum of the midpoint raw marks for your 4 cluster "
    "subjects (A = 90.2, B = 66, C = 50 and so on, out of 400), and aggregate is "
    "your KCSE total out of 84. The maximum possible cluster points score is 48."
)

CLUSTERS_QUESTION = "What are the 18 KUCCPS clusters?"
CLUSTERS_ANSWER = (
    "KUCCPS groups degree programmes into 18 clusters (C1–C18). Each cluster uses "
    "4 cluster subjects relevant to its field. For example, Cluster 13 (Medicine, "
    "Nursing, Health Sciences) uses Biology, Chemistry, Mathematics or Physics, and "
    "one other subject. You can view all 18 clusters and their subject compositions "
    "on the Clusters page."
)

TARGETS = [
    ("resources", "FAQItem", ["question", "answer"]),
    ("resources", "SuccessStory", ["quote"]),
    ("resources", "Article", ["author", "content"]),
    ("resources", "SiteSetting", ["value"]),
    ("career", "AIKnowledgeEntry", ["question", "answer"]),
    ("career", "JobMarketData", ["source_name"]),
]


def rebrand(apps, schema_editor):
    for app_label, model_name, fields in TARGETS:
        Model = apps.get_model(app_label, model_name)
        for obj in Model.objects.all().iterator():
            changed = []
            for f in fields:
                old = getattr(obj, f) or ""
                new = BRAND.sub("CareerNext", old).replace(OLD_EMAIL, NEW_EMAIL)
                if new != old:
                    setattr(obj, f, new)
                    changed.append(f)
            if changed:
                obj.save(update_fields=changed)

    FAQItem = apps.get_model("resources", "FAQItem")
    FAQItem.objects.filter(
        question=FORMULA_QUESTION, answer__contains="/ 48"
    ).update(answer=FORMULA_ANSWER)

    FAQItem.objects.filter(question="What are the 20 KUCCPS clusters?").update(
        question=CLUSTERS_QUESTION, answer=CLUSTERS_ANSWER
    )


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0016_db_index_cleanup"),
        ("career", "0025_non_degree_submission_lock"),
    ]

    operations = [
        migrations.RunPython(rebrand, migrations.RunPython.noop),
    ]
