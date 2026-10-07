import hashlib
import hmac
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from payments.models import Payment, PaymentExemption, PaymentFeature
from payments.services import (
    has_paid_for_feature,
    normalise_phone,
    price_for_feature,
    verify_intasend_signature,
)

User = get_user_model()


class NormalisePhoneTests(TestCase):
    def test_local_format_converted(self):
        self.assertEqual(normalise_phone("0712345678"), "254712345678")

    def test_plus_prefix_stripped(self):
        self.assertEqual(normalise_phone("+254712345678"), "254712345678")

    def test_already_normalised_unchanged(self):
        self.assertEqual(normalise_phone("254712345678"), "254712345678")

    def test_spaces_and_dashes_removed(self):
        self.assertEqual(normalise_phone("0712 345-678"), "254712345678")


class VerifyIntasendSignatureTests(TestCase):
    @override_settings(INTASEND_WEBHOOK_SECRET="")
    def test_no_secret_configured_allows_request(self):
        request = Mock(headers={}, body=b"{}")
        self.assertTrue(verify_intasend_signature(request))

    @override_settings(INTASEND_WEBHOOK_SECRET="testsecret")
    def test_missing_signature_header_rejected(self):
        request = Mock(headers={}, body=b'{"foo": "bar"}')
        self.assertFalse(verify_intasend_signature(request))

    @override_settings(INTASEND_WEBHOOK_SECRET="testsecret")
    def test_valid_signature_accepted(self):
        body = b'{"foo": "bar"}'
        sig = hmac.new(b"testsecret", body, hashlib.sha256).hexdigest()
        request = Mock(headers={"X-IntaSend-Signature": sig}, body=body)
        self.assertTrue(verify_intasend_signature(request))

    @override_settings(INTASEND_WEBHOOK_SECRET="testsecret")
    def test_invalid_signature_rejected(self):
        body = b'{"foo": "bar"}'
        request = Mock(headers={"X-IntaSend-Signature": "wrongsignature"}, body=body)
        self.assertFalse(verify_intasend_signature(request))


class HasPaidForFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="student@example.com", password="pass1234")

    def test_staff_always_passes(self):
        self.user.is_staff = True
        self.user.save()
        self.assertTrue(has_paid_for_feature(self.user, "ai_chat_access"))

    def test_no_payment_no_exemption_fails(self):
        self.assertFalse(has_paid_for_feature(self.user, "ai_chat_access"))

    def test_completed_payment_passes(self):
        Payment.objects.create(user=self.user, feature="ai_chat_access", status="completed")
        self.assertTrue(has_paid_for_feature(self.user, "ai_chat_access"))

    def test_pending_payment_does_not_pass(self):
        Payment.objects.create(user=self.user, feature="ai_chat_access", status="pending")
        self.assertFalse(has_paid_for_feature(self.user, "ai_chat_access"))

    def test_feature_specific_exemption_passes(self):
        PaymentExemption.objects.create(user=self.user, feature="ai_chat_access")
        self.assertTrue(has_paid_for_feature(self.user, "ai_chat_access"))

    def test_blanket_exemption_passes_any_feature(self):
        PaymentExemption.objects.create(user=self.user, feature="")
        self.assertTrue(has_paid_for_feature(self.user, "premium_career_report"))


class PriceForFeatureTests(TestCase):
    def test_disabled_feature_returns_zero(self):
        PaymentFeature.objects.update_or_create(
            feature="ai_chat_access",
            defaults={"label": "AI Chat", "price": 50, "is_enabled": False},
        )
        self.assertEqual(price_for_feature("ai_chat_access"), 0)

    def test_enabled_feature_returns_configured_price(self):
        PaymentFeature.objects.update_or_create(
            feature="ai_chat_access",
            defaults={"label": "AI Chat", "price": 75, "is_enabled": True},
        )
        self.assertEqual(price_for_feature("ai_chat_access"), 75)

    def test_unconfigured_feature_falls_back_to_default(self):
        PaymentFeature.objects.filter(feature="advanced_analysis").delete()
        self.assertEqual(price_for_feature("advanced_analysis"), 149)


# ── Paid-but-locked recovery ────────────────────────────────────────────────

from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from payments.models import Transaction
from payments.services import (
    extract_mpesa_code,
    has_paid_for_current_session,
    is_valid_mpesa_phone,
    lock_submission_on_payment,
)
from payments.views import complete_payment


class ExtractMpesaCodeTests(TestCase):
    def test_bare_code(self):
        self.assertEqual(extract_mpesa_code("TGH4ABC123"), "TGH4ABC123")

    def test_lowercase_and_whitespace(self):
        self.assertEqual(extract_mpesa_code("  tgh4abc123 "), "TGH4ABC123")

    def test_whole_sms(self):
        sms = "TGH4ABC123 Confirmed. Ksh100.00 sent to CAREERNEXT for account 42 on 1/9/26 at 10:02 AM."
        self.assertEqual(extract_mpesa_code(sms), "TGH4ABC123")

    def test_rejects_non_codes(self):
        self.assertEqual(extract_mpesa_code("0712345678"), "")
        self.assertEqual(extract_mpesa_code("CONFIRMED"), "")
        self.assertEqual(extract_mpesa_code(""), "")


class IsValidMpesaPhoneTests(TestCase):
    def test_accepts_kenyan_mobiles(self):
        for phone in ("0712345678", "0112345678", "+254712345678", "254112345678", "0712 345 678"):
            self.assertTrue(is_valid_mpesa_phone(phone), phone)

    def test_rejects_bad_numbers(self):
        for phone in ("", "071234567", "0212345678", "12345"):
            self.assertFalse(is_valid_mpesa_phone(phone), phone)


def _make_submission(user, feature="cluster_calculator"):
    from career.models import CareerSubmission
    return CareerSubmission.objects.create(
        user=user, feature=feature, grades_json={}, lock_at=timezone.now() + timedelta(days=1),
    )


class CompletePaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="payer@example.com", password="pass1234")

    @patch("payments.views.fulfil_completed_payment")
    def test_fulfils_exactly_once(self, fulfil):
        payment = Payment.objects.create(user=self.user, feature="ai_chat_access", amount=50)
        self.assertTrue(complete_payment(payment, mpesa_code="TGH4ABC123"))
        self.assertFalse(complete_payment(payment))
        self.assertEqual(fulfil.call_count, 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "completed")
        self.assertEqual(payment.mpesa_code, "TGH4ABC123")


class CurrentSessionUnlockTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="calc@example.com", password="pass1234")

    def test_links_submission_without_lock_config(self):
        sub = _make_submission(self.user)
        payment = Payment.objects.create(user=self.user, feature="view_cluster_points", status="completed")
        lock_submission_on_payment(payment)
        sub.refresh_from_db()
        self.assertEqual(sub.unlocked_by_payment_id, payment.pk)
        self.assertTrue(has_paid_for_current_session(self.user, "cluster_calculator", "view_cluster_points"))

    def test_unpaid_submission_is_locked(self):
        _make_submission(self.user)
        self.assertFalse(has_paid_for_current_session(self.user, "cluster_calculator", "view_cluster_points"))

    def test_self_heals_missing_link(self):
        sub = _make_submission(self.user)
        Payment.objects.create(user=self.user, feature="view_cluster_points", status="completed")
        self.assertTrue(has_paid_for_current_session(self.user, "cluster_calculator", "view_cluster_points"))
        sub.refresh_from_db()
        self.assertIsNotNone(sub.unlocked_by_payment_id)

    def test_career_report_locks_non_degree_session(self):
        from career.models import SubmissionLockConfig
        SubmissionLockConfig.objects.update_or_create(
            feature="non_degree_career", defaults={"is_enabled": True, "lock_on_payment": True},
        )
        sub = _make_submission(self.user, feature="non_degree_career")
        self.assertFalse(has_paid_for_current_session(self.user, "non_degree_career", "premium_career_report"))
        payment = Payment.objects.create(user=self.user, feature="premium_career_report", status="completed")
        lock_submission_on_payment(payment)
        sub.refresh_from_db()
        self.assertEqual((sub.unlocked_by_payment_id, sub.status), (payment.pk, "locked"))
        self.assertTrue(has_paid_for_current_session(self.user, "non_degree_career", "premium_career_report"))

    def test_career_report_keeps_already_paid_session_link(self):
        old = Payment.objects.create(user=self.user, feature="premium_career_report", status="completed")
        degree = _make_submission(self.user, feature="degree_career")
        lock_submission_on_payment(old)
        non_degree = _make_submission(self.user, feature="non_degree_career")
        new = Payment.objects.create(user=self.user, feature="premium_career_report", status="completed")
        lock_submission_on_payment(new)
        degree.refresh_from_db()
        non_degree.refresh_from_db()
        self.assertEqual(degree.unlocked_by_payment_id, old.pk)
        self.assertEqual(non_degree.unlocked_by_payment_id, new.pk)

    def test_old_payment_does_not_unlock_new_grades(self):
        payment = Payment.objects.create(user=self.user, feature="view_cluster_points", status="completed")
        Payment.objects.filter(pk=payment.pk).update(updated_at=timezone.now() - timedelta(days=2))
        _make_submission(self.user)
        self.assertFalse(has_paid_for_current_session(self.user, "cluster_calculator", "view_cluster_points"))


@patch("payments.views.fulfil_completed_payment")
class VerifyByTransactionCodeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email="stuck@example.com", password="pass1234")
        self.client.force_login(self.user)
        self.url = reverse("payments:verify_by_transaction_code")

    def post(self, code, feature="ai_chat_access"):
        return self.client.post(
            self.url, data={"feature": feature, "mpesa_code": code}, content_type="application/json",
        )

    def test_invalid_code_rejected(self, fulfil):
        self.assertEqual(self.post("hello").json()["status"], "error")

    def test_matches_logged_transaction(self, fulfil):
        payment = Payment.objects.create(user=self.user, feature="ai_chat_access", amount=50)
        Transaction.objects.create(payment=payment, mpesa_ref="TGH4ABC123", amount=50)
        self.assertEqual(self.post("tgh4abc123 Confirmed. Ksh50").json()["status"], "completed")
        payment.refresh_from_db()
        self.assertEqual(payment.status, "completed")

    @patch("payments.views.fetch_intasend_invoice", return_value={"state": "COMPLETE", "mpesa_ref": "TGH4ABC123"})
    def test_asks_intasend_when_webhook_missing(self, fetch, fulfil):
        payment = Payment.objects.create(
            user=self.user, feature="ai_chat_access", amount=50, status="failed", checkout_id="CHK1",
        )
        self.assertEqual(self.post("TGH4ABC123").json()["status"], "completed")
        payment.refresh_from_db()
        self.assertEqual(payment.status, "completed")
        self.assertTrue(payment.transactions.filter(mpesa_ref="TGH4ABC123").exists())

    @patch("payments.views.fetch_intasend_invoice", return_value={"state": "COMPLETE", "mpesa_ref": "TGH4ABC123"})
    def test_intasend_ref_stored_over_submitted_code(self, fetch, fulfil):
        payment = Payment.objects.create(
            user=self.user, feature="ai_chat_access", amount=50, status="failed", checkout_id="CHK1",
        )
        self.assertEqual(self.post("Invoice R7KQ2PX9WZ paid").json()["status"], "completed")
        payment.refresh_from_db()
        self.assertEqual(payment.mpesa_code, "TGH4ABC123")

    @patch("payments.views.fetch_intasend_invoice", return_value={"state": "PENDING", "mpesa_ref": ""})
    def test_unconfirmed_code_queued_for_review(self, fetch, fulfil):
        payment = Payment.objects.create(
            user=self.user, feature="ai_chat_access", amount=50, checkout_id="CHK1",
        )
        self.assertEqual(self.post("TGH4ABC123").json()["status"], "under_review")
        payment.refresh_from_db()
        self.assertEqual(payment.status, "pending")
        self.assertEqual(payment.mpesa_code, "TGH4ABC123")
        fulfil.assert_not_called()

    def test_code_from_another_account_rejected(self, fulfil):
        other = User.objects.create_user(email="other@example.com", password="pass1234")
        payment = Payment.objects.create(user=other, feature="ai_chat_access", amount=50, status="completed")
        Transaction.objects.create(payment=payment, mpesa_ref="TGH4ABC123", amount=50)
        self.assertEqual(self.post("TGH4ABC123").json()["status"], "not_found")

    def test_rate_limited(self, fulfil):
        for _ in range(10):
            self.post("hello-not-a-code TGH4ABC12X")
        self.assertEqual(self.post("TGH4ABC123").status_code, 429)
