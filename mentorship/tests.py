import json
import uuid
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from mentorship.models import MentorProfile, MentorshipSession, TimeSlot
from payments.models import Payment

User = get_user_model()


@override_settings(INTASEND_WEBHOOK_SECRET="", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MentorshipDoubleWebhookConfirmationTests(TestCase):
    """
    A mentorship session can be confirmed via two independent webhook endpoints —
    payments:mpesa_webhook (the one actually registered with IntaSend) and
    mentorship:payment_webhook (kept as a fallback). Both funnel into the shared
    _confirm_session_after_payment() and must credit the mentor's wallet exactly
    once even if IntaSend (or a retry) delivers the callback to both endpoints.
    """

    def setUp(self):
        mentor_user = User.objects.create_user(email="mentor@example.com", password="pass1234")
        self.mentor = MentorProfile.objects.create(
            user=mentor_user,
            bio="Experienced mentor",
            whatsapp="+254712345678",
            is_approved=True,
        )
        mentee = User.objects.create_user(email="mentee@example.com", password="pass1234")
        slot = TimeSlot.objects.create(
            mentor=self.mentor,
            date=date.today() + timedelta(days=1),
            start_time="14:00",
        )
        self.session = MentorshipSession.objects.create(
            token=uuid.uuid4(),
            mentor=self.mentor,
            mentee=mentee,
            slot=slot,
            mentee_question="What is campus life like?",
            amount=100,
            mentor_payout=70,
            status="pending_payment",
        )
        self.payment = Payment.objects.create(
            user=mentee,
            feature="mentorship_booking",
            amount=100,
            status="pending",
            mentorship_session=self.session,
        )

    def _webhook_payload(self):
        return {
            "state": "COMPLETE",
            "api_ref": str(self.session.token),
            "invoice_id": "INV-TEST-001",
        }

    def test_single_webhook_confirms_and_credits_mentor(self):
        response = self.client.post(
            reverse("payments:mpesa_webhook"),
            data=json.dumps(self._webhook_payload()),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        self.session.refresh_from_db()
        self.mentor.refresh_from_db()
        self.assertEqual(self.session.status, "confirmed")
        self.assertEqual(self.mentor.wallet_balance, 70)
        self.assertEqual(self.mentor.total_earned, 70)

    def test_both_webhooks_firing_credits_mentor_only_once(self):
        payload = json.dumps(self._webhook_payload())

        first = self.client.post(
            reverse("payments:mpesa_webhook"), data=payload, content_type="application/json"
        )
        second = self.client.post(
            reverse("mentorship:payment_webhook"), data=payload, content_type="application/json"
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        self.session.refresh_from_db()
        self.mentor.refresh_from_db()
        self.assertEqual(self.session.status, "confirmed")
        # Idempotency guard: second webhook finds no session with status
        # "pending_payment" (already confirmed) so it must not double-credit.
        self.assertEqual(self.mentor.wallet_balance, 70)
        self.assertEqual(self.mentor.total_earned, 70)

    def test_confirmation_marks_linked_payment_completed(self):
        self.client.post(
            reverse("payments:mpesa_webhook"),
            data=json.dumps(self._webhook_payload()),
            content_type="application/json",
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "completed")

    def test_webhook_with_unknown_token_is_ignored(self):
        payload = {
            "state": "COMPLETE",
            "api_ref": str(uuid.uuid4()),
            "invoice_id": "INV-UNKNOWN",
        }
        response = self.client.post(
            reverse("payments:mpesa_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "pending_payment")
