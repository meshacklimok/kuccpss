from django.core.management.base import BaseCommand
from payments.models import PaymentFeature

FEATURES = [
    {
        "feature": "view_cluster_points",
        "label": "View Cluster Points",
        "price": 0,
        "is_enabled": False,
    },
    {
        "feature": "view_eligible_courses",
        "label": "View Eligible Courses",
        "price": 0,
        "is_enabled": False,
    },
    {
        "feature": "premium_career_report",
        "label": "Premium Career Report",
        "price": 50,
        "is_enabled": True,
    },
    {
        "feature": "advanced_analysis",
        "label": "Advanced Career Analysis",
        "price": 149,
        "is_enabled": False,
    },
]


class Command(BaseCommand):
    help = "Create or update PaymentFeature records with default prices"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite price and is_enabled even if the record already exists",
        )

    def handle(self, *args, **options):
        force = options["force"]
        created = updated = skipped = 0

        for spec in FEATURES:
            obj, is_new = PaymentFeature.objects.get_or_create(
                feature=spec["feature"],
                defaults={
                    "label": spec["label"],
                    "price": spec["price"],
                    "is_enabled": spec["is_enabled"],
                },
            )

            if is_new:
                created += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  Created: {obj.label} — KES {obj.price} ({'enabled' if obj.is_enabled else 'disabled'})"
                ))
            elif force:
                obj.label = spec["label"]
                obj.price = spec["price"]
                obj.is_enabled = spec["is_enabled"]
                obj.save()
                updated += 1
                self.stdout.write(self.style.WARNING(
                    f"  Updated: {obj.label} — KES {obj.price} ({'enabled' if obj.is_enabled else 'disabled'})"
                ))
            else:
                skipped += 1
                self.stdout.write(
                    f"  Skipped (already exists): {obj.label} — KES {obj.price}"
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. {created} created, {updated} updated, {skipped} skipped."
        ))
        self.stdout.write(
            "Run with --force to overwrite existing prices."
        )
