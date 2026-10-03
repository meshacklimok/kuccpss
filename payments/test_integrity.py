"""
Database-level integrity tests for payments: constraints, webhook idempotency,
per-user isolation and the affiliate commission ledger.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import AffiliateCommission, AffiliateProfile, Referral
from analytics.models import AuditLog
from payments.models import Payment, Transaction
from payments.services import credit_affiliate_commission
from payments.views import complete_payment

User = get_user_model()


class PaymentConstraintTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="payer@example.com", password="pass1234")

    def test_negative_amount_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(user=self.user, feature="view_cluster_points", amount=-1)

    def test_unknown_status_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(user=self.user, feature="view_cluster_points", amount=50, status="paid")

    def test_duplicate_checkout_id_rejected(self):
        Payment.objects.create(user=self.user, feature="view_cluster_points", amount=50, checkout_id="CHK1")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(user=self.user, feature="view_cluster_points", amount=50, checkout_id="CHK1")

    def test_blank_checkout_ids_may_repeat(self):
        Payment.objects.create(user=self.user, feature="view_cluster_points", amount=50)
        Payment.objects.create(user=self.user, feature="view_cluster_points", amount=50)
        self.assertEqual(Payment.objects.filter(checkout_id="").count(), 2)

    def test_negative_transaction_amount_rejected(self):
        p = Payment.objects.create(user=self.user, feature="view_cluster_points", amount=50)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Transaction.objects.create(payment=p, amount=Decimal("-5"))


@override_settings(INTASEND_WEBHOOK_SECRET="", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class WebhookIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="payer@example.com", password="pass1234")
        self.payment = Payment.objects.create(user=self.user, feature="view_cluster_points", amount=50)

    def _post(self, state, value="50", ref="QAB123XYZ"):
        return self.client.post(
            reverse("payments:mpesa_webhook"),
            data=json.dumps({"api_ref": str(self.payment.pk), "state": state,
                             "mpesa_reference": ref, "value": value}),
            content_type="application/json",
        )

    def test_retried_webhook_records_one_transaction_and_completes_once(self):
        for _ in range(3):
            self.assertEqual(self._post("COMPLETE").status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "completed")
        self.assertEqual(self.payment.transactions.count(), 1)
        self.assertEqual(AuditLog.objects.filter(action="payment.completed").count(), 1)

    def test_late_failed_webhook_does_not_downgrade_completed_payment(self):
        self._post("COMPLETE")
        self._post("FAILED")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "completed")

    def test_malformed_amount_does_not_500(self):
        self.assertEqual(self._post("COMPLETE", value="not-a-number").status_code, 200)
        self.assertEqual(self.payment.transactions.get().amount, Decimal("0"))

    def test_complete_payment_returns_true_only_once(self):
        self.assertTrue(complete_payment(self.payment))
        self.assertFalse(complete_payment(self.payment))


class PerUserIsolationTests(TestCase):
    """Users must never read each other's payments — every lookup is scoped to request.user."""

    def setUp(self):
        owner = User.objects.create_user(email="owner@example.com", password="pass1234")
        self.other = User.objects.create_user(email="other@example.com", password="pass1234")
        self.payment = Payment.objects.create(user=owner, feature="view_cluster_points",
                                              amount=50, status="completed")

    def test_other_user_gets_404_on_status_and_receipt(self):
        self.client.force_login(self.other)
        for name in ("payments:payment_status", "payments:payment_receipt"):
            resp = self.client.get(reverse(name, args=[self.payment.pk]))
            self.assertEqual(resp.status_code, 404, name)


class AffiliateLedgerTests(TestCase):
    def setUp(self):
        referrer = User.objects.create_user(email="aff@example.com", password="pass1234")
        self.buyer = User.objects.create_user(email="buyer@example.com", password="pass1234")
        Referral.objects.create(referrer=referrer, code="ABC123", referred_user=self.buyer, converted=True)
        self.affiliate = AffiliateProfile.objects.create(user=referrer, commission_rate=Decimal("20"))
        self.payment = Payment.objects.create(user=self.buyer, feature="view_cluster_points",
                                              amount=Decimal("100"), status="completed")

    def test_commission_credited_exactly_once(self):
        credit_affiliate_commission(self.payment)
        credit_affiliate_commission(self.payment)
        self.affiliate.refresh_from_db()
        self.assertEqual(AffiliateCommission.objects.filter(payment=self.payment).count(), 1)
        self.assertEqual(self.affiliate.wallet_balance, Decimal("20"))
        self.assertEqual(self.affiliate.total_earned, Decimal("20"))
        self.assertEqual(AuditLog.objects.filter(action="affiliate.commission_credited").count(), 1)

    def test_wallet_cannot_go_negative(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AffiliateProfile.objects.filter(pk=self.affiliate.pk).update(wallet_balance=Decimal("-1"))

    def test_commission_rate_bounded(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AffiliateProfile.objects.filter(pk=self.affiliate.pk).update(commission_rate=Decimal("150"))
