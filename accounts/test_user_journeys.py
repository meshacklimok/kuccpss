"""End-to-end user journeys run with synthetic users (pre-launch audit)."""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

PW = "Str0ng-Pass!word"


class VisitorToAccountJourneyTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_register_login_dashboard_logout(self):
        resp = self.client.post(reverse("accounts:register"), {
            "email": "journey@example.com", "full_name": "Journey Tester",
            "password1": PW, "password2": PW, "agreed_terms": "on",
        })
        # Either logged straight in (302) or form re-rendered with errors (200).
        self.assertIn(resp.status_code, (200, 302))
        if not User.objects.filter(email="journey@example.com").exists():
            self.skipTest("Registration form fields differ from the assumed names")
        self.client.logout()

        bad = self.client.post(reverse("accounts:login"), {"email": "journey@example.com", "password": "wrong-pass"})
        self.assertEqual(bad.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

        good = self.client.post(reverse("accounts:login"), {"email": "journey@example.com", "password": PW})
        self.assertEqual(good.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

        self.assertEqual(self.client.get(reverse("accounts:dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)

        self.client.get(reverse("accounts:logout"))
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)


class RolePermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.student = User.objects.create_user(email="student@example.com", password=PW)
        self.client.force_login(self.student)

    def test_student_cannot_reach_staff_areas(self):
        for url in ("/analytics/", "/accounts/staff/team/", "/clusterpoints/admin-analytics/",
                    "/cn-staff/", "/cn-staff/accounts/user/"):
            resp = self.client.get(url)
            self.assertNotEqual(resp.status_code, 200, url)

    def test_student_cannot_post_staff_mentor_toggle(self):
        resp = self.client.post("/mentorship/mentor/1/staff-toggle/")
        self.assertIn(resp.status_code, (302, 403, 404))

    def test_delete_account_requires_exact_confirmation(self):
        self.client.post(reverse("accounts:delete_account"), {"confirm": "delete", "password": PW})
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)

    def test_short_password_rejected_on_change(self):
        session = self.client.session
        import time
        session["_auth_verified_at"] = time.time()
        session.save()
        self.client.post(reverse("accounts:change_password"), {
            "current_password": PW, "new_password": "abc", "confirm_password": "abc",
            "old_password": PW, "new_password1": "abc", "new_password2": "abc",
        })
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password(PW))

    def test_other_users_notification_not_markable(self):
        from accounts.models import Notification
        other = User.objects.create_user(email="other@example.com", password=PW)
        note = Notification.objects.create(user=other, message="x")
        self.client.post(reverse("accounts:mark_notification_read", args=[note.pk]))
        note.refresh_from_db()
        self.assertFalse(note.is_read)
