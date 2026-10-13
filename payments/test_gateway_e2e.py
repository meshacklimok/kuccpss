"""
End-to-end checks for the Daraja + IntaSend gateways with fake credentials.

The real views, services and database run; only `requests.get/post` is replaced by a
fake that records every outbound call and plays back canned IntaSend / Safaricom replies.
That lets us assert (a) Daraja works through the whole flow and (b) IntaSend traffic is
identical to what it was before Daraja existed, and is never touched when it shouldn't be.
"""
import base64
import json
from datetime import date, timedelta
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from payments.models import Payment, PaymentGatewayConfig, Transaction

User = get_user_model()

FAKE = dict(
    INTASEND_SECRET_KEY="ISSecretKey_test_fake", INTASEND_PUBLISHABLE_KEY="ISPubKey_test_fake",
    INTASEND_WEBHOOK_SECRET="is-webhook-secret", INTASEND_SANDBOX=False,
    DARAJA_CONSUMER_KEY="ck_fake", DARAJA_CONSUMER_SECRET="cs_fake", DARAJA_SHORTCODE="600999",
    DARAJA_PASSKEY="passkey_fake", DARAJA_CALLBACK_SECRET="cb-secret-fake",
    DARAJA_SITE_URL="https://example.test", DARAJA_SANDBOX=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
INTASEND_STK_URL = "https://payment.intasend.com/api/v1/payment/mpesa-stk-push/"
INTASEND_STATUS_URL = "https://payment.intasend.com/api/v1/payment/status/"
DARAJA_TOKEN_URL = "https://api.safaricom.co.ke/oauth/v1/generate"
DARAJA_STK_URL = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
DARAJA_QUERY_URL = "https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query"


def _resp(status, body):
    r = requests.Response()
    r.status_code = status
    r._content = json.dumps(body).encode()
    return r


class FakeNetwork:
    """Stands in for requests.get/post. `down` = hosts that refuse connections."""

    def __init__(self):
        self.calls = []
        self.down = set()
        self.intasend_invoice_state = "PENDING"
        self.daraja_result_code = None  # None → "still processing"

    def _host(self, url):
        return "daraja" if "safaricom" in url else "intasend"

    def _handle(self, method, url, **kw):
        self.calls.append({"method": method, "url": url, "json": kw.get("json"),
                           "headers": kw.get("headers"), "kw": kw})
        host = self._host(url)
        url = url.replace("https://sandbox.safaricom.co.ke", "https://api.safaricom.co.ke")
        if host in self.down:
            raise requests.ConnectionError(f"{host} is down")
        if url == INTASEND_STK_URL:
            return _resp(200, {"invoice": {"invoice_id": "ISINV-1", "state": "PENDING"}})
        if url == INTASEND_STATUS_URL:
            return _resp(200, {"invoice": {"state": self.intasend_invoice_state, "mpesa_reference": "ISREF12345"}})
        if url == DARAJA_TOKEN_URL:
            return _resp(200, {"access_token": "tok_fake", "expires_in": "3599"})
        if url == DARAJA_STK_URL:
            return _resp(200, {"ResponseCode": "0", "CheckoutRequestID": "ws_CO_FAKE1",
                               "ResponseDescription": "Success"})
        if url == DARAJA_QUERY_URL:
            if self.daraja_result_code is None:
                return _resp(500, {"errorCode": "500.001.1001", "errorMessage": "being processed"})
            return _resp(200, {"ResultCode": str(self.daraja_result_code), "ResultDesc": "x"})
        raise AssertionError(f"Unexpected outbound call: {method} {url}")

    def post(self, url, **kw):
        return self._handle("POST", url, **kw)

    def get(self, url, **kw):
        return self._handle("GET", url, **kw)

    def to(self, host):
        return [c for c in self.calls if self._host(c["url"]) == host]


@override_settings(**FAKE)
class GatewayEndToEnd(TestCase):
    def setUp(self):
        cache.clear()
        self.net = FakeNetwork()
        for target in ("requests.post", "requests.get"):
            p = patch(target, getattr(self.net, target.split(".")[1]))
            p.start()
            self.addCleanup(p.stop)
        self.user = User.objects.create_user(email="u@example.com", password="pw")
        self.client.force_login(self.user)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _pay(self, feature="ai_chat_access", phone="0712 345 678"):
        return self.client.post(
            reverse("payments:initiate_payment"),
            json.dumps({"feature": feature, "phone": phone}), content_type="application/json",
        )

    def _intasend_webhook(self, payment, state="COMPLETE"):
        return self.client.post(
            reverse("payments:mpesa_webhook"),
            json.dumps({"challenge": "is-webhook-secret", "api_ref": str(payment.pk), "state": state,
                        "mpesa_reference": "ISREF12345", "invoice_id": "ISINV-1",
                        "phone_number": "254712345678", "value": "50.00"}),
            content_type="application/json",
        )

    def _daraja_callback(self, checkout_id, code=0, amount=50):
        cb = {"CheckoutRequestID": checkout_id, "ResultCode": code, "ResultDesc": "x"}
        if code == 0:
            cb["CallbackMetadata"] = {"Item": [
                {"Name": "Amount", "Value": amount},
                {"Name": "MpesaReceiptNumber", "Value": "SGR7ABC123"},
                {"Name": "PhoneNumber", "Value": 254712345678},
            ]}
        return self.client.post(
            reverse("payments:daraja_callback", args=["cb-secret-fake"]),
            json.dumps({"Body": {"stkCallback": cb}}), content_type="application/json",
        )

    def _daraja_primary(self, **kw):
        PaymentGatewayConfig.objects.update_or_create(
            pk=1, defaults=dict(primary_provider="daraja", daraja_enabled=True, **kw))

    # ── IntaSend alone (default config, exactly like production today) ───────
    def test_default_config_uses_intasend_only_and_never_contacts_daraja(self):
        resp = self._pay()
        self.assertEqual(resp.status_code, 200, resp.content)
        payment = Payment.objects.get()
        self.assertEqual((payment.provider, payment.checkout_id, payment.status), ("intasend", "ISINV-1", "pending"))

        self.assertEqual(self.net.to("daraja"), [])          # Daraja never contacted
        (call,) = self.net.to("intasend")
        self.assertEqual(call["url"], INTASEND_STK_URL)
        # Byte-for-byte what the pre-Daraja code sent:
        self.assertEqual(call["json"], {
            "public_key": "ISPubKey_test_fake", "currency": "KES", "amount": 50,
            "phone_number": "254712345678", "email": "u@example.com",
            "narrative": "CareerNext AI Chat Top-Up", "api_ref": str(payment.pk),
        })
        self.assertEqual(call["headers"], {"Authorization": "Bearer ISSecretKey_test_fake",
                                           "Content-Type": "application/json"})
        self.assertEqual(call["kw"]["timeout"], 15)

    def test_intasend_webhook_completes_payment(self):
        self._pay()
        payment = Payment.objects.get()
        self.assertEqual(self._intasend_webhook(payment).status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "completed")
        self.assertTrue(Transaction.objects.filter(payment=payment, mpesa_ref="ISREF12345").exists())
        self.assertTrue(any("Payment Confirmed" in m.subject for m in mail.outbox))
        self.assertEqual(self.net.to("daraja"), [])

    def test_intasend_status_poll_asks_intasend_only(self):
        self._pay()
        payment = Payment.objects.get()
        self.net.intasend_invoice_state = "COMPLETE"
        data = self.client.get(reverse("payments:payment_status", args=[payment.pk])).json()
        self.assertEqual(data["status"], "completed")
        poll = self.net.to("intasend")[-1]
        self.assertEqual((poll["url"], poll["json"]), (INTASEND_STATUS_URL, {"invoice_id": "ISINV-1"}))
        self.assertEqual(self.net.to("daraja"), [])

    def test_daraja_enabled_but_intasend_primary_still_uses_intasend(self):
        PaymentGatewayConfig.objects.create(primary_provider="intasend", daraja_enabled=True)
        self._pay()
        self.assertEqual(Payment.objects.get().provider, "intasend")
        self.assertEqual(self.net.to("daraja"), [])

    # ── Daraja alone ─────────────────────────────────────────────────────────
    def test_daraja_primary_full_flow(self):
        self._daraja_primary()
        resp = self._pay()
        self.assertEqual(resp.status_code, 200, resp.content)
        payment = Payment.objects.get()
        self.assertEqual((payment.provider, payment.checkout_id), ("daraja", "ws_CO_FAKE1"))
        self.assertEqual(self.net.to("intasend"), [])        # IntaSend never contacted

        token_call, stk_call = self.net.to("daraja")
        self.assertEqual(token_call["url"], DARAJA_TOKEN_URL)
        self.assertEqual(token_call["kw"]["auth"], ("ck_fake", "cs_fake"))
        body = stk_call["json"]
        self.assertEqual(stk_call["headers"]["Authorization"], "Bearer tok_fake")
        self.assertEqual(body["BusinessShortCode"], "600999")
        self.assertEqual(body["PartyB"], "600999")
        self.assertEqual(body["TransactionType"], "CustomerPayBillOnline")
        self.assertEqual((body["Amount"], body["PartyA"], body["PhoneNumber"]), (50, "254712345678", "254712345678"))
        self.assertEqual(body["CallBackURL"], "https://example.test/payments/webhook/daraja/cb-secret-fake/")
        self.assertLessEqual(len(body["AccountReference"]), 12)
        self.assertLessEqual(len(body["TransactionDesc"]), 20)
        self.assertEqual(base64.b64decode(body["Password"]).decode(), "600999passkey_fake" + body["Timestamp"])

        # While the customer hasn't answered, polling reports pending (and doesn't break anything)
        self.assertEqual(self.client.get(reverse("payments:payment_status", args=[payment.pk])).json()["status"], "pending")

        # Safaricom's callback unlocks it
        self.assertEqual(self._daraja_callback("ws_CO_FAKE1").status_code, 200)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.mpesa_code), ("completed", "SGR7ABC123"))
        self.assertTrue(any("Payment Confirmed" in m.subject for m in mail.outbox))
        self.assertEqual(self.net.to("intasend"), [])

    def test_daraja_lost_callback_recovered_by_polling(self):
        self._daraja_primary()
        self._pay()
        payment = Payment.objects.get()
        self.net.daraja_result_code = 0
        self.assertEqual(self.client.get(reverse("payments:payment_status", args=[payment.pk])).json()["status"], "completed")
        self.assertEqual(self.net.to("intasend"), [])

    def test_daraja_user_cancelled(self):
        self._daraja_primary()
        self._pay()
        self._daraja_callback("ws_CO_FAKE1", code=1032)
        self.assertEqual(Payment.objects.get().status, "failed")

    # ── Failover & switching ─────────────────────────────────────────────────
    def test_daraja_down_fails_over_to_intasend_with_identical_request(self):
        self._daraja_primary()
        self.net.down.add("daraja")
        self.assertEqual(self._pay().status_code, 200)
        payment = Payment.objects.get()
        self.assertEqual((payment.provider, payment.checkout_id), ("intasend", "ISINV-1"))
        (call,) = self.net.to("intasend")
        self.assertEqual(call["json"]["api_ref"], str(payment.pk))
        self.assertEqual(call["json"]["public_key"], "ISPubKey_test_fake")
        # …and that IntaSend payment still completes through the IntaSend webhook
        self._intasend_webhook(payment)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "completed")

    def test_intasend_down_with_intasend_primary_falls_over_to_daraja(self):
        PaymentGatewayConfig.objects.create(primary_provider="intasend", daraja_enabled=True)
        self.net.down.add("intasend")
        self.assertEqual(self._pay().status_code, 200)
        self.assertEqual(Payment.objects.get().provider, "daraja")

    def test_both_down_gives_clean_error_and_failed_payment(self):
        self._daraja_primary()
        self.net.down.update({"daraja", "intasend"})
        resp = self._pay()
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(Payment.objects.get().status, "failed")

    def test_intasend_switched_off_in_admin_is_never_called(self):
        self._daraja_primary(intasend_enabled=False)
        self.net.down.add("daraja")
        self.assertEqual(self._pay().status_code, 502)
        self.assertEqual(self.net.to("intasend"), [])

    def test_in_flight_payments_keep_their_own_gateway_after_switch(self):
        """An IntaSend payment started before the switch must still be checked with IntaSend."""
        self._pay()                                  # IntaSend (default config)
        payment = Payment.objects.get()
        self._daraja_primary()                       # admin flips primary to Daraja
        self.net.intasend_invoice_state = "COMPLETE"
        self.client.get(reverse("payments:payment_status", args=[payment.pk]))
        self.assertEqual(Payment.objects.get().status, "completed")
        self.assertEqual(self.net.to("daraja"), [])

    # ── Webhook isolation ────────────────────────────────────────────────────
    def test_daraja_callback_cannot_complete_an_intasend_payment(self):
        self._pay()                                  # IntaSend payment, checkout ISINV-1
        self._daraja_callback("ISINV-1")
        self.assertEqual(Payment.objects.get().status, "pending")

    def test_intasend_webhook_endpoint_still_requires_its_secret(self):
        self._pay()
        payment = Payment.objects.get()
        resp = self.client.post(
            reverse("payments:mpesa_webhook"),
            json.dumps({"challenge": "wrong", "api_ref": str(payment.pk), "state": "COMPLETE"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    # ── Mentorship ───────────────────────────────────────────────────────────
    def _mentorship_session(self):
        from mentorship.models import MentorProfile, MentorshipSession, TimeSlot
        mentor_user = User.objects.create_user(email="m@example.com", password="pw")
        mentor = MentorProfile.objects.create(user=mentor_user, bio="b", whatsapp="+254712345678", is_approved=True)
        TimeSlot.objects.create(mentor=mentor, date=date.today() + timedelta(days=2), start_time="14:00")
        slot = TimeSlot.objects.get()
        self.client.post(reverse("mentorship:book_session", args=[mentor.pk]),
                         {"slot": slot.pk, "mentee_question": "q", "mentee_phone": "0712345678"})
        return MentorshipSession.objects.get()

    def _mentorship_pay(self, session):
        return self.client.post(reverse("mentorship:initiate_payment", args=[session.token]),
                                json.dumps({"phone": "0712345678"}), content_type="application/json")

    def test_mentorship_booking_via_daraja_confirms_on_callback(self):
        self._daraja_primary()
        session = self._mentorship_session()
        resp = self._mentorship_pay(session)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self.net.to("intasend"), [])
        payment = Payment.objects.get(mentorship_session=session)
        self.assertEqual((payment.provider, payment.checkout_id), ("daraja", "ws_CO_FAKE1"))
        self._daraja_callback("ws_CO_FAKE1", amount=int(session.amount))
        session.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual((session.status, payment.status), ("confirmed", "completed"))

    def test_mentorship_booking_via_intasend_unchanged(self):
        session = self._mentorship_session()
        self.assertEqual(self._mentorship_pay(session).status_code, 200)
        self.assertEqual(self.net.to("daraja"), [])
        (call,) = self.net.to("intasend")
        self.assertEqual(call["json"]["api_ref"], str(session.token))   # IntaSend still keyed by session token
        # IntaSend's UUID-ref webhook still confirms the booking
        self.client.post(
            reverse("payments:mpesa_webhook"),
            json.dumps({"challenge": "is-webhook-secret", "api_ref": str(session.token), "state": "COMPLETE",
                        "invoice_id": "ISINV-1"}),
            content_type="application/json",
        )
        session.refresh_from_db()
        self.assertEqual(session.status, "confirmed")

    def test_mentorship_daraja_down_fails_over_to_intasend(self):
        self._daraja_primary()
        self.net.down.add("daraja")
        session = self._mentorship_session()
        self.assertEqual(self._mentorship_pay(session).status_code, 200)
        self.assertEqual(Payment.objects.get(mentorship_session=session).provider, "intasend")
