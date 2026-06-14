"""
Management command: seed_ttc

Creates the TTC CourseType, seeds all 21 active public Teacher Training Colleges
in Kenya, seeds TTC programmes (PTE, ECDE, SNE, Art & Craft), and links courses
to institutions via CourseOffering.

Run:
    conda run python manage.py seed_ttc
    conda run python manage.py seed_ttc --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, CourseOffering, CourseType
from institutions.models import Institution, InstitutionType


# ── Public TTCs in Kenya ─────────────────────────────────────────────────────
PUBLIC_TTCS = [
    {"name": "Bomet Teachers College",                   "location": "Bomet County",          "abbreviation": "BTC"},
    {"name": "Chuka Teachers College",                   "location": "Tharaka-Nithi County",  "abbreviation": "CTC"},
    {"name": "Eregi Teachers College",                   "location": "Vihiga County",          "abbreviation": "ETC"},
    {"name": "Garissa Teachers College",                 "location": "Garissa County",         "abbreviation": "GTC"},
    {"name": "Highridge Teachers College",               "location": "Nairobi County",         "abbreviation": "HTC"},
    {"name": "Kagumo Teachers College",                  "location": "Nyeri County",           "abbreviation": "KagumoTC"},
    {"name": "Kakamega Teachers College",                "location": "Kakamega County",        "abbreviation": "KakTC"},
    {"name": "Kamwenja Teachers College",                "location": "Nyeri County",           "abbreviation": "KamTC"},
    {"name": "Kenya Science and Teachers College",       "location": "Nairobi County",         "abbreviation": "KSTC"},
    {"name": "Kitui Teachers College",                   "location": "Kitui County",           "abbreviation": "KitTC"},
    {"name": "Lugari Teachers College",                  "location": "Kakamega County",        "abbreviation": "LTC"},
    {"name": "Machakos Teachers College",                "location": "Machakos County",        "abbreviation": "MachTC"},
    {"name": "Meru Teachers College",                    "location": "Meru County",            "abbreviation": "MeruTC"},
    {"name": "Migori Teachers College",                  "location": "Migori County",          "abbreviation": "MigTC"},
    {"name": "Mosoriot Teachers College",                "location": "Nandi County",           "abbreviation": "MosoTC"},
    {"name": "Muranga Teachers College",                 "location": "Murang'a County",        "abbreviation": "MurTC"},
    {"name": "Nairobi Teachers College",                 "location": "Nairobi County",         "abbreviation": "NaiTC"},
    {"name": "Ramogi Teachers College",                  "location": "Kisumu County",          "abbreviation": "RTC"},
    {"name": "Shanzu Teachers College",                  "location": "Mombasa County",         "abbreviation": "STC"},
    {"name": "Tambach Teachers College",                 "location": "Elgeyo Marakwet County", "abbreviation": "TambTC"},
    {"name": "Thogoto Teachers College",                 "location": "Kiambu County",          "abbreviation": "ThTC"},
]

# ── TTC Programmes ──────────────────────────────────────────────────────────
# All offered at every public TTC unless specified.
# minimum_mean_grade follows KUCCPS placement criteria:
#   PTE Diploma → C  (mean grade C plain, 2 years)
#   ECDE Certificate → D+
#   SNE Diploma → C-
#   Art & Craft → C-
TTC_COURSES = [
    {
        "name": "Diploma in Primary Teacher Education",
        "minimum_mean_grade": "C",
        "description": (
            "A two-year programme that prepares students to teach in Kenya's primary schools. "
            "Leads to a P1 teaching certificate recognised by the Teachers Service Commission (TSC)."
        ),
        "all_institutions": True,
    },
    {
        "name": "Certificate in Early Childhood Development Education",
        "minimum_mean_grade": "D+",
        "description": (
            "Prepares students to work with children aged 3–8 years in pre-primary schools "
            "and ECD centres across Kenya."
        ),
        "all_institutions": True,
    },
    {
        "name": "Diploma in Special Needs Education",
        "minimum_mean_grade": "C-",
        "description": (
            "Equips teachers to work with learners with visual, hearing, physical, or "
            "intellectual disabilities in inclusive or special schools."
        ),
        "institutions": [
            "Kenya Science and Teachers College",
            "Highridge Teachers College",
            "Machakos Teachers College",
            "Kagumo Teachers College",
            "Eregi Teachers College",
            "Kamwenja Teachers College",
        ],
    },
    {
        "name": "Certificate in Art and Craft Education",
        "minimum_mean_grade": "C-",
        "description": (
            "Trains teachers to deliver art, craft, and design lessons in primary schools. "
            "Offered at select TTCs with specialist art facilities."
        ),
        "institutions": [
            "Kenya Science and Teachers College",
            "Highridge Teachers College",
            "Shanzu Teachers College",
            "Ramogi Teachers College",
            "Tambach Teachers College",
        ],
    },
]


class Command(BaseCommand):
    help = "Seed TTC CourseType, institutions, programmes, and course-institution links."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing to DB.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        prefix = "[DRY RUN] " if dry else ""

        self.stdout.write("=" * 60)
        self.stdout.write(f"{prefix}seed_ttc — Teacher Training Colleges")
        self.stdout.write("=" * 60)

        with transaction.atomic():
            # ── 1. Ensure TTC CourseType ────────────────────────────────────
            ct, created = CourseType.objects.get_or_create(
                name="TTC",
                defaults={
                    "description": (
                        "Teacher Training College programmes accredited by the Teachers "
                        "Service Commission (TSC) and offered at public TTCs across Kenya."
                    ),
                    "icon": "fa-solid fa-chalkboard-teacher",
                    "color_code": "#059669",
                },
            )
            action = "Created" if created else "Found"
            self.stdout.write(self.style.SUCCESS(f"\n{prefix}{action} CourseType: TTC (slug={ct.slug!r})"))

            # ── 2. Ensure TTC InstitutionType ───────────────────────────────
            ttc_itype = InstitutionType.objects.filter(name="TTC").first()
            if not ttc_itype:
                ttc_itype = InstitutionType(
                    name="TTC",
                    description="Public Teacher Training Colleges accredited by the TSC.",
                    icon="fa-solid fa-school",
                    color_code="#059669",
                )
                if not dry:
                    ttc_itype.save()
                self.stdout.write(self.style.SUCCESS(f"{prefix}Created InstitutionType: TTC"))
            else:
                self.stdout.write(f"  Found InstitutionType: TTC (id={ttc_itype.id})")

            # ── 3. Seed institutions ────────────────────────────────────────
            inst_map: dict[str, Institution] = {}
            new_insts = 0
            for data in PUBLIC_TTCS:
                inst = Institution.objects.filter(name=data["name"]).first()
                if inst:
                    inst_map[data["name"]] = inst
                    self.stdout.write(f"  Found: {data['name']}")
                else:
                    inst = Institution(
                        name=data["name"],
                        abbreviation=data["abbreviation"],
                        institution_type=ttc_itype,
                        location=data["location"],
                        description=f"Public Teacher Training College — {data['location']}.",
                    )
                    if not dry:
                        inst.save()
                    inst_map[data["name"]] = inst
                    new_insts += 1
                    self.stdout.write(self.style.SUCCESS(f"  {prefix}Created institution: {data['name']}"))

            self.stdout.write(self.style.SUCCESS(
                f"\n{prefix}Institutions: {new_insts} created, {len(PUBLIC_TTCS) - new_insts} already existed"
            ))

            # ── 4. Build full institution list for "all_institutions" courses ──
            all_inst_objs = [inst_map[d["name"]] for d in PUBLIC_TTCS if d["name"] in inst_map]

            # ── 5. Seed courses and link institutions ───────────────────────
            new_courses   = 0
            new_offerings = 0

            for cdata in TTC_COURSES:
                course = Course.objects.filter(name=cdata["name"], course_type=ct).first()
                if not course:
                    course = Course(
                        name=cdata["name"],
                        course_type=ct,
                        minimum_mean_grade=cdata["minimum_mean_grade"],
                        description=cdata["description"],
                    )
                    if not dry:
                        course.save()
                    new_courses += 1
                    self.stdout.write(self.style.SUCCESS(f"\n  {prefix}Created course: {cdata['name']}"))
                else:
                    self.stdout.write(f"\n  Found course: {cdata['name']}")

                # Determine target institutions
                if cdata.get("all_institutions"):
                    target_insts = all_inst_objs
                else:
                    target_insts = [
                        inst_map[n] for n in cdata.get("institutions", []) if n in inst_map
                    ]

                for inst in target_insts:
                    if dry:
                        new_offerings += 1
                        continue
                    _, offering_created = CourseOffering.objects.get_or_create(
                        course=course,
                        institution=inst,
                    )
                    if offering_created:
                        new_offerings += 1

                self.stdout.write(
                    f"    → {len(target_insts)} institution(s) linked"
                )

            # ── 6. Summary ──────────────────────────────────────────────────
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS(
                f"{prefix}Done.\n"
                f"  CourseType TTC: {'created' if ct.pk else 'pending'}\n"
                f"  Institutions:   {new_insts} new\n"
                f"  Courses:        {new_courses} new\n"
                f"  Offerings:      {new_offerings} new"
            ))

            if dry:
                transaction.set_rollback(True)
