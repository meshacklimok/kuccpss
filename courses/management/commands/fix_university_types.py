"""
Management command: fix_university_types

The initial university seed put ALL universities (public + private) under the
"Public University" InstitutionType. This command:

  1. Deletes the 20 duplicate private-university records added in the last
     session (they're case-different copies of entries already in Public Uni).
  2. Moves genuinely private universities from "Public University" to
     "Private University" — based on Kenya Commission for University Education
     (CUE) classification (chartered private universities).

Run:
    conda run python manage.py fix_university_types
    conda run python manage.py fix_university_types --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from institutions.models import Institution, InstitutionType


# These are the exact "name" values added by fix_institution_types.py in the
# last session. They duplicate (case-different) entries already in Public Uni.
DUPLICATE_PRIVATE_NAMES = {
    "United States International University - Africa",
    "Strathmore University",
    "Catholic University of Eastern Africa",
    "Daystar University",
    "Africa Nazarene University",
    "Presbyterian University of East Africa",
    "Pan Africa Christian University",
    "Aga Khan University",
    "St. Paul's University",
    "Mount Kenya University",
    "Kenya Methodist University",
    "Kabarak University",
    "Africa International University",
    "Scott Christian University",
    "Riara University",
    "KCA University",
    "Zetech University",
    "Pioneer International University",
    "Management University of Africa",
    "Adventist University of Africa",
}

# Names (as they appear in the DB, all-caps from initial seed) that are
# private universities wrongly sitting under "Public University".
# Source: Kenya Commission for University Education (CUE) chartered private list.
PRIVATE_IN_PUBLIC = {
    "AFRICA INTERNATIONAL UNIVERSITY",
    "AFRICA NAZARENE UNIVERSITY",
    "CATHOLIC UNIVERSITY OF EASTERN AFRICA",
    "DAYSTAR UNIVERSITY",
    "GREAT LAKES UNIVERSITY OF KISUMU",
    "GRETSA UNIVERSITY",
    "INTERNATIONAL LEADERSHIP UNIVERSITY",
    "ISLAMIC UNIVERSITY OF KENYA",
    "KCA UNIVERSITY",
    "KABARAK UNIVERSITY",
    "KAIMOSI FRIENDS UNIVERSITY",
    "KENYA ASSEMBLIES OF GOD EAST UNIVERSITY",
    "KENYA HIGHLANDS EVANGELICAL UNIVERSITY",
    "KENYA METHODIST UNIVERSITY",
    "KIRIRI WOMENS UNIVERSITY OF SCIENCE AND TECHNOLOGY",
    "LUKENYA UNIVERSITY",
    "MARIST INTERNATIONAL UNIVERSITY COLLEGE",
    "MANAGEMENT UNIVERSITY OF AFRICA",
    "MOUNT KENYA UNIVERSITY",
    "PAN AFRICA CHRISTIAN UNIVERSITY",
    "PRESBYTERIAN UNIVERSITY OF EAST AFRICA",
    "RIARA UNIVERSITY",
    "SCOTT CHRISTIAN UNIVERSITY",
    "ST PAULS UNIVERSITY",
    "STRATHMORE UNIVERSITY",
    "TANGAZA UNIVERSITY",
    "THE EAST AFRICAN UNIVERSITY",
    "UNITED STATES INTERNATIONAL UNIVERSITY - AFRICA",
    "UNIVERSITY OF EASTERN AFRICA, BARATON",
    "UZIMA UNIVERSITY",
    "ZETECH UNIVERSITY",
    "AGA KHAN UNIVERSITY",
    "PIONEER INTERNATIONAL UNIVERSITY",
    "ADVENTIST UNIVERSITY OF AFRICA",
    "AMREF INTERNATIONAL UNIVERSITY",
}


class Command(BaseCommand):
    help = "Reclassify universities from Public to Private where applicable."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        prefix = "[DRY RUN] " if dry else ""

        self.stdout.write("=" * 60)
        self.stdout.write(f"{prefix}fix_university_types")
        self.stdout.write("=" * 60)

        with transaction.atomic():
            pub_type  = InstitutionType.objects.get(name="Public University")
            priv_type = InstitutionType.objects.get(name="Private University")

            # ── 1. Delete duplicate private-university records ────────────────
            deleted = 0
            for name in DUPLICATE_PRIVATE_NAMES:
                inst = Institution.objects.filter(
                    name=name, institution_type=priv_type
                ).first()
                if inst:
                    if not dry:
                        inst.delete()
                    deleted += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  {prefix}Deleted duplicate: {name!r}"
                    ))

            self.stdout.write(self.style.SUCCESS(
                f"\n{prefix}Deleted {deleted} duplicate private-uni records\n"
            ))

            # ── 2. Move misclassified institutions from Public → Private ──────
            moved = 0
            for name in sorted(PRIVATE_IN_PUBLIC):
                inst = Institution.objects.filter(
                    name__iexact=name, institution_type=pub_type
                ).first()
                if inst:
                    if not dry:
                        inst.institution_type = priv_type
                        inst.save(update_fields=["institution_type"])
                    moved += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  {prefix}Moved to Private: {inst.name}"
                    ))
                else:
                    self.stdout.write(f"  Not found in Public Uni: {name!r}")

            # ── 3. Summary ────────────────────────────────────────────────────
            self.stdout.write("\n" + "=" * 60)
            pub_count  = Institution.objects.filter(institution_type=pub_type).count()
            priv_count = Institution.objects.filter(institution_type=priv_type).count()
            self.stdout.write(self.style.SUCCESS(
                f"{prefix}Done.\n"
                f"  Deleted duplicates: {deleted}\n"
                f"  Moved to Private:   {moved}\n"
                f"  Public University:  {pub_count} institutions (after)\n"
                f"  Private University: {priv_count} institutions (after)"
            ))

            if dry:
                transaction.set_rollback(True)
