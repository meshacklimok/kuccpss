"""
Management command: fix_institution_types

Cleans up institution type data:
  1. Deletes test-data institution "uon" and its course "data science"
  2. Removes the "Univesity" (typo) InstitutionType
  3. Removes the empty "TVET" InstitutionType (duplicate / placeholder)
  4. Removes the empty "University" CourseType (test data, not the real Degree type)
  5. Adds well-known Kenyan private universities to the Private University type
  6. Updates icon/color for TTC InstitutionType if missing

Run:
    conda run python manage.py fix_institution_types
    conda run python manage.py fix_institution_types --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from institutions.models import Institution, InstitutionType
from courses.models import Course, CourseType


# Well-known Kenyan private universities to seed
PRIVATE_UNIVERSITIES = [
    {"name": "United States International University - Africa", "abbreviation": "USIU-A",  "location": "Nairobi"},
    {"name": "Strathmore University",                           "abbreviation": "SU",       "location": "Nairobi"},
    {"name": "Catholic University of Eastern Africa",           "abbreviation": "CUEA",     "location": "Nairobi"},
    {"name": "Daystar University",                              "abbreviation": "DU",       "location": "Nairobi"},
    {"name": "Africa Nazarene University",                      "abbreviation": "ANU",      "location": "Kajiado County"},
    {"name": "Presbyterian University of East Africa",          "abbreviation": "PUEA",     "location": "Nakuru County"},
    {"name": "Pan Africa Christian University",                 "abbreviation": "PACU",     "location": "Nairobi"},
    {"name": "Aga Khan University",                             "abbreviation": "AKU",      "location": "Nairobi"},
    {"name": "St. Paul's University",                           "abbreviation": "SPU",      "location": "Kiambu County"},
    {"name": "Mount Kenya University",                          "abbreviation": "MKU",      "location": "Thika, Kiambu County"},
    {"name": "Kenya Methodist University",                      "abbreviation": "KeMU",     "location": "Meru County"},
    {"name": "Kabarak University",                              "abbreviation": "KabarakU", "location": "Nakuru County"},
    {"name": "Africa International University",                 "abbreviation": "AIU",      "location": "Nairobi"},
    {"name": "Scott Christian University",                      "abbreviation": "SCU",      "location": "Machakos County"},
    {"name": "Riara University",                                "abbreviation": "RU",       "location": "Nairobi"},
    {"name": "KCA University",                                  "abbreviation": "KCAU",     "location": "Nairobi"},
    {"name": "Zetech University",                               "abbreviation": "ZU",       "location": "Nairobi"},
    {"name": "Pioneer International University",                "abbreviation": "PIU",      "location": "Nairobi"},
    {"name": "Management University of Africa",                 "abbreviation": "MUA",      "location": "Nairobi"},
    {"name": "Adventist University of Africa",                  "abbreviation": "AUA",      "location": "Nairobi"},
]


class Command(BaseCommand):
    help = "Fix institution type inconsistencies and add private universities."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        prefix = "[DRY RUN] " if dry else ""

        self.stdout.write("=" * 60)
        self.stdout.write(f"{prefix}fix_institution_types")
        self.stdout.write("=" * 60)

        with transaction.atomic():
            # ── 1. Delete test course "data science" and its offerings ───────
            test_course = Course.objects.filter(name="data science").first()
            if test_course:
                if not dry:
                    test_course.offerings.all().delete()
                    test_course.delete()
                self.stdout.write(self.style.SUCCESS(f"{prefix}Deleted test course: data science"))

            # ── 2. Delete test institution "uon" ─────────────────────────────
            test_inst = Institution.objects.filter(name="uon").first()
            if test_inst:
                if not dry:
                    test_inst.offerings.all().delete()
                    test_inst.delete()
                self.stdout.write(self.style.SUCCESS(f"{prefix}Deleted test institution: uon"))

            # ── 3. Delete "Univesity" InstitutionType (typo) ─────────────────
            typo_type = InstitutionType.objects.filter(name="Univesity").first()
            if typo_type:
                if not dry:
                    typo_type.delete()
                self.stdout.write(self.style.SUCCESS(f"{prefix}Deleted InstitutionType: Univesity (typo)"))

            # ── 4. Delete empty "TVET" InstitutionType ───────────────────────
            empty_tvet = InstitutionType.objects.filter(name="TVET").first()
            if empty_tvet:
                count = Institution.objects.filter(institution_type=empty_tvet).count()
                if count == 0:
                    if not dry:
                        empty_tvet.delete()
                    self.stdout.write(self.style.SUCCESS(f"{prefix}Deleted empty InstitutionType: TVET"))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"  TVET type has {count} institutions — not deleted. Reassign first."
                    ))

            # ── 5. Delete empty "University" CourseType (test artifact) ──────
            uni_ct = CourseType.objects.filter(name="University").first()
            if uni_ct and uni_ct.course_set.count() <= 1:
                if not dry:
                    uni_ct.categories.all().delete()
                    uni_ct.course_set.all().delete()
                    uni_ct.delete()
                self.stdout.write(self.style.SUCCESS(f"{prefix}Deleted test CourseType: University"))

            # ── 6. Seed Private Universities ─────────────────────────────────
            priv_type = InstitutionType.objects.filter(name="Private University").first()
            if not priv_type:
                self.stdout.write(self.style.WARNING("  Private University InstitutionType not found — skipping."))
            else:
                # Update icon/color if missing
                changed = False
                if not priv_type.icon:
                    priv_type.icon = "fa-solid fa-university"
                    changed = True
                if not priv_type.color_code:
                    priv_type.color_code = "#7c3aed"
                    changed = True
                if changed and not dry:
                    priv_type.save()

                added = 0
                for data in PRIVATE_UNIVERSITIES:
                    exists = Institution.objects.filter(name=data["name"]).exists()
                    if not exists:
                        inst = Institution(
                            name=data["name"],
                            abbreviation=data["abbreviation"],
                            institution_type=priv_type,
                            location=data["location"],
                        )
                        if not dry:
                            inst.save()
                        added += 1
                        self.stdout.write(self.style.SUCCESS(f"  {prefix}Added private university: {data['name']}"))
                    else:
                        self.stdout.write(f"  Exists: {data['name']}")

                self.stdout.write(self.style.SUCCESS(f"\n{prefix}Added {added} private universities"))

            # ── 7. Ensure Public University has proper icon/color ─────────────
            pub_type = InstitutionType.objects.filter(name="Public University").first()
            if pub_type:
                changed = False
                if not pub_type.icon:
                    pub_type.icon = "fa-solid fa-university"
                    changed = True
                if not pub_type.color_code:
                    pub_type.color_code = "#1d4ed8"
                    changed = True
                if changed and not dry:
                    pub_type.save()
                    self.stdout.write(self.style.SUCCESS("  Updated Public University icon/color"))

            # ── 8. Ensure TTC has proper icon/color ──────────────────────────
            ttc_type = InstitutionType.objects.filter(name="TTC").first()
            if ttc_type and not ttc_type.color_code and not dry:
                ttc_type.color_code = "#059669"
                ttc_type.icon = "fa-solid fa-chalkboard-teacher"
                ttc_type.save()
                self.stdout.write(self.style.SUCCESS("  Updated TTC InstitutionType icon/color"))

            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS(f"{prefix}Done."))

            if dry:
                transaction.set_rollback(True)
