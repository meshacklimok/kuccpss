"""
Creates 5 approved test mentor accounts with time slots so the directory is populated.
Run once: python manage.py seed_test_mentors

Re-running is safe — existing emails are skipped.
"""
from datetime import date, timedelta, time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from courses.models import Course
from institutions.models import Institution
from mentorship.models import MentorProfile, TimeSlot

User = get_user_model()

MENTORS = [
    {
        "full_name": "Brian Otieno",
        "email": "brian.mentor@test.careernext.co.ke",
        "institution_id": 70,   # University of Nairobi
        "course_id": 379,       # BSc Applied Computer Science
        "year": 3,
        "bio": (
            "3rd-year Computer Science student at UoN. I can help you understand what CS "
            "really involves — the maths, the coding bootcamps, the job market, and which "
            "units to take seriously. Happy to share honest advice about campus life and "
            "industry internship placements I've been through."
        ),
        "whatsapp": "+254712000001",
    },
    {
        "full_name": "Amina Hassan",
        "email": "amina.mentor@test.careernext.co.ke",
        "institution_id": 28,   # Kenyatta University
        "course_id": 68,        # Bachelor of Medicine & Surgery (MBChB)
        "year": 4,
        "bio": (
            "4th-year Medicine student at KU. Pre-med can feel intimidating — let me walk "
            "you through KCSE cluster requirements, what the first two years feel like, "
            "and how to survive anatomy. I can also speak to elective rotations and the "
            "difference between public and private medical schools."
        ),
        "whatsapp": "+254712000002",
    },
    {
        "full_name": "Kevin Mwangi",
        "email": "kevin.mentor@test.careernext.co.ke",
        "institution_id": 20,   # JKUAT
        "course_id": 55,        # BSc Agricultural & Bio-Systems Engineering
        "year": 2,
        "bio": (
            "2nd-year Agri-Engineering student at JKUAT. If you're curious about engineering "
            "that combines food, environment, and machines, this course is underrated. I'll "
            "tell you the exact cluster points needed, the practical lab life, and the "
            "government sponsorship process for engineering courses."
        ),
        "whatsapp": "+254712000003",
    },
    {
        "full_name": "Grace Wanjiku",
        "email": "grace.mentor@test.careernext.co.ke",
        "institution_id": 817,  # Strathmore University
        "course_id": 81,        # Bachelor of Laws (LLB)
        "year": 5,
        "bio": (
            "Final-year Law student at Strathmore. Law school is nothing like TV — let me "
            "give you the real picture. I can help with choosing between public and private "
            "law schools, what moots and clinics look like, and what you can do with an LLB "
            "in Kenya beyond court work."
        ),
        "whatsapp": "+254712000004",
    },
    {
        "full_name": "Dennis Kipchoge",
        "email": "dennis.mentor@test.careernext.co.ke",
        "institution_id": 44,   # Moi University
        "course_id": 77,        # BSc Nursing and Public Health
        "year": 3,
        "bio": (
            "3rd-year Nursing student at Moi University. Nursing is one of the most "
            "in-demand courses in Kenya and abroad. Ask me about clinical attachments, "
            "the difference between Nursing at a public vs KMTC, NCLEX pathways for "
            "those eyeing the USA/UK, and what working conditions are actually like."
        ),
        "whatsapp": "+254712000005",
    },
]

# Future dates: next 7 days starting tomorrow
def _dates():
    today = date.today()
    return [today + timedelta(days=d) for d in range(1, 8)]

SLOT_TIMES = [time(9, 0), time(14, 0), time(17, 0)]


class Command(BaseCommand):
    help = "Seed 5 approved test mentor profiles with time slots"

    def handle(self, *args, **options):
        dates = _dates()
        created = 0
        skipped = 0

        for m in MENTORS:
            if User.objects.filter(email=m["email"]).exists():
                self.stdout.write(f"  skip (exists): {m['email']}")
                skipped += 1
                continue

            # Create user
            user = User.objects.create_user(
                email=m["email"],
                password="testpass123",
                full_name=m["full_name"],
            )

            # Resolve FK objects
            try:
                course = Course.objects.get(pk=m["course_id"])
            except Course.DoesNotExist:
                course = Course.objects.first()

            try:
                institution = Institution.objects.get(pk=m["institution_id"])
            except Institution.DoesNotExist:
                institution = Institution.objects.filter(
                    institution_type__name__icontains="university"
                ).first()

            # Create approved mentor profile
            profile = MentorProfile.objects.create(
                user=user,
                course=course,
                institution=institution,
                year_of_study=m["year"],
                bio=m["bio"],
                whatsapp=m["whatsapp"],
                is_approved=True,
                is_active=True,
            )

            # Add 3 slots across the next 3 days
            for i, day in enumerate(dates[:3]):
                slot_time = SLOT_TIMES[i % len(SLOT_TIMES)]
                TimeSlot.objects.create(mentor=profile, date=day, start_time=slot_time)

            self.stdout.write(self.style.SUCCESS(
                f"  OK: {m['full_name']} ({course.name[:40]}) @ {institution.name}"
            ))
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Created: {created}  Skipped: {skipped}"
        ))
        self.stdout.write(
            "\nLogin credentials for all test mentors:\n"
            "  Password: testpass123\n"
            "  Emails:   see list above\n"
        )
