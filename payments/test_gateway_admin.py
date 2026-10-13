"""Daraja set up purely through the admin screen — no DARAJA_* environment variables."""
import json
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from payments import daraja, gateway
from payments.models import Payment, PaymentGatewayConfig
from payments.test_gateway_e2e import DARAJA_STK_URL, DARAJA_TOKEN_URL, FakeNetwork, _resp

User = get_user_model()

NO_ENV = dict(
    DARAJA_CONSUMER_KEY="", DARAJA_CONSUMER_SECRET="", DARAJA_SHORTCODE="", DARAJA_PASSKEY="",
    DARAJA_CALLBACK_SECRET="", DARAJA_SITE_URL="", DARAJA_SANDBOX=False,
    INTASEND_SECRET_KEY="isk", INTASEND_PUBLISHABLE_KEY="ispk", INTASEND_WEBHOOK_SECRET="is-secret",
    INTASEND_SANDBOX=False, STAFF_2FA_REQUIRED=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)

FORM = {
    "primary_provider": "daraja", "intasend_enabled": "on", "daraja_enabled": "on", "auto_failover": "on",
    "daraja_shortcode": "400200", "daraja_consumer_key": "  KEY123 ", "daraja_consumer_secret": "SECRET456",
    "daraja_passkey": "PASSKEY789", "daraja_site_url": "https://pay.example.test/",
}


class RejectingNetwork(FakeNetwork):
    """Safaricom refuses the consumer key/secret."""

    def _handle(self, method, url, **kw):
        if url == DARAJA_TOKEN_URL:
            self.calls.append({"method": method, "url": url, "json": None, "headers": None, "kw": kw})
            err = requests.HTTPError("bad creds")
            err.response = _resp(400, {"errorMessage": "Bad Request"})
            raise err
        return super()._handle(method, url, **kw)


@override_settings(**NO_ENV)
class AdminSetupTests(TestCase):
    net_class = FakeNetwork

    def setUp(self):
        cache.clear()
        self.net = self.net_class()
        for target in ("requests.post", "requests.get"):
            p = patch(target, getattr(self.net, target.split(".")[1]))
            p.start()
            self.addCleanup(p.stop)
        self.admin = User.objects.create_superuser(email="admin@example.com", password="pw")
        self.client.force_login(self.admin)
        self.url = reverse("admin:payments_paymentgatewayconfig_change", args=[1])
        PaymentGatewayConfig.load()

    def _save(self, **overrides):
        data = {**FORM, **overrides}
        return self.client.post(self.url, {k: v for k, v in data.items() if v is not None}, follow=True)

    def _messages(self, resp):
        return " | ".join(str(m) for m in resp.context["messages"])

    # ── happy path ───────────────────────────────────────────────────────────
    def test_changelist_and_form_load(self):
        self.assertEqual(self.client.get(reverse("admin:payments_paymentgatewayconfig_changelist")).status_code, 200)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "SECRET456")

    def test_credentials_entered_in_admin_switch_daraja_on(self):
        resp = self._save()
        cfg = PaymentGatewayConfig.load()
        self.assertTrue(cfg.daraja_enabled, self._messages(resp))
        self.assertIn("credentials accepted", self._messages(resp))
        self.assertEqual(cfg.daraja_consumer_key, "KEY123")            # whitespace stripped
        self.assertEqual(cfg.daraja_site_url, "https://pay.example.test")
        self.assertTrue(cfg.daraja_callback_secret)                    # generated
        self.assertEqual(gateway.enabled_providers(), ["daraja", "intasend"])
        self.assertEqual(gateway.configured_providers(), ["daraja", "intasend"])

    def test_payment_uses_admin_credentials_and_callback_url(self):
        self._save()
        secret = PaymentGatewayConfig.load().daraja_callback_secret
        user = User.objects.create_user(email="u@example.com", password="pw")
        self.client.force_login(user)
        resp = self.client.post(reverse("payments:initiate_payment"),
                                json.dumps({"feature": "ai_chat_access", "phone": "0712345678"}),
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200, resp.content)
        stk = [c for c in self.net.calls if c["url"] == DARAJA_STK_URL][0]
        self.assertEqual(stk["json"]["BusinessShortCode"], "400200")
        self.assertEqual(stk["json"]["CallBackURL"], f"https://pay.example.test/payments/webhook/daraja/{secret}/")
        token = [c for c in self.net.calls if c["url"] == DARAJA_TOKEN_URL][-1]
        self.assertEqual(token["kw"]["auth"], ("KEY123", "SECRET456"))
        # the generated callback secret actually authenticates the callback
        cb = {"Body": {"stkCallback": {"CheckoutRequestID": "ws_CO_FAKE1", "ResultCode": 0, "CallbackMetadata": {"Item": [
            {"Name": "Amount", "Value": 50}, {"Name": "MpesaReceiptNumber", "Value": "SGR7ABC123"}]}}}}
        r = self.client.post(reverse("payments:daraja_callback", args=[secret]), json.dumps(cb),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Payment.objects.get().status, "completed")

    def test_sandbox_checkbox_switches_endpoints(self):
        self._save(daraja_sandbox="on")
        self.assertTrue(any(c["url"].startswith("https://sandbox.safaricom.co.ke") for c in self.net.calls))

    # ── safety rails ─────────────────────────────────────────────────────────
    def test_blank_secret_boxes_keep_saved_values(self):
        self._save()
        self._save(daraja_consumer_key="", daraja_consumer_secret="", daraja_passkey="")
        cfg = PaymentGatewayConfig.load()
        self.assertEqual((cfg.daraja_consumer_key, cfg.daraja_consumer_secret, cfg.daraja_passkey),
                         ("KEY123", "SECRET456", "PASSKEY789"))
        self.assertTrue(cfg.daraja_enabled)

    def test_callback_secret_stays_stable_across_saves(self):
        self._save()
        first = PaymentGatewayConfig.load().daraja_callback_secret
        self._save(auto_failover=None)
        self.assertEqual(PaymentGatewayConfig.load().daraja_callback_secret, first)

    def test_cannot_enable_daraja_without_credentials(self):
        resp = self._save(daraja_consumer_key="", daraja_consumer_secret="", daraja_passkey="", daraja_shortcode="")
        self.assertContains(resp, "To switch Daraja on, first fill in")
        self.assertFalse(PaymentGatewayConfig.load().daraja_enabled)

    def test_can_save_credentials_first_and_enable_later(self):
        self._save(daraja_enabled=None)
        cfg = PaymentGatewayConfig.load()
        self.assertFalse(cfg.daraja_enabled)
        self.assertEqual(gateway.enabled_providers(), ["intasend"])     # nothing changed for customers
        self._save()
        self.assertTrue(PaymentGatewayConfig.load().daraja_enabled)

    def test_cannot_turn_both_gateways_off(self):
        resp = self._save(intasend_enabled=None, daraja_enabled=None)
        self.assertContains(resp, "at least one gateway")

    def test_paybill_must_be_digits_and_url_must_be_https(self):
        self.assertContains(self._save(daraja_shortcode="abc"), "digits only")
        self.assertContains(self._save(daraja_site_url="http://insecure.test"), "https://")

    def test_connection_test_action(self):
        self._save()
        resp = self.client.post(reverse("admin:payments_paymentgatewayconfig_changelist"),
                                {"action": "test_daraja_connection", "_selected_action": [1]}, follow=True)
        self.assertIn("credentials accepted", self._messages(resp))


@override_settings(**NO_ENV)
class BadCredentialsTests(AdminSetupTests):
    net_class = RejectingNetwork

    # Inherited happy-path tests don't apply with a rejecting Safaricom
    test_credentials_entered_in_admin_switch_daraja_on = None
    test_payment_uses_admin_credentials_and_callback_url = None
    test_sandbox_checkbox_switches_endpoints = None
    test_blank_secret_boxes_keep_saved_values = None
    test_callback_secret_stays_stable_across_saves = None
    test_can_save_credentials_first_and_enable_later = None
    test_connection_test_action = None
    test_changelist_and_form_load = None
    test_cannot_enable_daraja_without_credentials = None
    test_cannot_turn_both_gateways_off = None
    test_paybill_must_be_digits_and_url_must_be_https = None

    def test_rejected_credentials_leave_daraja_off_and_intasend_working(self):
        resp = self._save()
        cfg = PaymentGatewayConfig.load()
        self.assertFalse(cfg.daraja_enabled)
        self.assertIn("Daraja was NOT switched on", self._messages(resp))
        self.assertEqual(cfg.daraja_shortcode, "400200")                # the rest was still saved
        self.assertEqual(gateway.enabled_providers(), ["intasend"])
        # customers still pay through IntaSend
        user = User.objects.create_user(email="u@example.com", password="pw")
        self.client.force_login(user)
        r = self.client.post(reverse("payments:initiate_payment"),
                             json.dumps({"feature": "ai_chat_access", "phone": "0712345678"}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Payment.objects.get().provider, "intasend")

    def test_rejected_credentials_mid_flight_still_fail_over(self):
        """Even if Daraja were somehow on with bad credentials, IntaSend takes the payment."""
        PaymentGatewayConfig.objects.filter(pk=1).update(
            primary_provider="daraja", daraja_enabled=True, daraja_consumer_key="x",
            daraja_consumer_secret="y", daraja_shortcode="1", daraja_passkey="z", daraja_callback_secret="s")
        user = User.objects.create_user(email="u@example.com", password="pw")
        self.client.force_login(user)
        r = self.client.post(reverse("payments:initiate_payment"),
                             json.dumps({"feature": "ai_chat_access", "phone": "0712345678"}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Payment.objects.get().provider, "intasend")


@override_settings(**NO_ENV)
class DarajaConfigFallbackTests(TestCase):
    def test_nothing_configured_means_not_ready_and_no_crash(self):
        self.assertFalse(daraja.is_configured())
        self.assertEqual(daraja.Config().missing[0], "Consumer key")
        self.assertIsNone(daraja.query_stk("ws_CO_x"))
        ok, msg = daraja.test_connection()
        self.assertFalse(ok)
        self.assertIn("Missing", msg)

    @override_settings(DARAJA_CONSUMER_KEY="envkey", DARAJA_CONSUMER_SECRET="envsec",
                       DARAJA_SHORTCODE="111", DARAJA_PASSKEY="envpk", DARAJA_CALLBACK_SECRET="envcb")
    def test_env_vars_still_work_and_admin_value_wins(self):
        self.assertTrue(daraja.is_configured())
        self.assertEqual(daraja.Config().shortcode, "111")
        PaymentGatewayConfig.objects.update_or_create(pk=1, defaults={"daraja_shortcode": "222"})
        self.assertEqual(daraja.Config().shortcode, "222")
