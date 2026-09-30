import time

from django.core.cache import cache
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts import staff_2fa
from accounts.models import StaffTOTPDevice, User


def _code(raw: bytes, at: float | None = None) -> str:
    return staff_2fa._totp(raw).generate(int(at or time.time())).decode()


class StaffTwoFactorTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user(email="staff@example.com", password="Pass1234!x")
        self.staff.is_staff = True
        self.staff.save()
        self.client.force_login(self.staff)

    def _enrol(self) -> bytes:
        raw = staff_2fa.new_secret()
        StaffTOTPDevice.objects.create(
            user=self.staff, secret_encrypted=staff_2fa.encrypt_secret(raw),
            confirmed_at="2026-01-01T00:00:00Z",
        )
        return raw

    def test_unenrolled_staff_redirected_to_setup(self):
        resp = self.client.get("/accounts/dashboard/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:staff_2fa_setup"), resp["Location"])

    def test_enrolled_staff_redirected_to_verify(self):
        self._enrol()
        resp = self.client.get("/cn-staff/")
        self.assertIn(reverse("accounts:staff_2fa_verify"), resp["Location"])

    def test_ajax_gets_403_json(self):
        resp = self.client.get("/accounts/dashboard/", HTTP_ACCEPT="application/json")
        self.assertEqual(resp.status_code, 403)

    def test_setup_flow_enrols_and_unlocks(self):
        self.client.get(reverse("accounts:staff_2fa_setup"))
        raw = staff_2fa.decrypt_secret(self.client.session[staff_2fa.SETUP_SECRET_KEY])
        resp = self.client.post(reverse("accounts:staff_2fa_setup"), {"code": _code(raw), "next": "/cn-staff/"})
        self.assertRedirects(resp, "/cn-staff/", fetch_redirect_response=False)
        self.assertTrue(staff_2fa.has_confirmed_device(self.staff))
        self.assertEqual(self.client.get("/accounts/dashboard/").status_code, 200)

    def test_verify_accepts_valid_code_and_rejects_replay(self):
        raw = self._enrol()
        code = _code(raw)
        resp = self.client.post(reverse("accounts:staff_2fa_verify"), {"code": code, "next": "/cn-staff/"})
        self.assertEqual(resp["Location"], "/cn-staff/")
        # Same code again in a fresh session must be refused (replay).
        self.client.logout()
        self.client.force_login(self.staff)
        resp = self.client.post(reverse("accounts:staff_2fa_verify"), {"code": code})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(staff_2fa.SESSION_KEY, self.client.session)

    def test_wrong_codes_are_rate_limited(self):
        raw = self._enrol()
        for _ in range(staff_2fa.ATTEMPT_LIMIT):
            self.client.post(reverse("accounts:staff_2fa_verify"), {"code": "000000"})
        self.client.post(reverse("accounts:staff_2fa_verify"), {"code": _code(raw)})
        self.assertNotIn(staff_2fa.SESSION_KEY, self.client.session)

    def test_open_redirect_blocked(self):
        raw = self._enrol()
        resp = self.client.post(reverse("accounts:staff_2fa_verify"),
                                {"code": _code(raw), "next": "https://evil.example/"})
        self.assertEqual(resp["Location"], "/cn-staff/")

    def test_students_unaffected(self):
        student = User.objects.create_user(email="s@example.com", password="Pass1234!x")
        self.client.force_login(student)
        self.assertEqual(self.client.get("/accounts/dashboard/").status_code, 200)

    def test_secret_encrypted_at_rest(self):
        raw = self._enrol()
        stored = StaffTOTPDevice.objects.get(user=self.staff).secret_encrypted
        self.assertNotIn(staff_2fa.base32_secret(raw), stored)


class LoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email="victim@example.com", password="RightPass123!")

    def _login(self, password, ip):
        return self.client.post(reverse("accounts:login"),
                                {"email": "victim@example.com", "password": password},
                                REMOTE_ADDR=ip)

    def test_per_account_limit_across_many_ips(self):
        from accounts.views import LOGIN_FAIL_LIMIT_ACCOUNT
        for i in range(LOGIN_FAIL_LIMIT_ACCOUNT):
            self._login("wrong", f"10.0.0.{i}")
        # Correct password from a fresh IP is still refused while locked.
        self._login("RightPass123!", "10.0.1.1")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_clears_counters(self):
        self._login("wrong", "10.0.0.1")
        self._login("RightPass123!", "10.0.0.1")
        self.assertIn("_auth_user_id", self.client.session)
        self.assertIsNone(cache.get("login_fail_acct:victim@example.com"))


class JsJsonFilterTests(SimpleTestCase):
    def test_escapes_script_breakout(self):
        out = Template("{{ v|js_json }}").render(Context({"v": '["</script><img src=x>"]'}))
        self.assertNotIn("<", out)
        self.assertIn("\\u003C/script\\u003E", out)

    def test_none_and_python_values(self):
        self.assertEqual(Template("{{ v|js_json }}").render(Context({"v": None})), "null")
        self.assertEqual(Template("{{ v|js_json }}").render(Context({"v": [1, "a"]})), '[1, "a"]')
