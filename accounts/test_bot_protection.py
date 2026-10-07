from unittest import mock

import requests
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from kuccpss.ip_utils import get_client_ip

CF_EDGE = "172.68.1.10"      # inside 172.64.0.0/13
VISITOR = "41.90.5.20"


class ClientIpTests(SimpleTestCase):
    def _ip(self, **meta):
        return get_client_ip(RequestFactory().get("/", **meta))

    def test_trusts_cf_header_when_last_hop_is_cloudflare(self):
        ip = self._ip(HTTP_X_FORWARDED_FOR=f"{VISITOR}, {CF_EDGE}", HTTP_CF_CONNECTING_IP=VISITOR)
        self.assertEqual(ip, VISITOR)

    def test_ignores_cf_header_when_not_from_cloudflare(self):
        # Direct hit on the origin with a forged CF-Connecting-IP.
        ip = self._ip(HTTP_X_FORWARDED_FOR="8.8.8.8, 203.0.113.9", HTTP_CF_CONNECTING_IP="1.2.3.4")
        self.assertEqual(ip, "203.0.113.9")

    def test_falls_back_to_edge_when_cf_header_invalid(self):
        ip = self._ip(HTTP_X_FORWARDED_FOR=CF_EDGE, HTTP_CF_CONNECTING_IP="not-an-ip")
        self.assertEqual(ip, CF_EDGE)

    def test_remote_addr_without_proxy(self):
        self.assertEqual(self._ip(REMOTE_ADDR="10.1.2.3"), "10.1.2.3")

    def test_ipv6_cloudflare_edge(self):
        ip = self._ip(HTTP_X_FORWARDED_FOR="2606:4700::1", HTTP_CF_CONNECTING_IP=VISITOR)
        self.assertEqual(ip, VISITOR)


def _siteverify(success):
    resp = mock.Mock()
    resp.json.return_value = {"success": success, "error-codes": [] if success else ["invalid-input-response"]}
    return resp


@override_settings(TURNSTILE_SITE_KEY="site", TURNSTILE_SECRET_KEY="secret")
class TurnstileGateTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user(email="s@example.com", password="RightPass123!")

    def _login(self, **extra):
        return self.client.post(reverse("accounts:login"),
                                {"email": "s@example.com", "password": "RightPass123!", **extra})

    def test_widget_rendered(self):
        self.assertContains(self.client.get(reverse("accounts:login")), 'data-sitekey="site"')

    def test_login_without_token_refused(self):
        self._login()
        self.assertNotIn("_auth_user_id", self.client.session)

    @mock.patch("kuccpss.turnstile.requests.post", return_value=_siteverify(False))
    def test_login_rejected_token_refused(self, _post):
        self._login(**{"cf-turnstile-response": "bad"})
        self.assertNotIn("_auth_user_id", self.client.session)

    @mock.patch("kuccpss.turnstile.requests.post", return_value=_siteverify(True))
    def test_login_valid_token_allowed(self, _post):
        self._login(**{"cf-turnstile-response": "good"})
        self.assertIn("_auth_user_id", self.client.session)

    @mock.patch("kuccpss.turnstile.requests.post", side_effect=requests.ConnectionError)
    def test_siteverify_outage_fails_open(self, _post):
        self._login(**{"cf-turnstile-response": "tok"})
        self.assertIn("_auth_user_id", self.client.session)

    def test_register_without_token_refused(self):
        self.client.post(reverse("accounts:register"), {
            "email": "new@example.com", "password1": "Str0ngPass!x", "password2": "Str0ngPass!x",
            "agreed_terms": "on",
        })
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    @mock.patch("kuccpss.turnstile.requests.post")
    def test_password_reset_without_token_sends_nothing(self, _post):
        with mock.patch("allauth.account.forms.ResetPasswordForm.save") as save:
            self.client.post(reverse("account_reset_password"), {"email": "s@example.com"})
        save.assert_not_called()

    def test_allauth_signup_redirects_to_register(self):
        resp = self.client.get("/accounts/signup/")
        self.assertRedirects(resp, reverse("accounts:register"), fetch_redirect_response=False)


class TurnstileDisabledTests(TestCase):
    def test_login_works_without_keys(self):
        User.objects.create_user(email="s@example.com", password="RightPass123!")
        self.client.post(reverse("accounts:login"), {"email": "s@example.com", "password": "RightPass123!"})
        self.assertIn("_auth_user_id", self.client.session)
