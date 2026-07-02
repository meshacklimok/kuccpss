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
