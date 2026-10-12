"""After a payment completes, each paid feature must actually unlock for the payer."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from career.models import AIChatCredit, CareerConfig, CareerSubmission
from career.views import _check_and_increment_ai_calls
from payments.models import Payment, PaymentFeature
from payments.services import has_paid_for_current_session, has_paid_for_feature
from payments.views import complete_payment

User = get_user_model()


def _enable(feature, price):
    PaymentFeature.objects.update_or_create(
        feature=feature, defaults={"label": feature, "price": price, "is_enabled": True}
    )


def _pay(user, feature, amount):
    payment = Payment.objects.create(user=user, feature=feature, amount=amount, status="pending")
    complete_payment(payment, mpesa_code="TGH4ABC123")
    return payment


class FeatureUnlockAfterPaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="payer@example.com", password="pass1234")

    def _submission(self, feature):
        return CareerSubmission.objects.create(
            user=self.user, feature=feature, grades_json={"mathematics": 10},
            lock_at=timezone.now() + timedelta(days=1),
        )

    def test_view_cluster_points(self):
        _enable("view_cluster_points", 50)
        self._submission(CareerSubmission.FEATURE_CALCULATOR)
        gate = lambda: has_paid_for_current_session(
            self.user, CareerSubmission.FEATURE_CALCULATOR, "view_cluster_points")
        self.assertFalse(gate())
        _pay(self.user, "view_cluster_points", 50)
        self.assertTrue(gate())

    def test_premium_career_report_degree_and_non_degree(self):
        _enable("premium_career_report", 50)
        self._submission(CareerSubmission.FEATURE_DEGREE)
        self._submission(CareerSubmission.FEATURE_NON_DEGREE)
        gate = lambda f: has_paid_for_current_session(self.user, f, "premium_career_report")
        self.assertFalse(gate(CareerSubmission.FEATURE_DEGREE))
        self.assertFalse(gate(CareerSubmission.FEATURE_NON_DEGREE))
        _pay(self.user, "premium_career_report", 50)
        self.assertTrue(gate(CareerSubmission.FEATURE_DEGREE))
        self.assertTrue(gate(CareerSubmission.FEATURE_NON_DEGREE))

    def test_view_eligible_courses(self):
        _enable("view_eligible_courses", 50)
        self.assertFalse(has_paid_for_feature(self.user, "view_eligible_courses"))
        _pay(self.user, "view_eligible_courses", 50)
        self.assertTrue(has_paid_for_feature(self.user, "view_eligible_courses"))

    def test_advanced_analysis_is_recorded_as_paid(self):
        # Only records the purchase: no view currently checks this feature (see docs).
        _enable("advanced_analysis", 149)
        self.assertFalse(has_paid_for_feature(self.user, "advanced_analysis"))
        _pay(self.user, "advanced_analysis", 149)
        self.assertTrue(has_paid_for_feature(self.user, "advanced_analysis"))

    def test_ai_chat_access_tops_up_messages(self):
        _enable("ai_chat_access", 50)
        cfg = CareerConfig.get()
        credit = AIChatCredit.for_user(self.user)
        credit.free_messages_used = cfg.ai_free_message_limit
        credit.save()
        request = RequestFactory().post("/")
        request.user = self.user
        allowed, _, _, reason = _check_and_increment_ai_calls(request)
        self.assertFalse(allowed)
        self.assertEqual(reason, "payment_required")

        _pay(self.user, "ai_chat_access", 50)
        allowed, _, _, reason = _check_and_increment_ai_calls(request)
        self.assertTrue(allowed, reason)
        self.assertEqual(
            AIChatCredit.for_user(self.user).paid_messages_remaining, cfg.ai_paid_message_limit - 1)
