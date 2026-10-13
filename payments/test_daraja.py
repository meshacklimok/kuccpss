import json
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from kuccpss.circuit_breaker import CircuitOpenError
from payments import daraja, gateway
from payments.models import Payment, PaymentGatewayConfig, Transaction

User = get_user_model()

DARAJA_SETTINGS = dict(
    DARAJA_CONSUMER_KEY="k", DARAJA_CONSUMER_SECRET="s", DARAJA_SHORTCODE="174379",
    DARAJA_PASSKEY="p", DARAJA_CALLBACK_SECRET="cbsecret",
    INTASEND_SECRET_KEY="isk", INTASEND_PUBLISHABLE_KEY="ispk",
)


def _callback(checkout_id, code=0, amount=50, receipt="TGH4ABC123"):
    cb = {"CheckoutRequestID": checkout_id, "ResultCode": code, "ResultDesc": "x"}
    if code == 0:
        cb["CallbackMetadata"] = {"Item": [
            {"Name": "Amount", "Value": amount},
            {"Name": "MpesaReceiptNumber", "Value": receipt},
            {"Name": "PhoneNumber", "Value": 254712345678},
        ]}
    return json.dumps({"Body": {"stkCallback": cb}})


@override_settings(**DARAJA_SETTINGS)
class GatewayConfigTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_defaults_keep_intasend_only(self):
        self.assertEqual(gateway.enabled_providers(), ["intasend"])

    def test_daraja_primary_with_failover(self):
        PaymentGatewayConfig.objects.create(primary_provider="daraja", daraja_enabled=True)
        self.assertEqual(gateway.enabled_providers(), ["daraja", "intasend"])

    def test_either_gateway_can_be_switched_off(self):
        PaymentGatewayConfig.objects.create(primary_provider="daraja", daraja_enabled=True, intasend_enabled=False)
        self.assertEqual(gateway.enabled_providers(), ["daraja"])

    def test_failover_off_means_primary_only(self):
        PaymentGatewayConfig.objects.create(primary_provider="daraja", daraja_enabled=True, auto_failover=False)
        self.assertEqual(gateway.enabled_providers(), ["daraja"])

    @override_settings(DARAJA_PASSKEY="")
    def test_unconfigured_gateway_is_skipped(self):
        PaymentGatewayConfig.objects.create(primary_provider="daraja", daraja_enabled=True)
        self.assertEqual(gateway.configured_providers(), ["intasend"])


@override_settings(**DARAJA_SETTINGS)
class FailoverTests(TestCase):
    def setUp(self):
        cache.clear()
        PaymentGatewayConfig.objects.create(primary_provider="daraja", daraja_enabled=True)

    def _push(self):
        return gateway.initiate_stk("0712345678", 50, "1")

    @patch("payments.services.initiate_stk_push", return_value="INV1")
    @patch("payments.daraja.initiate_stk_push", return_value="ws_CO_1")
    def test_primary_used_first(self, d, i):
        self.assertEqual(self._push(), ("daraja", "ws_CO_1"))
        i.assert_not_called()

    @patch("payments.services.initiate_stk_push", return_value="INV1")
    @patch("payments.daraja.initiate_stk_push", side_effect=CircuitOpenError("daraja"))
    def test_falls_back_when_primary_down(self, d, i):
        self.assertEqual(self._push(), ("intasend", "INV1"))

    @patch("payments.services.initiate_stk_push", return_value="INV1")
    @patch("payments.daraja.initiate_stk_push", side_effect=requests.ReadTimeout())
    def test_ambiguous_read_timeout_does_not_double_prompt(self, d, i):
        with self.assertRaises(requests.ReadTimeout):
            self._push()
        i.assert_not_called()

    @patch("payments.services.initiate_stk_push", side_effect=requests.ConnectionError())
    @patch("payments.daraja.initiate_stk_push", side_effect=requests.ConnectionError())
    def test_raises_when_all_down(self, d, i):
        with self.assertRaises(requests.ConnectionError):
            self._push()


@override_settings(**DARAJA_SETTINGS)
class DarajaCallbackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email="d@example.com", password="x")
        self.payment = Payment.objects.create(
            user=self.user, feature="ai_chat_access", amount=50, provider="daraja", checkout_id="ws_CO_1",
        )
        self.url = reverse("payments:daraja_callback", args=["cbsecret"])

    def _post(self, body, url=None):
        return self.client.post(url or self.url, body, content_type="application/json")

    def test_wrong_secret_rejected(self):
        resp = self._post(_callback("ws_CO_1"), reverse("payments:daraja_callback", args=["nope"]))
        self.assertEqual(resp.status_code, 404)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    @patch("payments.views.fulfil_completed_payment")
    def test_success_completes_once(self, fulfil):
        self.assertEqual(self._post(_callback("ws_CO_1")).status_code, 200)
        self._post(_callback("ws_CO_1"))  # Safaricom retry
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "completed")
        self.assertEqual(self.payment.mpesa_code, "TGH4ABC123")
        self.assertEqual(Transaction.objects.filter(payment=self.payment).count(), 1)
        fulfil.assert_called_once()

    @patch("payments.views.fulfil_completed_payment")
    def test_short_payment_not_unlocked(self, fulfil):
        self._post(_callback("ws_CO_1", amount=10))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")
        fulfil.assert_not_called()

    def test_cancelled_marks_failed(self):
        self._post(_callback("ws_CO_1", code=1032))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "failed")

    @patch("payments.views.fulfil_completed_payment")
    def test_intasend_payment_with_same_id_untouched(self, fulfil):
        Payment.objects.filter(pk=self.payment.pk).update(provider="intasend")
        self._post(_callback("ws_CO_1"))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")


@override_settings(**DARAJA_SETTINGS)
class DarajaStatusTests(TestCase):
    def _resp(self, status, body):
        r = requests.Response()
        r.status_code = status
        r._content = json.dumps(body).encode()
        return r

    def setUp(self):
        cache.clear()

    @patch("payments.daraja._post")
    def test_query_states(self, post):
        post.return_value = self._resp(200, {"ResultCode": "0"})
        self.assertEqual(daraja.query_stk("x")["state"], "COMPLETE")
        post.return_value = self._resp(200, {"ResultCode": "1032"})
        self.assertEqual(daraja.query_stk("x")["state"], "FAILED")
        post.return_value = self._resp(500, {"errorCode": "500.001.1001"})
        self.assertEqual(daraja.query_stk("x")["state"], "PENDING")

    @patch("payments.daraja._post")
    def test_processing_does_not_trip_breaker(self, post):
        from kuccpss.circuit_breaker import daraja_breaker
        post.return_value = self._resp(500, {"errorCode": "500.001.1001"})
        for _ in range(10):
            daraja.query_stk("x")
        self.assertFalse(daraja_breaker.is_open())
