"""
Expert mentors (professionals who advise on any course) and per-mentor session length:
directory placement, booking snapshots, slot overlap, auto-complete, self-edit.
"""
from datetime import date, time, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from mentorship.calendar_utils import generate_ics
from mentorship.models import MentorProfile, MentorshipConfig, MentorshipSession, TimeSlot
from mentorship.tasks import complete_expired_sessions

User = get_user_model()


def _mentor(email, **kwargs):
    user = User.objects.create_user(email=email, password="pass1234", full_name=email.split("@")[0])
    return MentorProfile.objects.create(
        user=user, bio="Bio", whatsapp="+254712345678", is_approved=True, **kwargs,
    )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ExpertMentorTests(TestCase):
    def setUp(self):
        cache.clear()
        self.expert = _mentor(
            "expert@example.com", mentor_type=MentorProfile.EXPERT,
            headline="Career Counsellor", custom_session_price=500,
            custom_mentor_payout=350, custom_session_minutes=45,
        )
        self.student = _mentor("student@example.com")
        self.mentee = User.objects.create_user(email="mentee@example.com", password="pass1234")
        self.day = date.today() + timedelta(days=2)

    def test_directory_pins_experts_and_lists_mentors_without_slots(self):
        resp = self.client.get(reverse("mentorship:directory"), {"q": "zzz-no-match"})
        self.assertEqual(list(resp.context["experts"]), [self.expert])
        self.assertEqual(resp.context["total_count"], 0)

        resp = self.client.get(reverse("mentorship:directory"))
        self.assertEqual(list(resp.context["mentors"]), [self.student])
        self.assertContains(resp, "No slots available. Check back soon")
        self.assertContains(resp, "Career Counsellor")

    def test_students_with_open_slots_listed_first(self):
        busy = _mentor("busy@example.com")
        TimeSlot.objects.create(mentor=busy, date=self.day, start_time="14:00")
        resp = self.client.get(reverse("mentorship:directory"))
        self.assertEqual(list(resp.context["mentors"]), [busy, self.student])

    def test_booking_expert_snapshots_price_length_and_course(self):
        slot = TimeSlot.objects.create(mentor=self.expert, date=self.day, start_time="14:00")
        self.client.force_login(self.mentee)
        self.client.post(reverse("mentorship:book_session", args=[self.expert.pk]), {
            "slot": slot.pk, "mentee_question": "Medicine or pharmacy?",
            "mentee_phone": "0712345678", "course_topic": "  Bachelor of   Pharmacy ",
        })
        session = MentorshipSession.objects.get(mentee=self.mentee)
        self.assertEqual((session.amount, session.mentor_payout, session.duration_minutes), (500, 350, 45))
        self.assertEqual(session.course_topic, "Bachelor of Pharmacy")
        self.assertIn("DTEND", generate_ics(session))
        self.assertEqual(session.end_time, time(14, 45))

    def test_student_booking_uses_global_length_and_has_no_course_field(self):
        MentorshipConfig.objects.update_or_create(pk=1, defaults={"session_minutes": 20})
        slot = TimeSlot.objects.create(mentor=self.student, date=self.day, start_time="14:00")
        self.client.force_login(self.mentee)
        resp = self.client.get(reverse("mentorship:book_session", args=[self.student.pk]))
        self.assertNotIn("course_topic", resp.context["form"].fields)
        self.client.post(reverse("mentorship:book_session", args=[self.student.pk]), {
            "slot": slot.pk, "mentee_question": "Q", "mentee_phone": "0712345678",
        })
        self.assertEqual(MentorshipSession.objects.get(mentee=self.mentee).duration_minutes, 20)

    def test_overlapping_slots_skipped_for_long_sessions(self):
        self.client.force_login(self.expert.user)
        self.client.post(reverse("mentorship:add_slots"), {
            "date": self.day.isoformat(), "times": ["11:00", "12:00"], "custom_time": "11:30",
        })
        times = list(TimeSlot.objects.filter(mentor=self.expert).values_list("start_time", flat=True))
        self.assertEqual(sorted(times), [time(11, 0), time(12, 0)])

    def test_auto_complete_waits_for_session_end(self):
        start = timezone.localtime(timezone.now() - timedelta(minutes=40)).replace(second=0, microsecond=0)
        slot = TimeSlot.objects.create(
            mentor=self.expert, date=start.date(), start_time=start.time(), is_booked=True,
        )
        session = MentorshipSession.objects.create(
            mentor=self.expert, mentee=self.mentee, slot=slot, mentee_question="Q",
            amount=500, mentor_payout=350, duration_minutes=45, status="confirmed",
        )
        self.assertEqual(complete_expired_sessions(), 0)  # ends in 5 min, +15 grace
        MentorshipSession.objects.filter(pk=session.pk).update(duration_minutes=15)
        self.assertEqual(complete_expired_sessions(), 1)

    def test_expert_can_edit_profile_without_course(self):
        self.client.force_login(self.expert.user)
        resp = self.client.post(reverse("mentorship:edit_profile"), {
            "headline": "Senior Career Advisor", "bio": "New bio", "whatsapp": "0712345678",
        })
        self.assertRedirects(resp, reverse("mentorship:dashboard"), fetch_redirect_response=False)
        self.expert.refresh_from_db()
        self.assertEqual(self.expert.headline, "Senior Career Advisor")

    def test_course_page_lists_experts_with_prefilled_booking_link(self):
        from courses.views import _expert_mentors
        self.assertEqual(_expert_mentors(), [self.expert])
        self.client.force_login(self.mentee)
        resp = self.client.get(
            reverse("mentorship:book_session", args=[self.expert.pk]), {"course": "BSc Nursing"},
        )
        self.assertEqual(resp.context["form"].initial["course_topic"], "BSc Nursing")


class CourseNameMatchingTests(TestCase):
    def _rank(self, a, b):
        from mentorship.matching import course_core, match_rank
        return match_rank(course_core(a), course_core(b))

    def test_variations_match(self):
        from mentorship.matching import SAME_CORE, VARIATION
        base = "BACHELOR OF SCIENCE IN DATA SCIENCE"
        self.assertEqual(self._rank(base, "BACHELOR OF SCIENCE DATA SCIENCE"), SAME_CORE)
        self.assertEqual(self._rank(base, "BACHELOR OF DATA SCIENCE"), SAME_CORE)
        self.assertEqual(self._rank(base, "BACHELOR OF DATA SCIENCE AND ANALYTICS"), VARIATION)
        self.assertEqual(self._rank(base, "Bachelor of Dta Science"), VARIATION)
        self.assertEqual(self._rank("BACHELOR OF SCIENCE (NURSING)", "BACHELOR OF NURSING"), SAME_CORE)
        self.assertEqual(
            self._rank("BACHELOR OF APPLIED COMPUTER SCIENCE", "BACHELOR OF SCIENCE (COMPUTER SCIENCE)"), SAME_CORE,
        )

    def test_different_combinations_do_not_match(self):
        base = "BACHELOR OF SCIENCE IN DATA SCIENCE"
        self.assertIsNone(self._rank(base, "BACHELOR OF ECONOMICS AND DATA SCIENCE"))
        self.assertIsNone(self._rank(base, "BACHELOR OF SCIENCE IN MATHEMATICS AND DATA SCIENCE"))
        self.assertIsNone(self._rank("BACHELOR OF SCIENCE", "BACHELOR OF SCIENCE IN SCIENCE EDUCATION"))
        self.assertIsNone(self._rank("BACHELOR OF NURSING", "Diploma in Kenya Registered Nursing"))

    def test_student_mentors_for_course_ranks_exact_then_open_slots(self):
        from courses.models import Course, CourseType
        from mentorship.matching import student_mentors_for_course
        degree = CourseType.objects.create(name="Degree", slug="degree")
        exact_course = Course.objects.create(name="BACHELOR OF SCIENCE IN DATA SCIENCE", course_type=degree)
        variation = Course.objects.create(name="BACHELOR OF DATA SCIENCE AND ANALYTICS", course_type=degree)
        other = Course.objects.create(name="BACHELOR OF ECONOMICS AND DATA SCIENCE", course_type=degree)
        exact = _mentor("exact@example.com", course=exact_course)
        var_open = _mentor("varopen@example.com", course=variation)
        var_closed = _mentor("varclosed@example.com", course=variation)
        _mentor("other@example.com", course=other)
        _mentor("expert2@example.com", mentor_type=MentorProfile.EXPERT, course=exact_course)
        TimeSlot.objects.create(mentor=var_open, date=date.today() + timedelta(days=2), start_time="10:00")

        self.assertEqual(student_mentors_for_course(exact_course), [exact, var_open, var_closed])
        self.assertEqual(student_mentors_for_course(exact_course, limit=1), [exact])


class NewMentorBadgeTests(TestCase):
    def test_badge_only_when_admin_enables_it(self):
        cache.clear()
        on = _mentor("on@example.com", show_new_badge=True)
        _mentor("off@example.com")
        resp = self.client.get(reverse("mentorship:directory"))
        self.assertContains(resp, "New mentor", count=1)
        resp = self.client.get(reverse("mentorship:mentor_profile", args=[on.pk]))
        self.assertContains(resp, "New mentor")


class ExpertBadgeTests(TestCase):
    def test_badge_only_when_admin_enables_it(self):
        cache.clear()
        on = _mentor("on@example.com", show_expert_badge=True)
        off = _mentor("off@example.com", mentor_type=MentorProfile.EXPERT)
        resp = self.client.get(reverse("mentorship:directory"))
        self.assertContains(resp, "mc-expert-badge\"", count=1)
        resp = self.client.get(reverse("mentorship:mentor_profile", args=[on.pk]))
        self.assertContains(resp, "Expert Mentor")
        resp = self.client.get(reverse("mentorship:mentor_profile", args=[off.pk]))
        self.assertNotContains(resp, "bi-patch-check-fill me-1\"></i>Expert Mentor")


class StudentMentorOrderTests(TestCase):
    def test_pinned_first_then_most_sessions(self):
        cache.clear()
        few = _mentor("few@example.com", total_sessions=2)
        many = _mentor("many@example.com", total_sessions=9, average_rating=3)
        rated = _mentor("rated@example.com", total_sessions=0, average_rating=5)
        TimeSlot.objects.create(mentor=rated, date=date.today() + timedelta(days=2), start_time="10:00")
        resp = self.client.get(reverse("mentorship:directory"))
        self.assertEqual(list(resp.context["mentors"]), [many, few, rated])

        rated.is_pinned = True
        rated.save()
        resp = self.client.get(reverse("mentorship:directory"))
        self.assertEqual(list(resp.context["mentors"]), [rated, many, few])


@override_settings(STAFF_2FA_REQUIRED=False)
class StaffToggleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.mentor = _mentor("m@example.com")
        self.url = reverse("mentorship:staff_toggle_flag", args=[self.mentor.pk])

    def test_staff_can_pin_and_badge_from_the_site(self):
        staff = User.objects.create_user(email="staff@example.com", password="pass1234", is_staff=True)
        self.client.force_login(staff)
        with mock.patch("accounts.staff_2fa.session_is_verified", return_value=True):
            resp = self.client.get(reverse("mentorship:directory"))
            self.assertContains(resp, "Pin to top")
            resp = self.client.post(self.url, {"field": "is_pinned", "next": "/mentorship/?page=1"})
            self.assertRedirects(resp, "/mentorship/?page=1", fetch_redirect_response=False)
            self.client.post(self.url, {"field": "show_expert_badge", "next": "https://evil.example.com/"})
        self.mentor.refresh_from_db()
        self.assertTrue(self.mentor.is_pinned)
        self.assertTrue(self.mentor.show_expert_badge)

    def test_students_cannot_toggle_or_see_pin(self):
        self.mentor.is_pinned = True
        self.mentor.save()
        student = User.objects.create_user(email="s@example.com", password="pass1234")
        self.client.force_login(student)
        resp = self.client.post(self.url, {"field": "show_expert_badge"})
        self.assertEqual(resp.status_code, 403)
        for page in (reverse("mentorship:directory"), reverse("mentorship:mentor_profile", args=[self.mentor.pk])):
            resp = self.client.get(page)
            self.assertNotContains(resp, "staff-toggle")
            self.assertNotContains(resp, "Unpin")
            self.assertNotContains(resp, "bi-pin")
